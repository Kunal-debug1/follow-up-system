from __future__ import annotations

"""
CRM Excel / CSV Import Router

This module handles:

    POST /api/import/analyze
    POST /api/import/preview
    POST /api/import/import

Design goals:
    - Keep uploads memory-safe.
    - Never load the complete XLSX into RAM.
    - Enforce a maximum upload size.
    - Validate worksheet selection.
    - Clean up temporary files.
    - Return useful API errors.
    - Work correctly with the existing import_service.py.
    - Avoid unnecessary duplicate file analysis.
"""

import logging
import tempfile
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


# ============================================================
# ROUTER CONFIGURATION
# ============================================================

router = APIRouter(
    prefix="/api/import",
    tags=["Import"],
)

logger = logging.getLogger(__name__)


# ============================================================
# UPLOAD SAFETY CONFIGURATION
# ============================================================

# Maximum uploaded file size.
#
# 12 MB is intentionally conservative because your Render
# instance has limited memory.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

# Uploads are read in 1 MB chunks.
UPLOAD_CHUNK_SIZE = 1024 * 1024


# ============================================================
# FILE TYPE DETECTION
# ============================================================

def _file_type(filename: str) -> str:
    """
    Determine the supported file type from the filename.

    Supported:
        .xlsx
        .csv

    Deliberately not supporting:
        .xls

    The current importer uses openpyxl's streaming XLSX reader,
    which is designed for .xlsx files.
    """

    suffix = Path(filename).suffix.lower()

    if suffix == ".xlsx":
        return "xlsx"

    if suffix == ".csv":
        return "csv"

    raise HTTPException(
        status_code=400,
        detail="Only CSV and XLSX files are supported.",
    )


# ============================================================
# SAVE UPLOADED FILE SAFELY
# ============================================================

async def _save_upload(
    file: UploadFile,
    filename: str,
) -> tuple[Path, int]:
    """
    Save the uploaded file to a temporary file.

    IMPORTANT:
    We do not call await file.read() without a limit.

    Instead, the upload is copied in chunks so a large request
    cannot consume the entire Render instance's RAM.
    """

    suffix = Path(filename).suffix.lower()

    temporary = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        prefix="crm-import-",
    )

    path = Path(temporary.name)
    size = 0

    try:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)

            if not chunk:
                break

            size += len(chunk)

            # Stop immediately if the file is too large.
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Upload exceeds the "
                        f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB "
                        f"safety limit."
                    ),
                )

            temporary.write(chunk)

        temporary.close()

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        return path, size

    except Exception:
        # Always close the file handle.
        try:
            temporary.close()
        except Exception:
            pass

        # Remove partially uploaded file.
        path.unlink(missing_ok=True)

        raise


# ============================================================
# WORKSHEET SELECTION
# ============================================================

def _get_sheets(
    path: Path,
    file_type: str,
    selected_sheet: str | None,
) -> list[str | None]:
    """
    Get available worksheets.

    CSV:
        Returns [None]

    XLSX:
        Returns all worksheet names.

    If the caller specified a worksheet, validate it.
    """

    if file_type == "csv":
        sheets: list[str | None] = [None]

    else:
        try:
            sheets = workbook_sheets(path)

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

    # Validate explicitly selected worksheet.
    if selected_sheet is not None:

        if selected_sheet not in sheets:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Selected sheet does not exist.",
                    "available_sheets": [
                        sheet
                        for sheet in sheets
                        if sheet is not None
                    ],
                },
            )

        return [selected_sheet]

    return sheets


# ============================================================
# FILE ANALYSIS HELPER
# ============================================================

def _run_analysis(
    path: Path,
    file_type: str,
    sheet: str | None,
) -> dict:
    """
    Run import-service analysis and convert known parsing
    errors into clean HTTP errors.
    """

    try:
        return analyze_file(
            path,
            file_type,
            sheet,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Unexpected error while analyzing file. "
            "file_type=%s sheet=%s",
            file_type,
            sheet,
        )

        raise HTTPException(
            status_code=500,
            detail="Could not analyze the uploaded file.",
        )


# ============================================================
# VALIDATE ANALYSIS
# ============================================================

def _validate_analysis(analysis: dict) -> None:
    """
    Validate whether the importer detected the minimum
    required customer information.

    Currently the importer requires a customer name.
    """

    if analysis.get("missing_required"):

        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    "Could not detect a customer name column."
                ),
                "analysis": analysis,
            },
        )


# ============================================================
# ANALYZE ENDPOINT
# ============================================================

@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
):
    """
    Analyze an uploaded CSV/XLSX file.

    For XLSX:
        - If no sheet is selected, analyze all worksheet names
          and select the first usable worksheet.
        - If a sheet is selected, analyze only that sheet.

    IMPORTANT:
        This endpoint does NOT import customers.
    """

    filename = file.filename or "upload"

    # Determine extension.
    file_type = _file_type(filename)

    # Save upload to temporary disk.
    path, size = await _save_upload(
        file,
        filename,
    )

    started = monotonic()

    try:
        # --------------------------------------------------------
        # Get available sheets
        # --------------------------------------------------------

        sheets = _get_sheets(
            path,
            file_type,
            sheet,
        )

        # --------------------------------------------------------
        # CSV
        # --------------------------------------------------------

        if file_type == "csv":

            analysis = _run_analysis(
                path,
                file_type,
                None,
            )

            analysis.update(
                {
                    "file": filename,
                    "file_type": file_type,
                    "sheets": None,
                    "selected_sheet": None,
                    "mode": "csv",
                }
            )

            return analysis

        # --------------------------------------------------------
        # XLSX WITH EXPLICIT SHEET
        # --------------------------------------------------------

        if sheet is not None:

            analysis = _run_analysis(
                path,
                file_type,
                sheet,
            )

            analysis.update(
                {
                    "file": filename,
                    "file_type": file_type,
                    "sheets": sheets,
                    "selected_sheet": sheet,
                    "mode": "single_sheet",
                }
            )

            return analysis

        # --------------------------------------------------------
        # XLSX WITHOUT EXPLICIT SHEET
        #
        # Analyze each worksheet only once.
        # --------------------------------------------------------

        sheet_results = []

        for current_sheet in sheets:

            if current_sheet is None:
                continue

            try:
                analysis = _run_analysis(
                    path,
                    file_type,
                    current_sheet,
                )

                sheet_results.append(
                    {
                        "sheet": current_sheet,
                        "rows": analysis.get(
                            "total_rows",
                            0,
                        ),
                        "valid_records": 0,
                        "header_row": analysis.get(
                            "header_row"
                        ),
                        "detected_mapping": analysis.get(
                            "detected_mapping",
                            {},
                        ),
                        "status": (
                            "skipped"
                            if analysis.get(
                                "missing_required"
                            )
                            else "processed"
                        ),
                    }
                )

            except HTTPException as exc:

                # Don't make one broken worksheet prevent
                # the user from selecting another worksheet.
                sheet_results.append(
                    {
                        "sheet": current_sheet,
                        "rows": 0,
                        "valid_records": 0,
                        "header_row": None,
                        "detected_mapping": {},
                        "status": "error",
                        "error": exc.detail,
                    }
                )

        # --------------------------------------------------------
        # Find first usable worksheet.
        # --------------------------------------------------------

        selected_sheet = next(
            (
                item["sheet"]
                for item in sheet_results
                if item["status"] == "processed"
            ),
            None,
        )

        # --------------------------------------------------------
        # No usable worksheet.
        # --------------------------------------------------------

        if not selected_sheet:

            return {
                "file": filename,
                "file_type": file_type,
                "sheets": [
                    sheet_name
                    for sheet_name in sheets
                    if sheet_name
                ],
                "selected_sheet": None,
                "mode": "select_sheet",
                "sheet_results": sheet_results,
                "total_records": 0,
                "records_with_phone": 0,
                "records_without_phone": 0,
                "missing_required": ["name"],
            }

        # --------------------------------------------------------
        # Return the analysis of the selected worksheet.
        #
        # This is one additional analysis only for the selected
        # worksheet so the frontend receives the complete mapping.
        # --------------------------------------------------------

        selected_analysis = _run_analysis(
            path,
            file_type,
            selected_sheet,
        )

        selected_analysis.update(
            {
                "file": filename,
                "file_type": file_type,
                "sheets": [
                    sheet_name
                    for sheet_name in sheets
                    if sheet_name
                ],
                "selected_sheet": selected_sheet,
                "mode": "single_sheet",
                "sheet_results": sheet_results,
            }
        )

        return selected_analysis

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Unexpected import analyze failure. "
            "filename=%s size=%d sheet=%s",
            filename,
            size,
            sheet or "all",
        )

        raise HTTPException(
            status_code=500,
            detail="Could not analyze the uploaded file.",
        )

    finally:
        # --------------------------------------------------------
        # ALWAYS DELETE TEMPORARY FILE
        # --------------------------------------------------------

        path.unlink(missing_ok=True)

        logger.info(
            "Import analyze finished: "
            "filename=%s size=%d sheet=%s seconds=%.3f",
            filename,
            size,
            sheet or "all",
            monotonic() - started,
        )


# ============================================================
# PREVIEW ENDPOINT
# ============================================================

@router.post("/preview")
async def preview(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
    limit: int = Query(
        default=100,
        ge=1,
        le=MAX_SAMPLE_ROWS,
    ),
    db: Session = Depends(get_db),
):
    """
    Preview customer records before importing.

    The preview does not modify the database.
    """

    filename = file.filename or "upload"
    file_type = _file_type(filename)

    path, size = await _save_upload(
        file,
        filename,
    )

    started = monotonic()

    try:
        # --------------------------------------------------------
        # Determine worksheet.
        # --------------------------------------------------------

        selected = _get_sheets(
            path,
            file_type,
            sheet,
        )

        # XLSX preview requires exactly one worksheet.
        if file_type == "xlsx" and len(selected) != 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Choose a worksheet before previewing "
                    "an XLSX file."
                ),
            )

        selected_sheet = selected[0]

        # --------------------------------------------------------
        # Analyze selected source.
        # --------------------------------------------------------

        analysis = _run_analysis(
            path,
            file_type,
            selected_sheet,
        )

        _validate_analysis(analysis)

        # --------------------------------------------------------
        # Generate preview.
        # --------------------------------------------------------

        summary, rows = preview_file(
            db,
            path,
            file_type,
            selected_sheet,
            analysis["detected_mapping"],
            limit,
        )

        return {
            "file": filename,
            "file_type": file_type,
            "sheet": selected_sheet,
            "sheets": (
                [
                    sheet_name
                    for sheet_name in selected
                    if sheet_name
                ]
                if file_type == "xlsx"
                else None
            ),
            "mode": (
                "single_sheet"
                if file_type == "xlsx"
                else "csv"
            ),
            "analysis": analysis,
            "summary": summary,
            "preview": rows,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception(
            "Unexpected import preview failure. "
            "filename=%s size=%d sheet=%s",
            filename,
            size,
            sheet or "default",
        )

        raise HTTPException(
            status_code=500,
            detail="Could not generate import preview.",
        )

    finally:
        # Always remove uploaded temporary file.
        path.unlink(missing_ok=True)

        logger.info(
            "Import preview finished: "
            "filename=%s size=%d sheet=%s seconds=%.3f",
            filename,
            size,
            sheet or "default",
            monotonic() - started,
        )


# ============================================================
# IMPORT ENDPOINT
# ============================================================

@router.post("/import")
async def import_file(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Import customers from CSV/XLSX into PostgreSQL.

    XLSX:
        A worksheet must be explicitly selected.

    CSV:
        No worksheet is required.
    """

    filename = file.filename or "upload"
    file_type = _file_type(filename)

    path, size = await _save_upload(
        file,
        filename,
    )

    started = monotonic()

    try:
        # --------------------------------------------------------
        # XLSX requires a selected worksheet.
        # --------------------------------------------------------

        if file_type == "xlsx" and not sheet:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Choose a worksheet before "
                    "importing an XLSX file."
                ),
            )

        # --------------------------------------------------------
        # Get selected worksheet.
        # --------------------------------------------------------

        selected = _get_sheets(
            path,
            file_type,
            sheet,
        )

        # Safety check.
        if file_type == "xlsx" and len(selected) != 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Choose exactly one worksheet "
                    "before importing."
                ),
            )

        # --------------------------------------------------------
        # Analyze worksheet.
        # --------------------------------------------------------

        analyses = []

        for current_sheet in selected:

            analysis = _run_analysis(
                path,
                file_type,
                current_sheet,
            )

            _validate_analysis(analysis)

            analyses.append(
                (
                    current_sheet,
                    analysis,
                )
            )

        # --------------------------------------------------------
        # Build a lazy record generator.
        #
        # IMPORTANT:
        # Do NOT convert this to list().
        #
        # iter_records() streams the worksheet.
        # --------------------------------------------------------

        def records_generator():

            for current_sheet, analysis in analyses:

                yield from iter_records(
                    path,
                    file_type,
                    current_sheet,
                    analysis["detected_mapping"],
                )

        # --------------------------------------------------------
        # Import in database batches.
        # --------------------------------------------------------

        result = import_record_batches(
            db,
            filename,
            file_type,
            records_generator(),
        )

        # --------------------------------------------------------
        # No records found.
        # --------------------------------------------------------

        if not result.get("total_rows"):
            raise HTTPException(
                status_code=422,
                detail="No valid customer records found.",
            )

        # --------------------------------------------------------
        # Add frontend-friendly metadata.
        # --------------------------------------------------------

        result.update(
            {
                "file": filename,
                "file_type": file_type,
                "mode": (
                    "single_sheet"
                    if file_type == "xlsx"
                    else "csv"
                ),
                "sheet": sheet,
                "sheets": [
                    current
                    for current in selected
                    if current
                ],
                "sheets_processed": len(selected),
            }
        )

        logger.info(
            "Import completed: "
            "filename=%s size=%d sheet=%s "
            "rows=%d imported=%d updated=%d "
            "duplicates=%d skipped=%d seconds=%.3f",
            filename,
            size,
            sheet or "default",
            result.get("total_rows", 0),
            result.get("imported_rows", 0),
            result.get("updated_rows", 0),
            result.get("duplicate_rows", 0),
            result.get("skipped_rows", 0),
            monotonic() - started,
        )

        return result

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception(
            "Unexpected import failure: "
            "filename=%s size=%d sheet=%s",
            filename,
            size,
            sheet or "default",
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Import could not be completed. "
                "Please check the file format and try again."
            ),
        )

    finally:
        # --------------------------------------------------------
        # ALWAYS DELETE TEMPORARY FILE
        # --------------------------------------------------------

        path.unlink(missing_ok=True)

        logger.info(
            "Import request finished: "
            "filename=%s size=%d sheet=%s seconds=%.3f",
            filename,
            size,
            sheet or "default",
            monotonic() - started,
        )
