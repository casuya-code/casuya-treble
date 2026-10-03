from datetime import date

from shared.visits import visit_totals

TODAY = date(2026, 10, 3)  # Saturday


def test_same_visitor_on_one_day_counts_once():
    rows = [("a", TODAY), ("a", TODAY)]
    totals = visit_totals(rows, TODAY)
    assert totals["today"] == 1
    assert totals["week"] == 1
    assert totals["year"] == 1
    assert totals["yesterday"] == 0


def test_periods_follow_the_nairobi_calendar():
    rows = [
        ("a", date(2026, 10, 3)),
        ("b", date(2026, 10, 2)),
        ("e", date(2026, 9, 29)),
        ("c", date(2026, 1, 2)),
        ("d", date(2025, 12, 31)),
    ]
    totals = visit_totals(rows, TODAY)
    assert totals == {"today": 1, "yesterday": 1, "week": 3, "year": 4}
