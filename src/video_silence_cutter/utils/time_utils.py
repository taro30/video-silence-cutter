import re

def seconds_to_hms(seconds: float, include_millis: bool = False) -> str:
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    
    total_seconds = int(seconds)
    millis = int(round((seconds - total_seconds) * 1000))
    if millis >= 1000:
        total_seconds += 1
        millis = 0

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if include_millis:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def hms_to_seconds(hms_str: str) -> float:
    s = hms_str.strip()
    if not s:
        raise ValueError("Time string cannot be empty")

    parts = s.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    elif len(parts) == 1:
        hours = 0
        minutes = 0
        seconds = float(parts[0])
    else:
        raise ValueError(f"Invalid time format: {hms_str}")

    if hours < 0 or minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
        raise ValueError(f"Time components out of bounds in: {hms_str}")

    return hours * 3600 + minutes * 60 + seconds


def validate_hms(hms_str: str) -> bool:
    try:
        hms_to_seconds(hms_str)
        return True
    except Exception:
        return False
