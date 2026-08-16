"""
Tests for the import service streaming pipeline.

Uses SQLite so no PostgreSQL connection is required.
"""
import os
import tempfile
from pathlib import Path

import pytest
from openpyxl import Workbook

# Must be set before importing any app module that uses database.py
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_crm.db")
os.environ.setdefault("CRM_AUTH_SECRET", "test-secret")

from app.services.import_service import (
    MAX_WORKSHEET_ROWS,
    _bounded_rows,
    analyze_file,
    iter_records,
    import_record_batches,
    workbook_sheets,
    preview_file,
)
from app.database import Base, SessionLocal, engine


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def workbook_file(rows, headers=("Consumer Name", "Contact No", "EMAIL_ID", "ADDRESS_L1")):
    """Create a temporary XLSX file with given headers and rows."""
    handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    handle.close()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Customers"
    sheet.append(list(headers))
    for row in rows:
        sheet.append(row)
    workbook.save(handle.name)
    workbook.close()
    return Path(handle.name)


# ---------------------------------------------------------------------------
# Streaming / analysis tests
# ---------------------------------------------------------------------------

def test_normal_xlsx_analyzes_and_streams_records():
    path = workbook_file([["Ada", "9876543210", "ada@example.com", "Main Street"]])
    try:
        analysis = analyze_file(path, "xlsx", "Customers")
        assert analysis["detected_mapping"]["name"] == "Consumer Name"
        records = list(iter_records(path, "xlsx", "Customers", analysis["detected_mapping"]))
        assert records[0]["name"] == "Ada"
        assert records[0]["phone"] == "9876543210"
    finally:
        path.unlink(missing_ok=True)


def test_empty_workbook_is_rejected():
    # A workbook with no rows at all raises ValueError("empty")
    handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    handle.close()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Customers"
    # Do NOT add any rows — leave it completely empty
    workbook.save(handle.name)
    workbook.close()
    path = Path(handle.name)
    try:
        with pytest.raises(ValueError, match="empty"):
            analyze_file(path, "xlsx", "Customers")
    finally:
        path.unlink(missing_ok=True)



def test_missing_headers_are_reported():
    path = workbook_file([["value"]], headers=("Unknown Column",))
    try:
        assert analyze_file(path, "xlsx", "Customers")["missing_required"] == ["name"]
    finally:
        path.unlink(missing_ok=True)


def test_invalid_workbook_is_rejected_without_parser_details():
    # A file with .xlsx extension but invalid (not a zip) content
    # In the new architecture, the error is raised when _sheet_rows
    # tries to open the worksheet (not at workbook_sheets level), so
    # the message is 'Could not parse XLSX worksheet.'
    path = Path(tempfile.mkstemp(suffix=".xlsx")[1])
    path.write_bytes(b"not an xlsx")
    try:
        with pytest.raises(ValueError, match="Could not (read|parse) XLSX"):
            analyze_file(path, "xlsx", "Customers")
    except PermissionError:
        # Windows may lock the temp file — skip the cleanup silently
        pass
    finally:
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass


def test_many_rows_are_streamed_with_no_dataframe():
    path = workbook_file([[f"Customer {i}", "9876543210", None, None] for i in range(1000)])
    try:
        analysis = analyze_file(path, "xlsx", "Customers")
        count = sum(1 for _ in iter_records(path, "xlsx", "Customers", analysis["detected_mapping"]))
        assert count == 1000
    finally:
        path.unlink(missing_ok=True)


def test_row_safety_limit_rejects_oversized_worksheet():
    with pytest.raises(ValueError, match="safety limit"):
        list(_bounded_rows((tuple() for _ in range(MAX_WORKSHEET_ROWS + 1))))


def test_malformed_cells_are_safely_cleaned():
    path = workbook_file([["  Ada  ", "+91-98765-43210", None, "000000000000"]])
    try:
        analysis = analyze_file(path, "xlsx", "Customers")
        record = next(iter_records(path, "xlsx", "Customers", analysis["detected_mapping"]))
        assert record["name"] == "Ada"
        assert record["phone"] == "9876543210"
        assert record["address"] is None
    finally:
        path.unlink(missing_ok=True)


def test_workbook_sheets_returns_list():
    """workbook_sheets must return a list and not leak the workbook handle."""
    path = workbook_file([["Ada", "9876543210", None, None]])
    try:
        sheets = workbook_sheets(path)
        assert isinstance(sheets, list)
        assert "Customers" in sheets
    finally:
        path.unlink(missing_ok=True)


def test_workbook_sheets_returns_list_for_second_call():
    """Calling workbook_sheets twice must not fail (workbook closed properly)."""
    path = workbook_file([["Ada", "9876543210", None, None]])
    try:
        sheets1 = workbook_sheets(path)
        sheets2 = workbook_sheets(path)
        assert sheets1 == sheets2
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Preview tests
# ---------------------------------------------------------------------------

def test_preview_file_single_pass():
    """preview_file must work and return a summary + preview rows."""
    path = workbook_file([
        ["Ada", "9876543210", "ada@example.com", "Street"],
        ["Bob", "8765432109", None, None],
    ])
    try:
        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            analysis = analyze_file(path, "xlsx", "Customers")
            summary, preview = preview_file(
                db, path, "xlsx", "Customers",
                analysis["detected_mapping"], limit=10
            )
            assert isinstance(summary, dict)
            assert len(preview) == 2
            assert summary["valid_records"] == 2
        finally:
            db.close()
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------

def test_duplicate_contacts_are_not_inserted_twice():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        result = import_record_batches(
            db,
            "duplicates.xlsx",
            "xlsx",
            iter((
                {
                    "name": "Ada", "phone": "9876543210", "email": None,
                    "service": None, "consumer_number": "C-1", "address": None,
                    "region": None, "zone": None, "circle": None,
                    "division": None, "subdivision": None, "business_unit": None,
                    "source_row": 2,
                },
                {
                    "name": "Ada Again", "phone": "9876543210", "email": None,
                    "service": None, "consumer_number": "C-1", "address": None,
                    "region": None, "zone": None, "circle": None,
                    "division": None, "subdivision": None, "business_unit": None,
                    "source_row": 3,
                },
            )),
        )
        assert result["imported_rows"] == 1
        assert result["duplicate_rows"] == 1
    finally:
        db.close()
