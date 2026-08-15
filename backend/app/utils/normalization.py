import re
from typing import Any

def normalize_phone(value: Any) -> str | None:
    """Normalize phone numbers. Handle None, NaN, floats ending in .0, +91 prefix, leading 0, etc. Return 10-digit string or None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ('nan', 'none', 'null', 'nat', '<na>'):
        return None
    # Remove .0 from Excel float conversion
    if text.endswith('.0') and text[:-2].replace('-', '').replace('+', '').isdigit():
        text = text[:-2]
    digits = re.sub(r'\D', '', text)
    if not digits or digits == '0' or all(c == '0' for c in digits):
        return None
    if len(digits) == 10:
        return digits
    if len(digits) == 12 and digits.startswith('91'):
        return digits[2:]
    if len(digits) == 11 and digits.startswith('0'):
        return digits[1:]
    return digits if len(digits) >= 7 else None

def normalize_email(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in ('nan', 'none', 'null', 'nat', '<na>'):
        return None
    return text if '@' in text else None

def normalize_consumer_number(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ('nan', 'none', 'null', 'nat', '<na>'):
        return None
    if text.endswith('.0') and text[:-2].isdigit():
        text = text[:-2]
    return text if text else None
