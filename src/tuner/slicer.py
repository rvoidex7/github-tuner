import pendulum
from typing import Tuple

def split_date_range(start: str, end: str) -> Tuple[str, str, str]:
    """
    Split a date range (ISO strings) into two equal halves.
    Returns (start, midpoint, end) strings.
    """
    s = pendulum.parse(start)
    e = pendulum.parse(end)

    # Calculate difference in seconds
    diff_seconds = (e - s).total_seconds()

    # Midpoint
    mid = s.add(seconds=diff_seconds / 2)

    return s.to_iso8601_string(), mid.to_iso8601_string(), e.to_iso8601_string()

def get_query_with_date(query: str, start: str, end: str) -> str:
    """Append or replace created: range in query."""
    # This is a simple implementation. Ideally we parse the query to remove existing date range.
    # For now, we assume the base query doesn't have a date range or we append it.
    # GitHub queries allow multiple terms, but usually last one wins or acts as AND.
    return f"{query} created:{start}..{end}"
