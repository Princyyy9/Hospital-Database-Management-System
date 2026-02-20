import datetime
import re

def to_ddmmyyyy(date_str):
    """
    Converts supported date formats to DD/MM/YYYY.
    """
    if not date_str:
        return ""
    try:
        if isinstance(date_str, (datetime.date, datetime.datetime)):
            return date_str.strftime("%d/%m/%Y")
        if isinstance(date_str, str):
            if len(date_str) == 10 and date_str[2] == "/" and date_str[5] == "/":
                return date_str
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
                try:
                    dt = datetime.datetime.strptime(date_str, fmt)
                    return dt.strftime("%d/%m/%Y")
                except ValueError:
                    continue
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]:
                try:
                    dt = datetime.datetime.strptime(date_str, fmt)
                    return dt.strftime("%d/%m/%Y")
                except ValueError:
                    continue
    except Exception:
        pass
    return date_str or ""

def convert_to_db_date_format(date_str_dd_mm_yyyy):
    """
    Converts DD/MM/YYYY to YYYY-MM-DD for DB storage.
    """
    if not date_str_dd_mm_yyyy:
        return None
    try:
        dt_obj = datetime.datetime.strptime(date_str_dd_mm_yyyy, "%d/%m/%Y").date()
        return dt_obj.strftime("%Y-%m-%d")
    except ValueError:
        return None

def convert_from_db_date_format(date_str_yyyy_mm_dd):
    """
    Converts YYYY-MM-DD to DD/MM/YYYY for display.
    """
    if not date_str_yyyy_mm_dd or date_str_yyyy_mm_dd == 'None':
        return None
    try:
        dt_obj = datetime.datetime.strptime(date_str_yyyy_mm_dd, "%Y-%m-%d").date()
        return dt_obj.strftime("%d/%m/%Y")
    except ValueError:
        return None

def is_valid_email(email):
    """
    Validates email format.
    """
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))

def is_valid_mobile(mobile):
    """
    Validates that mobile is 10 digits.
    """
    return bool(re.match(r"^\d{10}$", mobile))

def is_valid_age(age):
    """
    Checks if age is between 0 and 150
    """
    try:
        age = int(age)
        return 0 <= age <= 150
    except Exception:
        return False

def is_valid_date_ddmmyyyy(date_str):
    """
    Checks if date is in DD/MM/YYYY format and valid.
    """
    try:
        datetime.datetime.strptime(date_str, "%d/%m/%Y")
        return True
    except Exception:
        return False