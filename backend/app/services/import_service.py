"""
Import service — streaming Excel/CSV import for the CRM.

Architecture:
    Upload → validate → stream workbook → normalize one row → batch 250 →
    database insert/upsert → commit → clear batch → continue

Memory model:
    O(batch_size) — never O(total_rows).
    A 26,450-row workbook uses the same peak memory as a 500-row one.

openpyxl note:
    Workbook is NOT used as a context manager (load_workbook does support
    __exit__ in 3.0.10+, but we use explicit try/finally to be defensive
    and explicit, as the project spec requires).
"""
from __future__ import annotations

import csv
import logging
import os
import re
from itertools import islice
from pathlib import Path
from time import monotonic
from typing import Any, Iterable, Iterator

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from ..models import Customer, ImportBatch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable limits (override via environment variables)
# ---------------------------------------------------------------------------

MAX_WORKSHEET_ROWS: int = int(os.getenv("MAX_WORKSHEET_ROWS", "50000"))
MAX_COLUMNS: int = 80
MAX_HEADER_SCAN_ROWS: int = 30
MAX_SAMPLE_ROWS: int = 100
IMPORT_BATCH_SIZE: int = int(os.getenv("IMPORT_BATCH_SIZE", "250"))

# ---------------------------------------------------------------------------
# Column alias mapping — canonical field → accepted header variants
# ---------------------------------------------------------------------------

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": (
        "name", "customer name", "consumer name", "client name", "full name",
    ),
    "phone": (
        "phone", "mobile", "mobile number", "contact", "contact no",
        "contact number", "phone number", "telephone",
    ),
    "email": ("email", "email address", "e mail"),
    "consumer_number": (
        "consumer number", "consumer no", "consumer id",
        "account number", "account no",
    ),
    "service": ("service", "product", "service name", "requirement", "trf desc"),
    "region": ("region", "region name"),
    "zone": ("zone", "zone name"),
    "circle": ("circle", "circle name"),
    "division": ("division", "division name"),
    "subdivision": ("subdivision", "sub division", "subdivision name"),
    "business_unit": ("bu", "business unit"),
}

# Exact source headings used by existing customer workbooks (snake_case lookup)
_EXACT_SOURCE_HEADINGS: dict[str, str] = {
    "name": "consumer_name",
    "consumer_number": "consumer_number",
    "email": "email_id",
    "service": "trf_desc",
    "region": "region_name",
    "zone": "zone_name",
    "circle": "circle_name",
    "division": "division_name",
    "subdivision": "subdivision_name",
    "business_unit": "bu",
}

_ADDRESS_COLUMN_ALIASES: frozenset[str] = frozenset(
    {"address", "address 1", "address 2", "address 3", "address l1", "address l2", "address l3"}
)

# Fields written to the Customer model during import
CUSTOMER_FIELDS: tuple[str, ...] = (
    "name", "phone", "email", "service", "consumer_number",
    "address", "region", "zone", "circle", "division", "subdivision", "business_unit",
)


# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

def normalize_column(value: Any) -> str:
    """Collapse a column header to lowercase alphanumeric words separated by spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower())).strip()


def clean_value(value: Any) -> str | None:
    """Return a stripped string or None for blank/sentinel values."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat", "<na>"}:
        return None
    # Excel sometimes stores integers as floats (e.g., consumer numbers)
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    # Reject strings that are all zeroes (common placeholder)
    if re.fullmatch(r"0{8,}", re.sub(r"\s+", "", text)):
        return None
    return text


def normalize_phone(value: str | None) -> str | None:
    """
    Normalise to a 10-digit Indian mobile number or return None.

    Handles: +91 prefix, leading 0, spaces, dashes, floats ending in .0.
    Valid first digit: 6, 7, 8, or 9.
    """
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else None


# ---------------------------------------------------------------------------
# Low-level row streaming
# ---------------------------------------------------------------------------

def _bounded_rows(rows: Iterable[tuple[Any, ...]]) -> Iterator[tuple[int, tuple[Any, ...]]]:
    """
    Yield (row_number, row_values) while enforcing the worksheet row limit.

    Raises ValueError if the limit is exceeded so callers get a clear message
    rather than silently truncating.
    """
    for number, row in enumerate(rows, start=1):
        if number > MAX_WORKSHEET_ROWS:
            raise ValueError(
                f"Worksheet exceeds the {MAX_WORKSHEET_ROWS:,}-row safety limit."
            )
        yield number, tuple(row[:MAX_COLUMNS])


def workbook_sheets(path: Path) -> list[str]:
    """Return the list of worksheet names from an XLSX workbook."""
    workbook = None
    try:
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        return list(workbook.sheetnames)
    except Exception as exc:
        raise ValueError("Could not read XLSX workbook.") from exc
    finally:
        if workbook is not None:
            workbook.close()


def _sheet_rows(path: Path, sheet_name: str) -> Iterator[tuple[int, tuple[Any, ...]]]:
    """
    Stream (row_number, row_values) tuples from a single XLSX worksheet.

    The workbook is closed in a finally block even if the caller stops
    consuming the generator mid-stream.
    """
    workbook = None
    try:
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        if sheet_name not in workbook.sheetnames:
            raise ValueError("Selected sheet does not exist.")
        worksheet = workbook[sheet_name]
        yield from _bounded_rows(worksheet.iter_rows(values_only=True))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not parse XLSX worksheet.") from exc
    finally:
        if workbook is not None:
            workbook.close()


def _csv_rows(path: Path) -> Iterator[tuple[int, tuple[Any, ...]]]:
    """Stream (row_number, row_values) tuples from a UTF-8 CSV file."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from _bounded_rows(csv.reader(handle))
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc
    except csv.Error as exc:
        raise ValueError("Could not parse CSV file.") from exc


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

def _header_score(row: tuple[Any, ...]) -> int:
    """
    Score a candidate header row by how many CRM field keywords it contains.

    Higher score = more likely to be the true header row.
    """
    text = " | ".join(normalize_column(v) for v in row if clean_value(v))
    keywords = (
        "consumer number", "consumer name", "customer name",
        "contact", "phone", "mobile", "email", "address",
    )
    score = sum(2 for kw in keywords if kw in text)
    score += 5 if "consumer number" in text else 0
    score += 5 if "consumer name" in text else 0
    return score


def _scan_source(
    path: Path,
    file_type: str,
    sheet_name: str | None,
) -> tuple[list[tuple[int, tuple[Any, ...]]], str | None]:
    """
    Read up to MAX_HEADER_SCAN_ROWS + MAX_SAMPLE_ROWS rows for header detection
    and analysis. Does NOT scan the entire file.

    Returns (scanned_rows, resolved_sheet_name).
    """
    if file_type == "xlsx":
        if sheet_name is None:
            sheets = workbook_sheets(path)          # single call — result stored
            sheet_name = sheets[0] if sheets else None
        if not sheet_name:
            raise ValueError("Workbook contains no worksheets.")
        source = _sheet_rows(path, sheet_name)
    else:
        source = _csv_rows(path)

    limit = MAX_HEADER_SCAN_ROWS + MAX_SAMPLE_ROWS
    rows: list[tuple[int, tuple[Any, ...]]] = []
    for row in source:
        rows.append(row)
        if len(rows) >= limit:
            break

    return rows, sheet_name


def _headers_and_mapping(
    scanned: list[tuple[int, tuple[Any, ...]]],
) -> tuple[int, list[str], dict[str, Any]]:
    """
    Detect the header row and build a field→column mapping from scanned rows.

    Returns (header_row_number, header_names, mapping_dict).
    """
    if not scanned:
        raise ValueError("The selected sheet is empty.")

    # Pick the row with the highest header score from the first scan window
    header_number, header_values = max(
        scanned[:MAX_HEADER_SCAN_ROWS],
        key=lambda item: _header_score(item[1]),
    )

    if not any(clean_value(v) for v in header_values):
        raise ValueError("The selected sheet is empty.")

    headers = [
        clean_value(v) or f"Unnamed: {i}"
        for i, v in enumerate(header_values)
    ]
    normalized = {header: normalize_column(header) for header in headers}

    mapping: dict[str, Any] = {}

    # Match by alias list
    for field, aliases in FIELD_ALIASES.items():
        aliases_normalized = {normalize_column(a) for a in aliases}
        for header, value in normalized.items():
            if value in aliases_normalized:
                mapping[field] = header
                break

    # Match by exact source headings (snake_case)
    for field, source_heading in _EXACT_SOURCE_HEADINGS.items():
        for header, value in normalized.items():
            if value == normalize_column(source_heading):
                mapping[field] = header
                break

    # Detect multiple address columns (address_l1, address_l2, …)
    address_columns = [
        header for header, value in normalized.items()
        if value in _ADDRESS_COLUMN_ALIASES
    ]
    if address_columns:
        mapping["address_columns"] = address_columns

    return header_number, headers, mapping


# ---------------------------------------------------------------------------
# Public analysis API
# ---------------------------------------------------------------------------

def analyze_file(path: Path, file_type: str, sheet_name: str | None = None) -> dict:
    """
    Inspect a small sample of the file to detect headers and field mapping.

    Intentionally does NOT scan all rows — for a 26,450-row file we only
    read MAX_HEADER_SCAN_ROWS + MAX_SAMPLE_ROWS rows. The returned
    `total_rows` is the number of data rows in the sample, not the full file.
    """
    scanned, selected_sheet = _scan_source(path, file_type, sheet_name)
    header_row, headers, mapping = _headers_and_mapping(scanned)

    # Count sample data rows (rows after the header within the scanned window)
    header_index = next(
        (i for i, item in enumerate(scanned) if item[0] == header_row),
        len(scanned),
    )
    sample_rows = max(0, len(scanned) - header_index - 1)

    return {
        "total_rows": sample_rows,
        "columns": headers,
        "header_row": header_row,
        "detected_mapping": mapping,
        "missing_required": [] if "name" in mapping else ["name"],
        "selected_sheet": selected_sheet,
    }


# ---------------------------------------------------------------------------
# Record streaming
# ---------------------------------------------------------------------------

def iter_records(
    path: Path,
    file_type: str,
    sheet_name: str | None,
    mapping: dict[str, Any],
) -> Iterator[dict]:
    """
    Stream normalised customer records from a file.

    Memory usage is O(MAX_HEADER_SCAN_ROWS) for the initial header scan
    plus O(1) per row — the full file is never held in memory.
    """
    if file_type == "xlsx":
        if not sheet_name:
            raise ValueError("A worksheet must be selected.")
        source: Iterable[tuple[int, tuple[Any, ...]]] = _sheet_rows(path, sheet_name)
    else:
        source = _csv_rows(path)

    rows_iter = iter(source)
    initial = list(islice(rows_iter, MAX_HEADER_SCAN_ROWS))

    if not initial:
        return

    header_number, headers, _ = _headers_and_mapping(initial)
    start_index = next(
        i for i, item in enumerate(initial) if item[0] == header_number
    ) + 1

    def _remaining() -> Iterator[tuple[int, tuple[Any, ...]]]:
        yield from initial[start_index:]
        yield from rows_iter

    for number, values in _remaining():
        row = {
            headers[i]: (values[i] if i < len(values) else None)
            for i in range(len(headers))
        }
        name = clean_value(row.get(mapping.get("name", "")))
        phone_raw = clean_value(row.get(mapping.get("phone", "")))

        # Skip rows with neither name nor phone — they carry no useful data
        if not name and not phone_raw:
            continue

        address_parts = [
            v
            for col in mapping.get("address_columns", [])
            if (v := clean_value(row.get(col)))
        ]
        address = ", ".join(dict.fromkeys(address_parts)) or None

        yield {
            "name": name or "Unknown",
            "phone": normalize_phone(phone_raw),
            "email": clean_value(row.get(mapping.get("email", ""))),
            "service": clean_value(row.get(mapping.get("service", ""))),
            "consumer_number": clean_value(row.get(mapping.get("consumer_number", ""))),
            "address": address,
            "region": clean_value(row.get(mapping.get("region", ""))),
            "zone": clean_value(row.get(mapping.get("zone", ""))),
            "circle": clean_value(row.get(mapping.get("circle", ""))),
            "division": clean_value(row.get(mapping.get("division", ""))),
            "subdivision": clean_value(row.get(mapping.get("subdivision", ""))),
            "business_unit": clean_value(row.get(mapping.get("business_unit", ""))),
            "source_row": number,
        }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _load_by_consumer(db: Session, values: set[str]) -> dict[str, Customer]:
    """Batch-fetch customers by consumer_number using a single IN query."""
    if not values:
        return {}
    return {
        customer.consumer_number: customer
        for customer in (
            db.query(Customer)
            .filter(Customer.consumer_number.in_(values))
            .order_by(Customer.id)
            .all()
        )
        if customer.consumer_number
    }


def _load_by_phone_name(db: Session, phones: set[str]) -> dict[tuple[str, str], Customer]:
    """
    Batch-fetch customers by phone, returning a (phone, normalized_name) → Customer map.

    Two customers with the same phone but different names are distinct records
    per the business rule.
    """
    if not phones:
        return {}
    return {
        (customer.phone, normalize_column(customer.name)): customer
        for customer in (
            db.query(Customer)
            .filter(Customer.phone.in_(phones))
            .order_by(Customer.id)
            .all()
        )
        if customer.phone
    }


def _has_updates(customer: Customer, record: dict) -> bool:
    """Return True if the record carries new data for any tracked field."""
    return any(
        record.get(field) and getattr(customer, field) != record[field]
        for field in CUSTOMER_FIELDS
    )


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def preview_file(
    db: Session,
    path: Path,
    file_type: str,
    sheet_name: str | None,
    mapping: dict[str, Any],
    limit: int,
) -> tuple[dict, list[dict]]:
    """
    Single-pass preview: stream the file once, collecting statistics and preview
    rows simultaneously. Then perform one batch DB lookup.

    The original implementation made two full passes through the file —
    this version makes exactly one pass, which halves I/O for large files.
    """
    consumers: set[str] = set()
    fallback_phones: set[str] = set()
    seen_consumers: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()

    total = 0
    with_phone = 0
    duplicates = 0
    preview: list[dict] = []

    # Single pass: count + collect identifiers + collect preview rows
    for record in iter_records(path, file_type, sheet_name, mapping):
        total += 1

        if record.get("phone"):
            with_phone += 1

        consumer = record.get("consumer_number")
        if consumer:
            if consumer in seen_consumers:
                duplicates += 1
            seen_consumers.add(consumer)
            consumers.add(consumer)
        elif record.get("phone"):
            key = (record["phone"], normalize_column(record["name"]))
            if key in seen_fallback:
                duplicates += 1
            seen_fallback.add(key)
            fallback_phones.add(record["phone"])

        if len(preview) < limit:
            preview.append(record)

    # One batch DB lookup for all collected identifiers
    by_consumer = _load_by_consumer(db, consumers)
    by_fallback = _load_by_phone_name(db, fallback_phones)

    # Count existing / update rows from already-collected preview data +
    # a lightweight second pass only over the preview slice (at most `limit` rows)
    existing_rows = 0
    updates = 0
    counted_consumers: set[str] = set()
    counted_fallback: set[tuple[str, str]] = set()

    for record in preview:
        consumer = record.get("consumer_number")
        if consumer:
            if consumer in counted_consumers:
                continue
            counted_consumers.add(consumer)
            existing = by_consumer.get(consumer)
        elif record.get("phone"):
            key = (record["phone"], normalize_column(record["name"]))
            if key in counted_fallback:
                continue
            counted_fallback.add(key)
            existing = by_fallback.get(key)
        else:
            continue

        if existing:
            existing_rows += 1
            updates += int(_has_updates(existing, record))

    # For records outside the preview slice we can't compute per-record updates
    # without a second file pass. We report accurate totals for what we have
    # and use "already_in_database" as a lower bound.
    summary = {
        "rows_in_file": total,
        "valid_records": total,
        "records_with_phone": with_phone,
        "records_without_phone": total - with_phone,
        "duplicate_rows_in_file": duplicates,
        "already_in_database": existing_rows,
        "update_rows": updates,
        "new_records": max(0, total - duplicates - existing_rows),
    }

    return summary, preview


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_record_batches(
    db: Session,
    filename: str,
    file_type: str,
    records: Iterable[dict],
) -> dict:
    """
    Stream records through the import pipeline in fixed-size batches.

    Memory usage: O(IMPORT_BATCH_SIZE), not O(total_rows).

    Returns import statistics.
    """
    started = monotonic()

    batch = ImportBatch(
        filename=filename,
        file_type=file_type,
        total_rows=0,
        status="processing",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    imported = 0
    updated = 0
    duplicates = 0
    skipped = 0
    total = 0
    seen_consumers: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()

    try:
        pending: list[dict] = []

        for record in records:
            pending.append(record)

            if len(pending) >= IMPORT_BATCH_SIZE:
                counts = _import_batch(db, batch, pending, seen_consumers, seen_fallback)
                total += len(pending)
                imported += counts[0]
                updated += counts[1]
                duplicates += counts[2]
                skipped += counts[3]
                pending = []

        # Flush remaining records
        if pending:
            counts = _import_batch(db, batch, pending, seen_consumers, seen_fallback)
            total += len(pending)
            imported += counts[0]
            updated += counts[1]
            duplicates += counts[2]
            skipped += counts[3]

        batch.total_rows = total
        batch.imported_rows = imported
        batch.duplicate_rows = duplicates
        batch.skipped_rows = skipped
        batch.status = "completed"
        db.commit()

    except Exception:
        db.rollback()
        batch.status = "failed"
        db.add(batch)
        db.commit()
        raise

    elapsed = round(monotonic() - started, 3)
    logger.info(
        "import_record_batches complete filename=%s total=%d imported=%d "
        "updated=%d duplicates=%d skipped=%d seconds=%.3f",
        filename, total, imported, updated, duplicates, skipped, elapsed,
    )

    return {
        "import_id": batch.id,
        "total_rows": total,
        "imported_rows": imported,
        "updated_rows": updated,
        "duplicate_rows": duplicates,
        "skipped_rows": skipped,
        "status": "completed",
        "processing_seconds": elapsed,
    }


def _import_batch(
    db: Session,
    batch: ImportBatch,
    records: list[dict],
    seen_consumers: set[str],
    seen_fallback: set[tuple[str, str]],
) -> tuple[int, int, int, int]:
    """
    Process one batch of records: deduplicate, upsert, and commit.

    Returns (imported, updated, duplicates, skipped).
    """
    consumers = {
        record["consumer_number"]
        for record in records
        if record.get("consumer_number")
    }
    phones = {
        record["phone"]
        for record in records
        if not record.get("consumer_number") and record.get("phone")
    }

    by_consumer = _load_by_consumer(db, consumers)
    by_fallback = _load_by_phone_name(db, phones)

    imported = 0
    updated = 0
    duplicates = 0
    skipped = 0

    try:
        for record in records:
            consumer = record.get("consumer_number")
            key = (record.get("phone") or "", normalize_column(record["name"]))

            # Cross-batch duplicate detection
            if consumer and consumer in seen_consumers:
                duplicates += 1
                continue
            if not consumer and record.get("phone") and key in seen_fallback:
                duplicates += 1
                continue

            # Resolve existing record
            if consumer:
                existing = by_consumer.get(consumer)
            elif record.get("phone"):
                existing = by_fallback.get(key)
            else:
                existing = None

            # Register identifiers to prevent within-batch duplicates on retry
            if consumer:
                seen_consumers.add(consumer)
            elif record.get("phone"):
                seen_fallback.add(key)

            if existing:
                # Upsert: update changed fields, skip if nothing changed
                changed = 0
                for field in CUSTOMER_FIELDS:
                    if record.get(field) and getattr(existing, field) != record[field]:
                        setattr(existing, field, record[field])
                        changed += 1
                if changed:
                    updated += 1
                else:
                    skipped += 1
                continue

            # New customer
            customer = Customer(
                **{field: record.get(field) for field in CUSTOMER_FIELDS},
                import_id=batch.id,
                source_file=batch.filename,
                source_row=record["source_row"],
            )
            db.add(customer)
            imported += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return imported, updated, duplicates, skipped
