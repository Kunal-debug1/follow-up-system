"""
Import router — file upload, analysis, preview, and bulk import endpoints.

Upload security:
    - Maximum file size enforced during streaming upload (no full-memory load)
    - Only .csv and .xlsx extensions accepted
    - Temporary files use safe system-generated names (no user filename in path)
    - Temporary files are always cleaned up in finally blocks
    - .xls (legacy) is explicitly rejected
"""
from __future__ import annotations

import logging
import tempfile
from itertools import chain
from pathlib import Path
from time import monotonic

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.import_service import (
    MAX_SAMPLE_ROWS,
    analyze_file,
    import_record_batches,
    iter_records,
    preview_file,
    workbook_sheets,
)

router = APIRouter(prefix="/api/import", tags=["Import"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

import os
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _file_type(filename: str) -> str:
    """Return 'xlsx' or 'csv', or raise HTTP 400 for unsupported types."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".csv":
        return "csv"
    # Legacy .xls is deliberately rejected — not safely supported by the
    # streaming XLSX reader and requires a separate binary dependency.
    raise HTTPException(400, "Only CSV and XLSX files are supported.")


async def _save_upload(file: UploadFile, filename: str) -> tuple[Path, int]:
    """
    Stream the upload to a secure temporary file.

    - Never stores the user-supplied filename in the filesystem path.
    - Enforces MAX_UPLOAD_BYTES during streaming (no full-memory load).
    - Cleans up the temp file on error.
    """
    suffix = Path(filename).suffix.lower()
    handle = tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, prefix="crm-import-"
    )
    size = 0
    try:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    413,
                    f"Upload exceeds the {MAX_UPLOAD_BYTES // 1024 // 1024} MB safety limit.",
                )
            handle.write(chunk)
        handle.close()
        if not size:
            raise HTTPException(400, "Uploaded file is empty.")
        return Path(handle.name), size
    except Exception:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)
        raise


def _validate_analysis(analysis: dict) -> None:
    """Raise HTTP 422 if required columns are missing from the detected mapping."""
    if analysis.get("missing_required"):
        raise HTTPException(
            422,
            {"message": "Could not detect a customer name column.", "analysis": analysis},
        )


def _resolve_sheets(path: Path, file_type: str, selected: str | None) -> list[str | None]:
    """
    Return the list of sheet names to process.

    For CSV files, returns [None] (no sheet concept).
    For XLSX files, validates the selected sheet if one was specified.
    """
    if file_type != "xlsx":
        return [None]

    sheets = workbook_sheets(path)
    if selected is not None:
        if selected not in sheets:
            raise HTTPException(
                400,
                {"message": "Selected sheet does not exist.", "available_sheets": sheets},
            )
        return [selected]
    return sheets


def _run_analysis(path: Path, file_type: str, sheet: str | None) -> dict:
    """Run analyze_file and convert ValueError to HTTP 400."""
    try:
        return analyze_file(path, file_type, sheet)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
) -> dict:
    """
    Analyse the uploaded file structure without importing.

    Reads only a small header sample — never scans all rows for performance.
    Returns detected column mapping, header row, and sheet names.
    """
    filename = file.filename or "upload"
    file_type = _file_type(filename)
    path, size = await _save_upload(file, filename)
    started = monotonic()

    try:
        sheets = _resolve_sheets(path, file_type, sheet)

        # Multi-sheet mode: return a summary for each sheet
        if file_type == "xlsx" and sheet is None:
            results = []
            for current in sheets:
                analysis = _run_analysis(path, file_type, current)
                results.append({
                    "sheet": current,
                    "rows": analysis["total_rows"],
                    "valid_records": 0,
                    "header_row": analysis["header_row"],
                    "detected_mapping": analysis["detected_mapping"],
                    "status": "skipped" if analysis["missing_required"] else "processed",
                })
            return {
                "file": filename,
                "sheets": [s for s in sheets if s],
                "selected_sheet": None,
                "mode": "all_sheets",
                "sheet_results": results,
                "total_records": sum(
                    r["rows"] for r in results if r["status"] == "processed"
                ),
                "records_with_phone": 0,
                "records_without_phone": 0,
            }

        # Single-sheet mode
        result = _run_analysis(path, file_type, sheets[0])
        result.update({
            "sheets": sheets if file_type == "xlsx" else None,
            "selected_sheet": sheets[0],
        })
        return result

    finally:
        logger.info(
            "import analyze filename=%s size=%d sheet=%s seconds=%.3f",
            filename, size, sheet or "all", monotonic() - started,
        )
        path.unlink(missing_ok=True)


@router.post("/preview")
async def preview(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_SAMPLE_ROWS),
    db: Session = Depends(get_db),
) -> dict:
    """
    Preview the first `limit` records without importing.

    A single file pass is used — the file is never read twice.
    """
    filename = file.filename or "upload"
    file_type = _file_type(filename)
    path, size = await _save_upload(file, filename)
    started = monotonic()

    try:
        sheets = _resolve_sheets(path, file_type, sheet)

        if len(sheets) != 1:
            raise HTTPException(
                400,
                "Choose a worksheet before previewing or importing an XLSX file.",
            )

        analysis = _run_analysis(path, file_type, sheets[0])
        _validate_analysis(analysis)

        summary, rows = preview_file(
            db, path, file_type, sheets[0], analysis["detected_mapping"], limit
        )

        return {
            "file": filename,
            "sheet": sheets[0],
            "sheets": sheets if file_type == "xlsx" else None,
            "mode": "single_sheet" if file_type == "xlsx" else "csv",
            "analysis": analysis,
            "summary": summary,
            "preview": rows,
        }

    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    finally:
        logger.info(
            "import preview filename=%s size=%d sheet=%s seconds=%.3f",
            filename, size, sheet or "default", monotonic() - started,
        )
        path.unlink(missing_ok=True)


@router.post("/import")
async def import_file(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """
    Stream and import all records from the uploaded file.

    Memory model: O(IMPORT_BATCH_SIZE) — not O(total_rows).
    Records are streamed, batched, inserted, and committed incrementally.
    The file is never fully loaded into memory.
    """
    filename = file.filename or "upload"
    file_type = _file_type(filename)
    path, size = await _save_upload(file, filename)
    started = monotonic()

    try:
        sheets = _resolve_sheets(path, file_type, sheet)

        # Analyse all target sheets and validate before touching the database
        analyses: list[tuple[str | None, dict]] = [
            (current, _run_analysis(path, file_type, current))
            for current in sheets
        ]
        for _, analysis in analyses:
            _validate_analysis(analysis)

        # Chain record iterators across all sheets
        records = chain.from_iterable(
            iter_records(path, file_type, current, analysis["detected_mapping"])
            for current, analysis in analyses
        )

        result = import_record_batches(db, filename, file_type, records)

        if not result["total_rows"]:
            raise HTTPException(422, "No valid customer records found.")

        result.update({
            "mode": (
                "single_sheet" if file_type == "xlsx" and sheet
                else "all_sheets" if file_type == "xlsx"
                else "csv"
            ),
            "sheet": sheet,
            "sheets": [s for s in sheets if s],
            "sheets_processed": len(sheets),
        })

        logger.info(
            "import complete filename=%s size=%d sheet=%s rows=%d "
            "imported=%d skipped=%d seconds=%.3f",
            filename, size, sheet or "all",
            result["total_rows"], result["imported_rows"],
            result["skipped_rows"] + result["duplicate_rows"],
            monotonic() - started,
        )
        return result

    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "import failed filename=%s size=%d sheet=%s",
            filename, size, sheet or "all",
        )
        raise HTTPException(500, "Import could not be completed.")

    finally:
        path.unlink(missing_ok=True)
