from __future__ import annotations

import csv
import os
import re
from itertools import islice
from pathlib import Path
from time import monotonic
from typing import Any, Iterable, Iterator

from openpyxl import load_workbook
from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from ..models import Customer, ImportBatch

MAX_WORKSHEET_ROWS = 50_000
MAX_COLUMNS = 80
MAX_HEADER_SCAN_ROWS = 30
MAX_SAMPLE_ROWS = 100
IMPORT_BATCH_SIZE = max(100, min(1_000, int(os.getenv("IMPORT_BATCH_SIZE", "500"))))

FIELD_ALIASES = {
    "name": ("name", "customer name", "consumer name", "client name", "full name"),
    "phone": ("phone", "mobile", "mobile number", "contact", "contact no", "contact number", "phone number", "telephone"),
    "email": ("email", "email address", "e mail"),
    "consumer_number": ("consumer number", "consumer no", "consumer id", "account number", "account no"),
    "service": ("service", "product", "service name", "requirement", "trf desc"),
    "region": ("region", "region name"),
    "zone": ("zone", "zone name"),
    "circle": ("circle", "circle name"),
    "division": ("division", "division name"),
    "subdivision": ("subdivision", "sub division", "subdivision name"),
    "business_unit": ("bu", "business unit"),
}
CUSTOMER_FIELDS = (
    "name", "phone", "email", "service", "consumer_number", "address", "region",
    "zone", "circle", "division", "subdivision", "business_unit",
)


def normalize_column(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower())).strip()


def clean_value(value: Any) -> str | None:
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
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else None


def _bounded_rows(rows: Iterable[tuple[Any, ...]]) -> Iterator[tuple[int, tuple[Any, ...]]]:
    for number, row in enumerate(rows, start=1):
        if number > MAX_WORKSHEET_ROWS:
            raise ValueError(f"Worksheet exceeds the {MAX_WORKSHEET_ROWS:,}-row safety limit.")
        yield number, tuple(row[:MAX_COLUMNS])


def workbook_sheets(path: Path) -> list[str]:
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
    workbook = None
    try:
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        if sheet_name not in workbook.sheetnames:
            raise ValueError("Selected sheet does not exist.")
        yield from _bounded_rows(workbook[sheet_name].iter_rows(values_only=True))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not parse XLSX worksheet.") from exc
    finally:
        if workbook is not None:
            workbook.close()


def _csv_rows(path: Path) -> Iterator[tuple[int, tuple[Any, ...]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from _bounded_rows(csv.reader(handle))
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc
    except csv.Error as exc:
        raise ValueError("Could not parse CSV file.") from exc


def _header_score(row: tuple[Any, ...]) -> int:
    text = " | ".join(normalize_column(value) for value in row if clean_value(value))
    keywords = ("consumer number", "consumer name", "customer name", "contact", "phone", "mobile", "email", "address")
    return sum(2 for item in keywords if item in text) + (5 if "consumer number" in text else 0) + (5 if "consumer name" in text else 0)


def _scan_source(path: Path, file_type: str, sheet_name: str | None) -> tuple[list[tuple[int, tuple[Any, ...]]], str | None]:
    if file_type == "xlsx":
        if sheet_name is None:
            sheets = workbook_sheets(path)
            sheet_name = sheets[0] if sheets else None
        if not sheet_name:
            raise ValueError("Workbook contains no worksheets.")
        source = _sheet_rows(path, sheet_name)
    else:
        source = _csv_rows(path)
    return list(islice(source, MAX_HEADER_SCAN_ROWS + MAX_SAMPLE_ROWS)), sheet_name


def _headers_and_mapping(scanned: list[tuple[int, tuple[Any, ...]]]) -> tuple[int, list[str], dict[str, Any]]:
    if not scanned:
        raise ValueError("The selected sheet is empty.")
    header_number, header_values = max(scanned[:MAX_HEADER_SCAN_ROWS], key=lambda item: _header_score(item[1]))
    if not any(clean_value(value) for value in header_values):
        raise ValueError("The selected sheet is empty.")
    headers = [clean_value(value) or f"Unnamed: {index}" for index, value in enumerate(header_values)]
    normalized = {header: normalize_column(header) for header in headers}
    mapping: dict[str, Any] = {}
    for field, aliases in FIELD_ALIASES.items():
        aliases_normalized = {normalize_column(alias) for alias in aliases}
        for header, value in normalized.items():
            if value in aliases_normalized:
                mapping[field] = header
                break
    for field, source in {
        "name": "consumer_name", "consumer_number": "consumer_number", "email": "email_id",
        "service": "trf_desc", "region": "region_name", "zone": "zone_name",
        "circle": "circle_name", "division": "division_name", "subdivision": "subdivision_name",
        "business_unit": "bu",
    }.items():
        for header, value in normalized.items():
            if value == normalize_column(source):
                mapping[field] = header
                break
    address_columns = [header for header, value in normalized.items() if value in {"address", "address 1", "address 2", "address 3", "address l1", "address l2", "address l3"}]
    if address_columns:
        mapping["address_columns"] = address_columns
    return header_number, headers, mapping


def analyze_file(path: Path, file_type: str, sheet_name: str | None = None) -> dict:
    scanned, selected_sheet = _scan_source(path, file_type, sheet_name)
    header_row, headers, mapping = _headers_and_mapping(scanned)
    sample_rows = max(0, len(scanned) - next(index for index, item in enumerate(scanned) if item[0] == header_row) - 1)
    return {
        "total_rows": sample_rows,
        "columns": headers,
        "header_row": header_row,
        "detected_mapping": mapping,
        "missing_required": [] if "name" in mapping else ["name"],
        "selected_sheet": selected_sheet,
        "sample_rows": sample_rows,
    }


def iter_records(path: Path, file_type: str, sheet_name: str | None, mapping: dict[str, Any]) -> Iterator[dict[str, Any]]:
    source: Iterable[tuple[int, tuple[Any, ...]]]
    if file_type == "xlsx":
        if not sheet_name:
            raise ValueError("A worksheet must be selected.")
        source = _sheet_rows(path, sheet_name)
    else:
        source = _csv_rows(path)
    rows = iter(source)
    initial = list(islice(rows, MAX_HEADER_SCAN_ROWS))
    if not initial:
        return
    header_number, headers, _ = _headers_and_mapping(initial)
    start_index = next(index for index, item in enumerate(initial) if item[0] == header_number) + 1
    for number, values in (*initial[start_index:], *()):
        yield from _record_from_values(number, values, headers, mapping)
    for number, values in rows:
        yield from _record_from_values(number, values, headers, mapping)


def _record_from_values(number: int, values: tuple[Any, ...], headers: list[str], mapping: dict[str, Any]) -> Iterator[dict[str, Any]]:
    row = {headers[index]: values[index] if index < len(values) else None for index in range(len(headers))}
    name = clean_value(row.get(mapping.get("name", "")))
    phone = clean_value(row.get(mapping.get("phone", "")))
    if not name and not phone:
        return
    address = ", ".join(dict.fromkeys(value for column in mapping.get("address_columns", []) if (value := clean_value(row.get(column))))) or None
    yield {
        "name": name or "Unknown", "phone": normalize_phone(phone),
        "email": clean_value(row.get(mapping.get("email", ""))),
        "service": clean_value(row.get(mapping.get("service", ""))),
        "consumer_number": clean_value(row.get(mapping.get("consumer_number", ""))),
        "address": address, "region": clean_value(row.get(mapping.get("region", ""))),
        "zone": clean_value(row.get(mapping.get("zone", ""))), "circle": clean_value(row.get(mapping.get("circle", ""))),
        "division": clean_value(row.get(mapping.get("division", ""))),
        "subdivision": clean_value(row.get(mapping.get("subdivision", ""))),
        "business_unit": clean_value(row.get(mapping.get("business_unit", ""))), "source_row": number,
    }


def _load_by_consumer(db: Session, values: set[str]) -> dict[str, Customer]:
    if not values:
        return {}
    return {customer.consumer_number: customer for customer in db.query(Customer).filter(Customer.consumer_number.in_(values)).all() if customer.consumer_number}


def _load_by_phone_name(db: Session, phones: set[str]) -> dict[tuple[str, str], Customer]:
    if not phones:
        return {}
    return {(customer.phone, normalize_column(customer.name)): customer for customer in db.query(Customer).filter(Customer.phone.in_(phones)).all() if customer.phone}


def _has_updates(customer: Customer, record: dict[str, Any]) -> bool:
    return any(record.get(field) and getattr(customer, field) != record[field] for field in CUSTOMER_FIELDS)


def preview_file(db: Session, path: Path, file_type: str, sheet_name: str | None, mapping: dict[str, Any], limit: int) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Preview only the requested bounded sample; never scan the full workbook."""
    preview = list(islice(iter_records(path, file_type, sheet_name, mapping), limit))
    consumers = {record["consumer_number"] for record in preview if record.get("consumer_number")}
    phones = {record["phone"] for record in preview if not record.get("consumer_number") and record.get("phone")}
    by_consumer = _load_by_consumer(db, consumers)
    by_phone_name = _load_by_phone_name(db, phones)
    seen_consumers: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()
    duplicates = existing_rows = updates = with_phone = 0
    for record in preview:
        consumer = record.get("consumer_number")
        key = (record.get("phone") or "", normalize_column(record["name"]))
        if record.get("phone"):
            with_phone += 1
        if consumer:
            if consumer in seen_consumers:
                duplicates += 1
                continue
            seen_consumers.add(consumer)
            existing = by_consumer.get(consumer)
        elif record.get("phone"):
            if key in seen_fallback:
                duplicates += 1
                continue
            seen_fallback.add(key)
            existing = by_phone_name.get(key)
        else:
            existing = None
        if existing:
            existing_rows += 1
            updates += int(_has_updates(existing, record))
    total = len(preview)
    return {
        "rows_in_file": total, "valid_records": total, "records_with_phone": with_phone,
        "records_without_phone": total - with_phone, "duplicate_rows_in_file": duplicates,
        "already_in_database": existing_rows, "update_rows": updates,
        "new_records": max(0, total - duplicates - existing_rows), "sampled_rows": total,
    }, preview


def import_record_batches(db: Session, filename: str, file_type: str, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    started = monotonic()
    batch = ImportBatch(filename=filename, file_type=file_type, total_rows=0, status="processing")
    db.add(batch)
    db.commit()
    batch_id = batch.id
    imported = updated = duplicates = skipped = total = 0
    try:
        pending: list[dict[str, Any]] = []
        for record in records:
            pending.append(record)
            if len(pending) >= IMPORT_BATCH_SIZE:
                counts = _import_batch(db, batch_id, filename, pending)
                total += len(pending); imported += counts[0]; updated += counts[1]; duplicates += counts[2]; skipped += counts[3]
                pending.clear()
        if pending:
            counts = _import_batch(db, batch_id, filename, pending)
            total += len(pending); imported += counts[0]; updated += counts[1]; duplicates += counts[2]; skipped += counts[3]
        db.execute(update(ImportBatch).where(ImportBatch.id == batch_id).values(total_rows=total, imported_rows=imported, duplicate_rows=duplicates, skipped_rows=skipped, status="completed"))
        db.commit()
    except Exception:
        db.rollback()
        db.execute(update(ImportBatch).where(ImportBatch.id == batch_id).values(status="failed"))
        db.commit()
        raise
    return {"import_id": batch_id, "total_rows": total, "imported_rows": imported, "updated_rows": updated, "duplicate_rows": duplicates, "skipped_rows": skipped, "status": "completed", "processing_seconds": round(monotonic() - started, 3)}


def _import_batch(db: Session, batch_id: int, filename: str, records: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    consumers = {record["consumer_number"] for record in records if record.get("consumer_number")}
    phones = {record["phone"] for record in records if not record.get("consumer_number") and record.get("phone")}
    by_consumer = _load_by_consumer(db, consumers)
    by_phone_name = _load_by_phone_name(db, phones)
    seen_consumers: set[str] = set()
    seen_fallback: set[tuple[str, str]] = set()
    inserts: list[dict[str, Any]] = []
    imported = updated = duplicates = skipped = 0
    try:
        for record in records:
            consumer = record.get("consumer_number")
            key = (record.get("phone") or "", normalize_column(record["name"]))
            if consumer and consumer in seen_consumers:
                duplicates += 1
                continue
            if not consumer and record.get("phone") and key in seen_fallback:
                duplicates += 1
                continue
            if consumer:
                seen_consumers.add(consumer)
                existing = by_consumer.get(consumer)
            elif record.get("phone"):
                seen_fallback.add(key)
                existing = by_phone_name.get(key)
            else:
                existing = None
            if existing:
                changed = False
                for field in CUSTOMER_FIELDS:
                    if record.get(field) and getattr(existing, field) != record[field]:
                        setattr(existing, field, record[field])
                        changed = True
                updated += int(changed)
                skipped += int(not changed)
                continue
            inserts.append({**{field: record.get(field) for field in CUSTOMER_FIELDS}, "import_id": batch_id, "source_file": filename, "source_row": record["source_row"]})
        if inserts:
            db.execute(insert(Customer), inserts)
            imported = len(inserts)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return imported, updated, duplicates, skipped
