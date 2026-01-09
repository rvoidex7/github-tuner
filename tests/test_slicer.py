import pytest
from tuner.slicer import split_date_range, get_query_with_date
import pendulum

def test_split_date_range():
    start = "2024-01-01"
    end = "2024-01-03"

    s, m, e = split_date_range(start, end)

    # Midpoint of 48 hours is 24 hours later -> 2024-01-02
    assert pendulum.parse(s) == pendulum.parse("2024-01-01")
    assert pendulum.parse(m) == pendulum.parse("2024-01-02")
    assert pendulum.parse(e) == pendulum.parse("2024-01-03")

def test_get_query_with_date():
    q = "machine learning"
    s = "2023-01-01"
    e = "2023-12-31"

    res = get_query_with_date(q, s, e)
    assert res == "machine learning created:2023-01-01..2023-12-31"
