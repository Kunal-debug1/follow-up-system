from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from ..models import Customer, ImportBatch


# ============================================================
# COLUMN MAPPING
# ============================================================

FIELD_ALIASES: dict[str, list[str]] = {
    "name": [
        "name",
        "customer name",
        "customer_name",
        "consumer name",
        "consumer_name",
        "client name",
        "full name",
    ],
    "phone": [
        "phone",
        "mobile",
        "mobile number",
        "contact",
        "contact no",
        "contact number",
        "contact_no",
        "phone number",
        "telephone",
    ],
    "email": [
        "email",
        "email address",
        "e-mail",
        "email_id",
    ],
    "consumer_number": [
        "consumer number",
        "consumer_number",
        "consumer no",
        "consumer id",
        "account number",
        "account no",
    ],
    "service": [
        "service",
        "product",
        "service name",
    ],
    "region": [
        "region",
        "region name",
        "region_name",
    ],
    "zone": [
        "zone",
        "zone name",
        "zone_name",
    ],
    "circle": [
        "circle",
        "circle name",
        "circle_name",
    ],
    "division": [
        "division",
        "division name",
        "division_name",
    ],
    "subdivision": [
        "subdivision",
        "sub division",
        "subdivision name",
        "subdivision_name",
    ],
    "business_unit": [
        "bu",
        "business unit",
        "business_unit",
    ],
}


# ============================================================
# BASIC CLEANING
# ============================================================

def normalize_column(value: Any) -> str:
    """
    Convert a column name into a predictable comparison format.

    Example:
        "Consumer_Number" -> "consumer number"
        "EMAIL_ID"       -> "email id"
    """
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_value(value: Any) -> str | None:
    """
    Convert Excel/Pandas values into clean strings.

    Handles:
    - NaN
    - None
    - empty strings
    - Excel numeric values ending in .0
    - meaningless zero placeholders
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip()

    if not text:
        return None

    if text.lower() in {
        "nan",
        "none",
        "null",
        "nat",
        "<na>",
    }:
        return None

    # Excel may convert values such as 12345 into "12345.0".
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]

    # Ignore meaningless address placeholders like:
    # 000000000000000000000000
    compact = re.sub(r"\s+", "", text)

    if re.fullmatch(r"0{8,}", compact):
        return None

    return text


# ============================================================
# HEADER DETECTION
# ============================================================

def find_header_row(
    raw: pd.DataFrame,
    max_rows: int = 30,
) -> int:
    """
    Automatically detect the Excel header row.

    This is important because the source workbook can have
    title/information rows before the actual table header.
    """

    best_row = 0
    best_score = -1

    keywords = [
        "consumer number",
        "consumer name",
        "contact",
        "phone",
        "mobile",
        "region name",
        "zone name",
        "division name",
        "email",
        "address",
    ]

    rows_to_check = min(max_rows, len(raw))

    for row_index in range(rows_to_check):
        values = [
            normalize_column(value)
            for value in raw.iloc[row_index].tolist()
            if pd.notna(value)
        ]

        if not values:
            continue

        joined = " | ".join(values)

        score = sum(
            2
            for keyword in keywords
            if keyword in joined
        )

        # Strong indicators.
        if "consumer number" in joined:
            score += 5

        if "consumer name" in joined:
            score += 5

        if score > best_score:
            best_score = score
            best_row = row_index

    return best_row


# ============================================================
# FILE LOADERS
# ============================================================

def load_excel_sheet(
    content: bytes,
    sheet_name: str | int = 0,
) -> tuple[pd.DataFrame, int]:
    """
    Load an Excel sheet and automatically detect its header row.
    """

    raw = pd.read_excel(
        BytesIO(content),
        sheet_name=sheet_name,
        header=None,
        dtype=str,
    )

    if raw.empty:
        raise ValueError("The selected Excel sheet is empty.")

    header_row = find_header_row(raw)

    headers: list[str] = []

    for index, value in enumerate(
        raw.iloc[header_row].tolist()
    ):
        header = clean_value(value)

        if header:
            headers.append(header)
        else:
            headers.append(f"Unnamed: {index}")

    df = raw.iloc[header_row + 1:].copy()

    df.columns = headers

    # Preserve the original Excel row number.
    df["_source_excel_row"] = range(
        header_row + 2,
        header_row + 2 + len(df),
    )

    # Remove completely empty rows.
    df = (
        df
        .dropna(how="all")
        .reset_index(drop=True)
    )

    return df, header_row


def load_csv(
    content: bytes,
) -> tuple[pd.DataFrame, int]:
    """
    Load CSV data.
    """

    df = pd.read_csv(
        BytesIO(content),
        dtype=str,
    )

    df["_source_excel_row"] = range(
        2,
        2 + len(df),
    )

    return df, 0


# ============================================================
# COLUMN DETECTION
# ============================================================

def detect_columns(
    columns: list[str],
    df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Automatically map source columns to CRM fields.
    """

    normalized_columns = {
        column: normalize_column(column)
        for column in columns
    }

    detected: dict[str, Any] = {}

    # --------------------------------------------------------
    # Standard aliases
    # --------------------------------------------------------

    for field, aliases in FIELD_ALIASES.items():
        alias_set = {
            normalize_column(alias)
            for alias in aliases
        }

        for original, normalized in normalized_columns.items():
            if normalized in alias_set:
                detected[field] = original
                break

    # --------------------------------------------------------
    # Exact source-file overrides
    # --------------------------------------------------------

    overrides = {
        "name": ["consumer_name"],
        "consumer_number": ["consumer_number"],
        "region": ["region_name"],
        "zone": ["zone_name"],
        "circle": ["circle_name"],
        "division": ["division_name"],
        "subdivision": ["subdivision_name"],
        "business_unit": ["bu"],
        "email": ["email_id"],
    }

    for field, candidates in overrides.items():
        candidate_set = {
            normalize_column(candidate)
            for candidate in candidates
        }

        for original in columns:
            if normalize_column(original) in candidate_set:
                detected[field] = original
                break

    # --------------------------------------------------------
    # Detect blank-header phone column.
    #
    # Your Excel file contains a phone column represented by
    # something similar to "Unnamed: 11".
    #
    # We inspect the values instead of relying on the header.
    # --------------------------------------------------------

    if "phone" not in detected and df is not None:
        for original in columns:

            normalized = normalize_column(original)

            if not normalized.startswith("unnamed"):
                continue

            sample = (
                df[original]
                .dropna()
                .astype(str)
                .str.strip()
                .head(200)
            )

            if len(sample) < 5:
                continue

            digits = sample.str.replace(
                r"\D",
                "",
                regex=True,
            )

            valid_ratio = (
                (digits.str.len() == 10).mean()
            )

            if valid_ratio >= 0.60:
                detected["phone"] = original
                break

    # --------------------------------------------------------
    # Address columns
    # --------------------------------------------------------

    address_names = {
        "address",
        "address 1",
        "address 2",
        "address 3",
        "address l1",
        "address l2",
        "address l3",
    }

    address_columns = [
        column
        for column in columns
        if normalize_column(column) in address_names
    ]

    if address_columns:
        detected["address_columns"] = address_columns

    return detected


# ============================================================
# ANALYSIS
# ============================================================

def analyze_dataframe(
    df: pd.DataFrame,
    header_row: int = 0,
) -> dict:
    """
    Analyze an imported dataframe and return the detected
    CRM column mapping.
    """

    columns = [
        str(column)
        for column in df.columns
        if str(column) != "_source_excel_row"
    ]

    mapping = detect_columns(
        columns,
        df,
    )

    return {
        "total_rows": int(len(df)),
        "columns": columns,
        "header_row": header_row + 1,
        "detected_mapping": mapping,
        "missing_required": (
            []
            if "name" in mapping
            else ["name"]
        ),
    }


# ============================================================
# ADDRESS
# ============================================================

def build_address(
    row: pd.Series,
    mapping: dict[str, Any],
) -> str | None:
    """
    Combine address columns into one clean address.
    """

    parts: list[str] = []

    # Single address column.
    address_column = mapping.get("address")

    if address_column:
        value = clean_value(
            row.get(address_column)
        )

        if value:
            parts.append(value)

    # Multiple address columns.
    for column in mapping.get(
        "address_columns",
        [],
    ):
        value = clean_value(
            row.get(column)
        )

        if value and value not in parts:
            parts.append(value)

    return (
        ", ".join(parts)
        if parts
        else None
    )


# ============================================================
# PHONE
# ============================================================

def normalize_phone(
    value: str | None,
) -> str | None:
    """
    Normalize Indian mobile numbers.

    Supported:
        9423149619
        +919423149619
        919423149619
        09423149619

    Returns:
        A clean 10-digit mobile number, or None.
    """
    if not value:
        return None

    digits = re.sub(r"\D", "", str(value))

    if not digits:
        return None

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 10 and digits[0] in "6789":
        return digits

    return None


# ============================================================
# RECORD PREPARATION
# ============================================================

def prepare_import(
    df: pd.DataFrame,
    mapping: dict[str, Any],
    sheet_name: str | None = None,
) -> list[dict]:
    """
    Convert dataframe rows into CRM customer records.
    """

    records: list[dict] = []

    for index, (_, row) in enumerate(
        df.iterrows(),
        start=0,
    ):

        name = (
            clean_value(
                row.get(mapping["name"])
            )
            if mapping.get("name")
            else None
        )

        phone = (
            clean_value(
                row.get(mapping["phone"])
            )
            if mapping.get("phone")
            else None
        )

        email = (
            clean_value(
                row.get(mapping["email"])
            )
            if mapping.get("email")
            else None
        )

        # Ignore completely unusable rows.
        if not name and not phone:
            continue

        source_row = row.get(
            "_source_excel_row"
        )

        try:
            if pd.isna(source_row):
                source_row = index + 2
        except (TypeError, ValueError):
            source_row = index + 2

        record = {
            "name": name or "Unknown",
            "phone": normalize_phone(phone),
            "email": email,

            "service": (
                clean_value(
                    row.get(mapping["service"])
                )
                if mapping.get("service")
                else None
            ),

            "consumer_number": (
                clean_value(
                    row.get(
                        mapping["consumer_number"]
                    )
                )
                if mapping.get("consumer_number")
                else None
            ),

            "address": build_address(
                row,
                mapping,
            ),

            "region": (
                clean_value(
                    row.get(mapping["region"])
                )
                if mapping.get("region")
                else None
            ),

            "zone": (
                clean_value(
                    row.get(mapping["zone"])
                )
                if mapping.get("zone")
                else None
            ),

            "circle": (
                clean_value(
                    row.get(mapping["circle"])
                )
                if mapping.get("circle")
                else None
            ),

            "division": (
                clean_value(
                    row.get(mapping["division"])
                )
                if mapping.get("division")
                else None
            ),

            "subdivision": (
                clean_value(
                    row.get(
                        mapping["subdivision"]
                    )
                )
                if mapping.get("subdivision")
                else None
            ),

            "business_unit": (
                clean_value(
                    row.get(
                        mapping["business_unit"]
                    )
                )
                if mapping.get("business_unit")
                else None
            ),

            "source_row": int(source_row),
        }

        records.append(record)

    return records


# ============================================================
# DUPLICATE / UPDATE PREVIEW
# ============================================================

def load_customers_by_consumer_number(
    db: Session,
    consumer_numbers: set[str],
) -> dict[str, Customer]:
    """Load each matching customer once, keyed by consumer number."""
    if not consumer_numbers:
        return {}

    customers: dict[str, Customer] = {}

    for customer in (
        db.query(Customer)
        .filter(Customer.consumer_number.in_(consumer_numbers))
        .order_by(Customer.id.asc())
        .all()
    ):
        if customer.consumer_number:
            customers.setdefault(customer.consumer_number, customer)

    return customers


def load_customers_by_phone_and_name(
    db: Session,
    phones: set[str],
) -> dict[tuple[str, str], Customer]:
    """Load possible fallback matches once, preserving first-match behavior."""
    if not phones:
        return {}

    customers: dict[tuple[str, str], Customer] = {}

    for customer in (
        db.query(Customer)
        .filter(Customer.phone.in_(phones))
        .order_by(Customer.id.asc())
        .all()
    ):
        if customer.phone:
            customers.setdefault(
                (customer.phone, normalize_column(customer.name)),
                customer,
            )

    return customers


def refresh_fallback_customer(
    customers_by_fallback: dict[tuple[str, str], Customer],
    customer: Customer,
    previous_key: tuple[str, str] | None = None,
) -> None:
    """Keep the in-memory fallback lookup consistent with current changes."""
    if previous_key and customers_by_fallback.get(previous_key) is customer:
        customers_by_fallback.pop(previous_key)

    if customer.phone:
        customers_by_fallback.setdefault(
            (customer.phone, normalize_column(customer.name)),
            customer,
        )


def find_duplicate_summary(
    db: Session,
    records: list[dict],
) -> dict:
    """
    Calculate import statistics before importing.

    Primary key:
        consumer_number

    Fallback:
        phone + normalized name

    Phone numbers alone are NOT treated as duplicates.
    """

    consumer_values = {
        record["consumer_number"]
        for record in records
        if record.get("consumer_number")
    }

    customers_by_consumer = load_customers_by_consumer_number(
        db,
        consumer_values,
    )

    seen_consumers: set[str] = set()

    duplicate_rows = 0
    existing_rows = 0
    update_rows = 0

    # --------------------------------------------------------
    # Records with consumer numbers
    # --------------------------------------------------------

    for record in records:

        consumer = record.get(
            "consumer_number"
        )

        if not consumer:
            continue

        if consumer in seen_consumers:
            duplicate_rows += 1
            continue

        seen_consumers.add(consumer)

        existing = customers_by_consumer.get(consumer)

        if not existing:
            continue

        existing_rows += 1

        if has_customer_updates(
            existing,
            record,
        ):
            update_rows += 1

    # --------------------------------------------------------
    # Records without consumer numbers
    # --------------------------------------------------------

    seen_fallback: set[
        tuple[str, str]
    ] = set()

    for record in records:

        if record.get("consumer_number"):
            continue

        phone = record.get("phone")

        if not phone:
            continue

        name_key = normalize_column(
            record.get("name", "")
        )

        fallback_key = (
            phone,
            name_key,
        )

        if fallback_key in seen_fallback:
            duplicate_rows += 1
            continue

        seen_fallback.add(fallback_key)

    return {
        "duplicate_rows_in_file": duplicate_rows,
        "already_in_database": existing_rows,
        "update_rows": update_rows,
        "new_records": max(
            0,
            len(records)
            - duplicate_rows
            - existing_rows,
        ),
    }


# ============================================================
# UPDATE HELPERS
# ============================================================

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


def has_customer_updates(
    customer: Customer,
    record: dict,
) -> bool:
    """
    Return True when the Excel record contains a useful value
    that differs from the existing customer.

    Empty Excel values are ignored and never erase CRM data.
    """
    for field in CUSTOMER_FIELDS:
        incoming = record.get(field)

        if not incoming:
            continue

        existing = getattr(customer, field, None)

        if existing != incoming:
            return True

    return False


def update_customer_fields(
    customer: Customer,
    record: dict,
) -> int:
    """
    Synchronize useful Excel values into an existing customer.

    Rules:
    - Empty/None Excel values never overwrite CRM data.
    - Non-empty Excel values update the field when different.
    """
    changed = 0

    for field in CUSTOMER_FIELDS:
        incoming = record.get(field)

        if not incoming:
            continue

        existing = getattr(customer, field, None)

        if existing == incoming:
            continue

        setattr(customer, field, incoming)
        changed += 1

    return changed



# ============================================================
# MULTI-SHEET MERGING
# ============================================================

def merge_records(records: list[dict]) -> list[dict]:
    """
    Merge records originating from multiple Excel sheets.

    Primary match:
        consumer_number

    Fallback:
        phone + normalized name

    Existing non-empty values are preserved.
    Missing fields are filled from duplicate records.
    """

    by_consumer: dict[str, dict] = {}
    by_fallback: dict[tuple[str, str], dict] = {}

    for record in records:
        consumer = record.get("consumer_number")

        if consumer:
            key = str(consumer).strip()

            if key not in by_consumer:
                by_consumer[key] = dict(record)
                continue

            existing = by_consumer[key]

            for field in CUSTOMER_FIELDS:
                incoming = record.get(field)

                if incoming and not existing.get(field):
                    existing[field] = incoming

            continue

        phone = record.get("phone")
        name_key = normalize_column(record.get("name", ""))

        key = (phone or "", name_key)

        if key not in by_fallback:
            by_fallback[key] = dict(record)
            continue

        existing = by_fallback[key]

        for field in CUSTOMER_FIELDS:
            incoming = record.get(field)

            if incoming and not existing.get(field):
                existing[field] = incoming

    return list(by_consumer.values()) + list(by_fallback.values())



# ============================================================
# IMPORT
# ============================================================

def import_records(
    db: Session,
    filename: str,
    file_type: str,
    records: list[dict],
) -> dict:
    """
    Import customer records.

    Behavior:

    1. New consumer number
       -> create customer.

    2. Existing consumer number
       -> do not create duplicate.
       -> synchronize non-empty Excel fields.

    3. No consumer number
       -> use phone + normalized name
          as fallback duplicate detection.

    4. Empty Excel values never overwrite existing CRM data.
       Non-empty changed Excel values are synchronized.
    """

    batch = ImportBatch(
        filename=filename,
        file_type=file_type,
        total_rows=len(records),
        status="processing",
    )

    db.add(batch)
    db.flush()

    seen_consumers: set[str] = set()
    seen_fallback: set[
        tuple[str, str]
    ] = set()

    imported = 0
    updated = 0
    duplicates = 0
    skipped = 0

    try:

        consumer_numbers = {
            record["consumer_number"]
            for record in records
            if record.get("consumer_number")
        }
        fallback_phones = {
            record["phone"]
            for record in records
            if not record.get("consumer_number") and record.get("phone")
        }
        customers_by_consumer = load_customers_by_consumer_number(
            db,
            consumer_numbers,
        )
        customers_by_fallback = load_customers_by_phone_and_name(
            db,
            fallback_phones,
        )

        for record in records:

            consumer = record.get(
                "consumer_number"
            )

            # =================================================
            # PRIMARY MATCH: CONSUMER NUMBER
            # =================================================

            if consumer:

                # Duplicate inside current Excel file.
                if consumer in seen_consumers:
                    duplicates += 1
                    continue

                seen_consumers.add(consumer)

                existing = customers_by_consumer.get(consumer)

                # Existing customer.
                if existing:

                    previous_fallback_key = (
                        (existing.phone, normalize_column(existing.name))
                        if existing.phone
                        else None
                    )

                    changed_fields = (
                        update_customer_fields(
                            existing,
                            record,
                        )
                    )

                    if changed_fields:
                        updated += 1
                    else:
                        skipped += 1

                    refresh_fallback_customer(
                        customers_by_fallback,
                        existing,
                        previous_fallback_key,
                    )

                    continue

            # =================================================
            # FALLBACK MATCH: PHONE + NAME
            # =================================================

            else:

                phone = record.get(
                    "phone"
                )

                name_key = normalize_column(
                    record.get("name", "")
                )

                fallback_key = (
                    phone,
                    name_key,
                )

                # Duplicate inside current file.
                if (
                    phone
                    and fallback_key
                    in seen_fallback
                ):
                    duplicates += 1
                    continue

                existing = (
                    customers_by_fallback.get(fallback_key)
                    if phone
                    else None
                )

                if existing:

                    previous_fallback_key = (
                        (existing.phone, normalize_column(existing.name))
                        if existing.phone
                        else None
                    )

                    changed_fields = (
                        update_customer_fields(
                            existing,
                            record,
                        )
                    )

                    if changed_fields:
                        updated += 1
                    else:
                        skipped += 1

                    seen_fallback.add(
                        fallback_key
                    )
                    refresh_fallback_customer(
                        customers_by_fallback,
                        existing,
                        previous_fallback_key,
                    )

                    continue

                if phone:
                    seen_fallback.add(
                        fallback_key
                    )

            # =================================================
            # CREATE NEW CUSTOMER
            # =================================================

            customer_data = {
                key: value
                for key, value in record.items()
                if key != "source_row"
            }

            customer = Customer(
                **customer_data,
                import_id=batch.id,
                source_file=filename,
                source_row=record["source_row"],
            )

            db.add(customer)
            refresh_fallback_customer(
                customers_by_fallback,
                customer,
            )

            imported += 1

        # -----------------------------------------------------
        # Save import statistics
        # -----------------------------------------------------

        batch.imported_rows = imported
        batch.duplicate_rows = duplicates
        batch.skipped_rows = skipped
        batch.status = "completed"

        db.commit()

        return {
            "import_id": batch.id,
            "total_rows": len(records),
            "imported_rows": imported,
            "updated_rows": updated,
            "duplicate_rows": duplicates,
            "skipped_rows": skipped,
            "status": "completed",
        }

    except Exception:
        db.rollback()

        batch.status = "failed"

        try:
            db.commit()
        except Exception:
            db.rollback()

        raise
