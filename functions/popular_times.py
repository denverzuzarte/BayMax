from datetime import datetime


def _classify(hour: int, weekday: int) -> dict:
    """
    Pure logic — takes hour (0-23) and weekday (0=Mon, 6=Sun).
    Extracted so tests can call it directly without mocking datetime.
    Based on typical Indian hospital OPD patterns.
    """
    if weekday == 6:  # Sunday
        return {"level": "quiet", "label": "Estimated quiet — Sunday"}

    if weekday == 5:  # Saturday
        if 9 <= hour < 14:
            return {"level": "busy", "label": "Estimated busy — Saturday morning"}
        return {"level": "moderate", "label": "Estimated moderate — Saturday"}

    # Weekdays
    if 8 <= hour < 11:
        return {"level": "very_busy", "label": "Estimated very busy — morning rush"}
    if 11 <= hour < 13:
        return {"level": "busy", "label": "Estimated busy"}
    if 13 <= hour < 15:
        return {"level": "moderate", "label": "Estimated moderate — post-lunch"}
    if 15 <= hour < 18:
        return {"level": "busy", "label": "Estimated busy — evening rush"}
    if 18 <= hour < 20:
        return {"level": "moderate", "label": "Estimated moderate — evening"}

    return {"level": "quiet", "label": "Estimated quiet"}


def get_wait_indicator(lat=None, lng=None, place_id=None) -> dict:
    """
    Returns a busyness estimate based on time of day and day of week.
    Google does not expose Popular Times via any official API.
    This is a heuristic based on typical Indian hospital OPD patterns.

    NEVER call this 'live' or 'real-time' in the UI.
    Always display the full label so users know it is an estimate.

    UI rendering:
      very_busy → red dot
      busy      → orange dot
      moderate  → yellow dot
      quiet     → green dot

    Returns: {"level": str, "label": str}
    """
    now = datetime.now()
    return _classify(now.hour, now.weekday())
