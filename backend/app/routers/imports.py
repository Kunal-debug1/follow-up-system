from __future__ import annotations

import logging
import os
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
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


def _file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".csv":
        return "csv"
    # Legacy .xls was previously routed through pandas, but is not safely
    # supported by the streaming XLSX reader and is deliberately rejected.
    raise HTTPException(400, "Only CSV and XLSX files are supported.")


async def _save_upload(file: UploadFile, filename: str) -> tuple[Path, int]:
    suffix = Path(filename).suffix.lower()
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="crm-import-")
    size = 0
    try:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"Upload exceeds the {MAX_UPLOAD_BYTES // 1024 // 1024} MB safety limit.")
            handle.write(chunk)
        handle.close()
        if not size:
            raise HTTPException(400, "Uploaded file is empty.")
        return Path(handle.name), size
    except Exception:
        handle.close()
        Path(handle.name).unlink(missing_ok=True)
        raise


def _validate(analysis: dict) -> None:
    if analysis.get("missing_required"):
        raise HTTPException(422, {"message": "Could not detect a customer name column.", "analysis": analysis})


def _sheets(path: Path, file_type: str, selected: str | None) -> list[str | None]:
    sheets = workbook_sheets(path) if file_type == "xlsx" else [None]
    if selected is not None:
        if selected not in sheets:
            raise HTTPException(400, {"message": "Selected sheet does not exist.", "available_sheets": sheets})
        return [selected]
    return sheets


def _analysis(path: Path, file_type: str, sheet: str | None) -> dict:
    try:
        return analyze_file(path, file_type, sheet)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/analyze")
async def analyze(file: UploadFile = File(...), sheet: str | None = Query(default=None)):
    filename = file.filename or "upload"
    file_type = _file_type(filename)
    path, size = await _save_upload(file, filename)
    started = monotonic()
    try:
        selected = _sheets(path, file_type, sheet)
        results = []
        for current in selected:
            analysis = _analysis(path, file_type, current)
            results.append({"sheet": current, "rows": analysis["total_rows"], "valid_records": 0, "header_row": analysis["header_row"], "detected_mapping": analysis["detected_mapping"], "status": "skipped" if analysis["missing_required"] else "processed"})
        if file_type == "xlsx" and sheet is None:
            return {"file": filename, "sheets": [item for item in selected if item], "selected_sheet": None, "mode": "all_sheets", "sheet_results": results, "total_records": sum(item["rows"] for item in results if item["status"] == "processed"), "records_with_phone": 0, "records_without_phone": 0}
        result = _analysis(path, file_type, selected[0])
        result.update({"sheets": selected if file_type == "xlsx" else None, "selected_sheet": selected[0]})
        return result
    finally:
        logger.info("import analyze filename=%s size=%d sheet=%s seconds=%.3f", filename, size, sheet or "all", monotonic()-started)
        path.unlink(missing_ok=True)


@router.post("/preview")
async def preview(file: UploadFile = File(...), sheet: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=MAX_SAMPLE_ROWS), db: Session = Depends(get_db)):
    filename = file.filename or "upload"; file_type = _file_type(filename); path, size = await _save_upload(file, filename); started = monotonic()
    try:
        selected = _sheets(path, file_type, sheet)
        if len(selected) != 1:
            raise HTTPException(400, "Choose a worksheet before previewing or importing an XLSX file.")
        analysis = _analysis(path, file_type, selected[0]); _validate(analysis)
        summary, rows = preview_file(db, path, file_type, selected[0], analysis["detected_mapping"], limit)
        return {"file": filename, "sheet": selected[0], "sheets": selected if file_type == "xlsx" else None, "mode": "single_sheet" if file_type == "xlsx" else "csv", "analysis": analysis, "summary": summary, "preview": rows}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        logger.info("import preview filename=%s size=%d sheet=%s seconds=%.3f", filename, size, sheet or "default", monotonic()-started)
        path.unlink(missing_ok=True)


@router.post("/import")
async def import_file(file: UploadFile = File(...), sheet: str | None = Query(default=None), db: Session = Depends(get_db)):
    filename = file.filename or "upload"; file_type = _file_type(filename); path, size = await _save_upload(file, filename); started = monotonic()
    try:
        selected = _sheets(path, file_type, sheet)
        analyses = [(current, _analysis(path, file_type, current)) for current in selected]
        for _, analysis in analyses: _validate(analysis)
        records = chain.from_iterable(iter_records(path, file_type, current, analysis["detected_mapping"]) for current, analysis in analyses)
        result = import_record_batches(db, filename, file_type, records)
        if not result["total_rows"]:
            raise HTTPException(422, "No valid customer records found.")
        result.update({"mode": "single_sheet" if file_type == "xlsx" and sheet else "all_sheets" if file_type == "xlsx" else "csv", "sheet": sheet, "sheets": [current for current in selected if current], "sheets_processed": len(selected)})
        logger.info("import complete filename=%s size=%d sheet=%s rows=%d imported=%d skipped=%d seconds=%.3f", filename, size, sheet or "all", result["total_rows"], result["imported_rows"], result["skipped_rows"] + result["duplicate_rows"], monotonic()-started)
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception("import failed filename=%s size=%d sheet=%s", filename, size, sheet or "all")
        raise HTTPException(500, "Import could not be completed. No details were exposed.")
    finally:
        path.unlink(missing_ok=True)
