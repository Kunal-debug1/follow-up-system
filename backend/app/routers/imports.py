from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.import_service import (
    analyze_dataframe,
    find_duplicate_summary,
    import_records,
    load_csv,
    load_excel_sheet,
    merge_records,
    prepare_import,
)


router = APIRouter(
    prefix="/api/import",
    tags=["Import"],
)


def is_excel_file(filename: str) -> bool:
    return filename.lower().endswith((".xlsx", ".xls"))


def get_excel_sheets(content: bytes) -> list[str]:
    try:
        return pd.ExcelFile(BytesIO(content)).sheet_names
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read Excel workbook: {exc}",
        ) from exc


def read_upload(
    filename: str,
    content: bytes,
    sheet_name: str | None = None,
):
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    try:
        if filename.lower().endswith(".csv"):
            return load_csv(content)

        if is_excel_file(filename):
            return load_excel_sheet(
                content,
                sheet_name if sheet_name is not None else 0,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read file: {exc}",
        ) from exc

    raise HTTPException(
        status_code=400,
        detail="Only CSV, XLSX and XLS files are supported.",
    )


def validate_analysis(analysis: dict) -> None:
    if analysis.get("missing_required"):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Could not detect a customer name column.",
                "analysis": analysis,
            },
        )


def process_all_excel_sheets(
    content: bytes,
) -> tuple[list[dict], list[dict]]:
    sheets = get_excel_sheets(content)

    all_records: list[dict] = []
    sheet_results: list[dict] = []

    for sheet_name in sheets:
        try:
            df, header_row = load_excel_sheet(content, sheet_name)

            if df.empty:
                sheet_results.append({
                    "sheet": sheet_name,
                    "rows": 0,
                    "valid_records": 0,
                    "status": "empty",
                })
                continue

            analysis = analyze_dataframe(df, header_row)

            if analysis.get("missing_required"):
                sheet_results.append({
                    "sheet": sheet_name,
                    "rows": len(df),
                    "valid_records": 0,
                    "status": "skipped",
                    "reason": "Customer name column not detected",
                })
                continue

            records = prepare_import(
                df,
                analysis["detected_mapping"],
                sheet_name,
            )

            all_records.extend(records)

            mapping = analysis["detected_mapping"]

            sheet_results.append({
                "sheet": sheet_name,
                "rows": len(df),
                "valid_records": len(records),
                "header_row": header_row + 1,
                "detected_mapping": mapping,
                "phone_column": mapping.get("phone"),
                "records_with_phone": sum(
                    1 for record in records if record.get("phone")
                ),
                "status": "processed",
            })

        except Exception as exc:
            sheet_results.append({
                "sheet": sheet_name,
                "rows": 0,
                "valid_records": 0,
                "status": "error",
                "reason": str(exc),
            })

    return merge_records(all_records), sheet_results


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
):
    filename = file.filename or "upload"
    content = await file.read()

    if is_excel_file(filename):
        sheets = get_excel_sheets(content)

        if sheet is not None:
            if sheet not in sheets:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Selected sheet does not exist.",
                        "available_sheets": sheets,
                    },
                )

            df, header_row = read_upload(
                filename,
                content,
                sheet,
            )
            result = analyze_dataframe(df, header_row)
            result["sheets"] = sheets
            result["selected_sheet"] = sheet
            return result

        records, sheet_results = process_all_excel_sheets(content)

        return {
            "file": filename,
            "sheets": sheets,
            "selected_sheet": None,
            "mode": "all_sheets",
            "sheet_results": sheet_results,
            "total_records": len(records),
            "records_with_phone": sum(
                1 for record in records if record.get("phone")
            ),
            "records_without_phone": sum(
                1 for record in records if not record.get("phone")
            ),
        }

    df, header_row = read_upload(filename, content)
    result = analyze_dataframe(df, header_row)
    result["sheets"] = None
    result["selected_sheet"] = None
    return result


@router.post("/preview")
async def preview(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    filename = file.filename or "upload"
    content = await file.read()

    if is_excel_file(filename):
        sheets = get_excel_sheets(content)

        if sheet is not None:
            if sheet not in sheets:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Selected sheet does not exist.",
                        "available_sheets": sheets,
                    },
                )

            df, header_row = read_upload(filename, content, sheet)
            analysis = analyze_dataframe(df, header_row)
            validate_analysis(analysis)

            records = prepare_import(
                df,
                analysis["detected_mapping"],
                sheet,
            )

            duplicate_summary = find_duplicate_summary(
                db,
                records,
            )

            return {
                "file": filename,
                "sheet": sheet,
                "sheets": sheets,
                "mode": "single_sheet",
                "analysis": analysis,
                "summary": {
                    "rows_in_file": len(df),
                    "valid_records": len(records),
                    "records_with_phone": sum(
                        1 for record in records if record.get("phone")
                    ),
                    "records_without_phone": sum(
                        1 for record in records if not record.get("phone")
                    ),
                    **duplicate_summary,
                },
                "preview": records[:limit],
            }

        records, sheet_results = process_all_excel_sheets(content)
        duplicate_summary = find_duplicate_summary(db, records)

        return {
            "file": filename,
            "sheet": None,
            "sheets": sheets,
            "mode": "all_sheets",
            "sheet_results": sheet_results,
            "summary": {
                "rows_in_file": sum(
                    item.get("rows", 0) for item in sheet_results
                ),
                "valid_records": len(records),
                "records_with_phone": sum(
                    1 for record in records if record.get("phone")
                ),
                "records_without_phone": sum(
                    1 for record in records if not record.get("phone")
                ),
                **duplicate_summary,
            },
            "preview": records[:limit],
        }

    df, header_row = read_upload(filename, content)
    analysis = analyze_dataframe(df, header_row)
    validate_analysis(analysis)

    records = prepare_import(
        df,
        analysis["detected_mapping"],
    )

    duplicate_summary = find_duplicate_summary(db, records)

    return {
        "file": filename,
        "sheet": None,
        "sheets": None,
        "mode": "csv",
        "analysis": analysis,
        "summary": {
            "rows_in_file": len(df),
            "valid_records": len(records),
            "records_with_phone": sum(
                1 for record in records if record.get("phone")
            ),
            "records_without_phone": sum(
                1 for record in records if not record.get("phone")
            ),
            **duplicate_summary,
        },
        "preview": records[:limit],
    }


@router.post("/import")
async def import_file(
    file: UploadFile = File(...),
    sheet: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    filename = file.filename or "upload"
    content = await file.read()

    if is_excel_file(filename):
        sheets = get_excel_sheets(content)

        if sheet is not None:
            if sheet not in sheets:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Selected sheet does not exist.",
                        "available_sheets": sheets,
                    },
                )

            df, header_row = read_upload(filename, content, sheet)
            analysis = analyze_dataframe(df, header_row)
            validate_analysis(analysis)

            records = prepare_import(
                df,
                analysis["detected_mapping"],
                sheet,
            )

            if not records:
                raise HTTPException(
                    status_code=422,
                    detail="No valid customer records found.",
                )

            result = import_records(
                db,
                filename,
                filename.lower().rsplit(".", 1)[-1],
                records,
            )
            result["mode"] = "single_sheet"
            result["sheet"] = sheet
            return result

        records, sheet_results = process_all_excel_sheets(content)

        if not records:
            raise HTTPException(
                status_code=422,
                detail="No valid customer records found in any workbook sheet.",
            )

        result = import_records(
            db,
            filename,
            filename.lower().rsplit(".", 1)[-1],
            records,
        )

        result.update({
            "mode": "all_sheets",
            "sheets": sheets,
            "sheets_processed": sum(
                1
                for item in sheet_results
                if item.get("status") == "processed"
            ),
            "sheet_results": sheet_results,
            "customers_with_phone": sum(
                1 for record in records if record.get("phone")
            ),
            "customers_without_phone": sum(
                1 for record in records if not record.get("phone")
            ),
        })

        return result

    df, header_row = read_upload(filename, content)
    analysis = analyze_dataframe(df, header_row)
    validate_analysis(analysis)

    records = prepare_import(
        df,
        analysis["detected_mapping"],
    )

    if not records:
        raise HTTPException(
            status_code=422,
            detail="No valid customer records found.",
        )

    result = import_records(
        db,
        filename,
        filename.lower().rsplit(".", 1)[-1],
        records,
    )
    result["mode"] = "csv"
    return result