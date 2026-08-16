from __future__ import annotations

import csv
import re
from itertools import islice
from pathlib import Path
from time import monotonic
from typing import Any, Iterable, Iterator

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Customer, ImportBatch


MAX_WORKSHEET_ROWS = 50_000
MAX_COLUMNS = 80
MAX_HEADER_SCAN_ROWS = 30
MAX_SAMPLE_ROWS = 100
IMPORT_BATCH_SIZE = 250

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "customer name", "consumer name", "client name", "full name"),
    "phone": (
        "phone",
        "mobile",
        "mobile number",
        "contact",
        "contact no",
        "contact number",
        "phone number",
        "telephone",
    ),
    "email": ("email", "email address", "e mail"),
    "consumer_number": (
        "consumer number",
        "consumer no",
        "consumer id",
        "account number",
        "account no",
    ),
    "service": ("service", "product", "service name", "requirement", "trf desc"),
    "region": ("region", "region name"),
    "zone": ("zone", "zone name"),
    "circle": ("circle", "circle name"),
    "division": ("division", "division name"),
    "subdivision": ("subdivision", "sub division", "subdivision name"),
    "business_unit": ("bu", "business unit"),
}

EXACT_SOURCE_HEADINGS: dict[str, str] = {
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

ADDRESS_HEADINGS = {
    "address",
    "address 1",
    "address 2",
    "address 3",
    "address l1",
    "address l2",
    "address l3",
}

CUSTOMER_FIELDS = (
    "name",
    "phone",
    "email",
    "service",
    "consumer_number",
    "address",
    "region",
    "zone",
    "circle",
    "division",
    "subdivision",
    "business_unit",
)


def normalize_column(value: Any) -> str:
    """Normalize a source column name for reliable matching."""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_value(value: Any) -> str | None:
    """Convert spreadsheet values into clean strings."""
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat", "<na>"}:
        return None

    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]

    if re.fullmatch(r"0{8,}", re.sub(r"\s+", "", text)):
        return None

    return text


def normalize_phone(value: str | None) -> str | None:
    """Normalize Indian phone numbers while preserving existing behavior."""
    if not value:
        return None

    digits = re.sub(r"\D", "", value)

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 10 and digits[0] in "6789":
        return digits

    return None


def _bounded_rows(
    rows: Iterable[tuple[Any, ...]],
) -> Iterator[tuple[int, tuple[Any, ...]]]:
    """Yield rows lazily and enforce workbook safety limits."""
    for row_number, row in enumerate(rows, start=1):
        if row_number > MAX_WORKSHEET_ROWS:
            raise ValueError(
                f"Worksheet exceeds the {MAX_WORKSHEET_ROWS:,}-row safety limit."
            )

        yield row_number, tuple(row[:MAX_COLUMNS])


def workbook_sheets(path: Path) -> list[str]:
    """Return worksheet names without loading the workbook into normal memory."""
    workbook = None
    try:
        workbook = load_workbook(
            filename=path,
            read_only=True,
            data_only=True,
            keep_links=False,
        )
        return list(workbook.sheetnames)
    except Exception as exc:
        raise ValueError("Could not read XLSX workbook.") from exc
    finally:
        if workbook is not None:
            workbook.close()


def _xlsx_source(
    path: Path,
    sheet_name: str,
) -> tuple[Iterator[tuple[int, tuple[Any, ...]]], int | None]:
    """Create a streaming XLSX row iterator and expose max_row as an estimate."""
    workbook = None
    try:
        workbook = load_workbook(
            filename=path,
            read_only=True,
            data_only=True,
            keep_links=False,
        )

        if sheet_name not in workbook.sheetnames:
            workbook.close()
            raise ValueError("Selected sheet does not exist.")

        worksheet = workbook[sheet_name]
        max_row = worksheet.max_row

        def rows() -> Iterator[tuple[int, tuple[Any, ...]]]:
            try:
                yield from _bounded_rows(worksheet.iter_rows(values_only=True))
            except Exception as exc:
                raise ValueError("Could not parse XLSX worksheet.") from exc
            finally:
                workbook.close()

        return rows(), max_row
    except ValueError:
        raise
    except Exception as exc:
        if workbook is not None:
            workbook.close()
        raise ValueError("Could not parse XLSX worksheet.") from exc


def _sheet_rows(path: Path, sheet_name: str) -> Iterator[tuple[int, tuple[Any, ...]]]:
    """Stream XLSX rows without materializing the worksheet."""
    rows, _ = _xlsx_source(path, sheet_name)
    yield from rows


def _csv_rows(path: Path) -> Iterator[tuple[int, tuple[Any, ...]]]:
    """Stream UTF-8 CSV rows."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from _bounded_rows(csv.reader(handle))
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc
    except csv.Error as exc:
        raise ValueError("Could not parse CSV file.") from exc


def _header_score(row: tuple[Any, ...]) -> int:
    text = " | ".join(
        normalize_column(value) for value in row if clean_value(value)
    )

    keywords = (
        "consumer number",
        "consumer name",
        "customer name",
        "contact",
        "phone",
        "mobile",
        "email",
        "address",
    )

    score = sum(2 for keyword in keywords if keyword in text)
    score += 5 if "consumer number" in text else 0
    score += 5 if "consumer name" in text else 0
    return score


def _scan_source(
    path: Path,
    file_type: str,
    sheet_name: str | None,
) -> tuple[list[tuple[int, tuple[Any, ...]]], str | None, int | None]:
    """Read only the bounded header/sample area needed for analysis."""
    estimated_rows: int | None = None

    if file_type == "xlsx":
        if sheet_name is None:
            sheets = workbook_sheets(path)
            sheet_name = sheets[0] if sheets else None

        if not sheet_name:
            raise ValueError("Workbook contains no worksheets.")

        source, max_row = _xlsx_source(path, sheet_name)
        estimated_rows = max_row
    else:
        source = _csv_rows(path)

    scanned = list(
        islice(source, MAX_HEADER_SCAN_ROWS + MAX_SAMPLE_ROWS)
    )

    # CSV has no cheap row-count metadata, so leave total_rows unknown
    # instead of scanning the entire file during /analyze.
    return scanned, sheet_name, estimated_rows


def _headers_and_mapping(
    scanned: list[tuple[int, tuple[Any, ...]]],
) -> tuple[int, list[str], dict[str, Any]]:
    if not scanned:
        raise ValueError("The selected sheet is empty.")

    header_number, header_values = max(
        scanned[:MAX_HEADER_SCAN_ROWS],
        key=lambda item: _header_score(item[1]),
    )

    if not any(clean_value(value) for value in header_values):
        raise ValueError("The selected sheet is empty.")

    headers = [
        clean_value(value) or f"Unnamed: {index}"
        for index, value in enumerate(header_values)
    ]

    normalized = {
        header: normalize_column(header)
        for header in headers
    }

    mapping: dict[str, Any] = {}

    for field, aliases in FIELD_ALIASES.items():
        aliases_normalized = {normalize_column(alias) for alias in aliases}

        for header, normalized_header in normalized.items():
            if normalized_header in aliases_normalized:
                mapping[field] = header
                break

    for field, source in EXACT_SOURCE_HEADINGS.items():
        normalized_source = normalize_column(source)

        for header, normalized_header in normalized.items():
            if normalized_header == normalized_source:
                mapping[field] = header
                break

    address_columns = [
        header
        for header, normalized_header in normalized.items()
        if normalized_header in ADDRESS_HEADINGS
    ]

    if address_columns:
        mapping["address_columns"] = address_columns

    return header_number, headers, mapping


def analyze_file(
    path: Path,
    file_type: str,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Analyze only a small sample; do not scan a large XLSX unnecessarily."""
    scanned, selected_sheet, estimated_rows = _scan_source(
        path,
        file_type,
        sheet_name,
    )

    header_row, headers, mapping = _headers_and_mapping(scanned)

    sample_start = next(
        (
            index
            for index, item in enumerate(scanned)
            if item[0] == header_row
        ),
        len(scanned),
    )

    sample_rows = max(0, len(scanned) - sample_start - 1)

    # For XLSX, max_row is cheap metadata. For CSV, keep the value bounded
    # rather than performing a full file scan during /analyze.
    total_rows = (
        max(0, estimated_rows - header_row)
        if estimated_rows is not None
        else sample_rows
    )

    return {
        "total_rows": total_rows,
        "columns": headers,
        "header_row": header_row,
        "detected_mapping": mapping,
        "missing_required": [] if "name" in mapping else ["name"],
        "selected_sheet": selected_sheet,
    }


def iter_records(
    path: Path,
    file_type: str,
    sheet_name: str | None,
    mapping: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """Yield normalized customer records one row at a time."""
    if file_type == "xlsx":
        if not sheet_name:
            raise ValueError("A worksheet must be selected.")
        source: Iterable[tuple[int, tuple[Any, ...]]] = _sheet_rows(
            path,
            sheet_name,
        )
    else:
        source = _csv_rows(path)

    rows = iter(source)
    initial = list(islice(rows, MAX_HEADER_SCAN_ROWS))

    if not initial:
        return

    header_number, headers, _ = _headers_and_mapping(initial)

    header_index = next(
        index
        for index, item in enumerate(initial)
        if item[0] == header_number
    )

    def remaining_rows() -> Iterator[tuple[int, tuple[Any, ...]]]:
        yield from initial[header_index + 1 :]
        yield from rows

    for row_number, values in remaining_rows():
        row = {
            headers[index]: values[index] if index < len(values) else None
            for index in range(len(headers))
        }

        name = clean_value(row.get(mapping.get("name", "")))
        phone = clean_value(row.get(mapping.get("phone", "")))

        if not name and not phone:
            continue

        address_values = (
            clean_value(row.get(column))
            for column in mapping.get("address_columns", [])
        )
        address = ", ".join(dict.fromkeys(value for value in address_values if value))

        yield {
            "name": name or "Unknown",
            "phone": normalize_phone(phone),
            "email": clean_value(row.get(mapping.get("email", ""))),
            "service": clean_value(row.get(mapping.get("service", ""))),
            "consumer_number": clean_value(
                row.get(mapping.get("consumer_number", ""))
            ),
            "address": address or None,
            "region": clean_value(row.get(mapping.get("region", ""))),
            "zone": clean_value(row.get(mapping.get("zone", ""))),
            "circle": clean_value(row.get(mapping.get("circle", ""))),
            "division": clean_value(row.get(mapping.get("division", ""))),
            "subdivision": clean_value(
                row.get(mapping.get("subdivision", ""))
            ),
            "business_unit": clean_value(
                row.get(mapping.get("business_unit", ""))
            ),
            "source_row": row_number,
        }


def _load_by_consumer(
    db: Session,
    values: set[str],
) -> dict[str, Customer]:
    if not values:
        return {}

    statement = (
        select(Customer)
        .where(Customer.consumer_number.in_(values))
        .order_by(Customer.id)
    )

    return {
        customer.consumer_number: customer
        for customer in db.scalars(statement)
        if customer.consumer_number
    }


def _load_by_phone_name(
    db: Session,
    phones: set[str],
) -> dict[tuple[str, str], Customer]:
    if not phones:
        return {}

    statement = (
        select(Customer)
        .where(Customer.phone.in_(phones))
        .order_by(Customer.id)
    )

    return {
        (customer.phone, normalize_column(customer.name)): customer
        for customer in db.scalars(statement)
        if customer.phone
    }


def _has_updates(customer: Customer, record: dict[str, Any]) -> bool:
    return any(
        record.get(field) and getattr(customer, field) != record[field]
        for field in CUSTOMER_FIELDS
    )


def preview_records(
    db: Session,
    records: Iterable[dict[str, Any]],
    limit: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compatibility helper for callers that already provide records."""
    collected = list(islice(records, MAX_WORKSHEET_ROWS))

    consumers = {
        record["consumer_number"]
        for record in collected
        if record.get("consumer_number")
    }
    existing = _load_by_consumer(db, consumers)

    seen: set[str] = set()
    duplicates = existing_rows = updates = 0

    for record in collected:
        consumer = record.get("consumer_number")
        if not consumer:
            continue

        if consumer in seen:
            duplicates += 1
            continue

        seen.add(consumer)

        if consumer in existing:
            existing_rows += 1
            updates += int(_has_updates(existing[consumer], record))

    summary = {
        "duplicate_rows_in_file": duplicates,
        "already_in_database": existing_rows,
        "update_rows": updates,
        "new_records": max(
            0,
            len(collected) - duplicates - existing_rows,
        ),
    }

    return summary, collected[:limit]


def preview_file(
    db: Session,
    path: Path,
    file_type: str,
    sheet_name: str | None,
    mapping: dict[str, Any],
    limit: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Stream the file and keep only the bounded preview plus lookup keys.

    A second streaming pass is used for database comparison so the full
    workbook is never materialized in Python memory.
    """
    consumers: set[str] = set()
    fallback_phones: set[str] = set()
    seen_consumers: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()

    preview: list[dict[str, Any]] = []
    total = 0
    with_phone = 0
    duplicates = 0

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
            key = (
                record["phone"],
                normalize_column(record["name"]),
            )
            if key in seen_fallback:
                duplicates += 1
            seen_fallback.add(key)
            fallback_phones.add(record["phone"])

        if len(preview) < limit:
            preview.append(record)

    by_consumer = _load_by_consumer(db, consumers)
    by_fallback = _load_by_phone_name(db, fallback_phones)

    existing_rows = 0
    updates = 0
    counted_consumers: set[str] = set()
    counted_fallback: set[tuple[str, str]] = set()

    for record in iter_records(path, file_type, sheet_name, mapping):
        consumer = record.get("consumer_number")

        if consumer:
            if consumer in counted_consumers:
                continue

            counted_consumers.add(consumer)
            existing = by_consumer.get(consumer)
        elif record.get("phone"):
            key = (
                record["phone"],
                normalize_column(record["name"]),
            )

            if key in counted_fallback:
                continue

            counted_fallback.add(key)
            existing = by_fallback.get(key)
        else:
            continue

        if existing:
            existing_rows += 1
            updates += int(_has_updates(existing, record))

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


def import_record_batches(
    db: Session,
    filename: str,
    file_type: str,
    records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Import records in bounded transactions."""
    started = monotonic()

    import_batch = ImportBatch(
        filename=filename,
        file_type=file_type,
        total_rows=0,
        status="processing",
    )
    db.add(import_batch)
    db.commit()
    db.refresh(import_batch)

    imported = 0
    updated = 0
    duplicates = 0
    skipped = 0
    total = 0

    seen_consumers: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()
    pending: list[dict[str, Any]] = []

    try:
        for record in records:
            pending.append(record)

            if len(pending) >= IMPORT_BATCH_SIZE:
                counts = _import_batch(
                    db,
                    import_batch,
                    pending,
                    seen_consumers,
                    seen_fallback,
                )
                total += len(pending)
                imported += counts[0]
                updated += counts[1]
                duplicates += counts[2]
                skipped += counts[3]
                pending.clear()

        if pending:
            counts = _import_batch(
                db,
                import_batch,
                pending,
                seen_consumers,
                seen_fallback,
            )
            total += len(pending)
            imported += counts[0]
            updated += counts[1]
            duplicates += counts[2]
            skipped += counts[3]
            pending.clear()

        import_batch.total_rows = total
        import_batch.imported_rows = imported
        import_batch.duplicate_rows = duplicates
        import_batch.skipped_rows = skipped
        import_batch.status = "completed"

        db.commit()

    except Exception:
        db.rollback()

        # Use a fresh transaction to persist the failed import status.
        import_batch.status = "failed"
        db.add(import_batch)
        db.commit()
        raise

    return {
        "import_id": import_batch.id,
        "total_rows": total,
        "imported_rows": imported,
        "updated_rows": updated,
        "duplicate_rows": duplicates,
        "skipped_rows": skipped,
        "status": "completed",
        "processing_seconds": round(monotonic() - started, 3),
    }


def _import_batch(
    db: Session,
    import_batch: ImportBatch,
    records: list[dict[str, Any]],
    seen_consumers: set[str],
    seen_fallback: set[tuple[str, str]],
) -> tuple[int, int, int, int]:
    """Process one bounded database transaction."""
    consumers = {
        record["consumer_number"]
        for record in records
        if record.get("consumer_number")
    }

    fallback_phones = {
        record["phone"]
        for record in records
        if not record.get("consumer_number") and record.get("phone")
    }

    by_consumer = _load_by_consumer(db, consumers)
    by_fallback = _load_by_phone_name(db, fallback_phones)

    imported = 0
    updated = 0
    duplicates = 0
    skipped = 0

    try:
        for record in records:
            consumer = record.get("consumer_number")
            fallback_key = (
                record.get("phone") or "",
                normalize_column(record["name"]),
            )

            if consumer and consumer in seen_consumers:
                duplicates += 1
                continue

            if (
                not consumer
                and record.get("phone")
                and fallback_key in seen_fallback
            ):
                duplicates += 1
                continue

            existing = (
                by_consumer.get(consumer)
                if consumer
                else by_fallback.get(fallback_key)
                if record.get("phone")
                else None
            )

            if consumer:
                seen_consumers.add(consumer)
            elif record.get("phone"):
                seen_fallback.add(fallback_key)

            if existing:
                changed = False

                for field in CUSTOMER_FIELDS:
                    value = record.get(field)

                    if value and getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed = True

                if changed:
                    updated += 1
                else:
                    skipped += 1

                continue

            customer_values = {
                field: record.get(field)
                for field in CUSTOMER_FIELDS
            }

            customer = Customer(
                **customer_values,
                import_id=import_batch.id,
                source_file=import_batch.filename,
                source_row=record["source_row"],
            )

            db.add(customer)
            imported += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return imported, updated, duplicates, skipped
