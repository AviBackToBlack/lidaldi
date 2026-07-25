"""N7: nearest-future-date year rollover in parse_store_availability."""

from datetime import datetime

import pytest


@pytest.fixture
def psa(po):
    return po.parse_store_availability


DEC = datetime(2025, 12, 10)
JUN = datetime(2025, 6, 15)


# ---------------------------------------------------------------------------
# dd.mm rollover
# ---------------------------------------------------------------------------
def test_march_seen_in_december_rolls_to_next_year(psa):
    # The old Nov->Feb heuristic misclassified this as past.
    assert psa("From 05.03", now=DEC) == "05-03-2026"


def test_january_seen_in_december_rolls_to_next_year(psa):
    assert psa("From 15.01", now=DEC) == "15-01-2026"


def test_future_date_same_year_kept(psa):
    assert psa("From 20.12", now=DEC) == "20-12-2025"


def test_recently_past_date_is_started(psa):
    # Nearest occurrence of 01.12 to Dec 10 is 9 days ago -> window started.
    assert psa("From 01.12", now=DEC) == "01-01-0000"


def test_past_date_mid_year_is_started(psa):
    # Nearest occurrence of 01.05 to Jun 15 is ~6 weeks ago -> started.
    assert psa("From 01.05", now=JUN) == "01-01-0000"


def test_far_future_mid_year_kept(psa):
    assert psa("From 01.11", now=JUN) == "01-11-2025"


def test_half_year_distance_resolves_to_nearest(psa):
    # 10.06 seen on Dec 10 2025: next Jun 10 (182 days ahead) is nearer
    # than last Jun 10 (183 days ago) -> future start date.
    assert psa("From 10.06", now=DEC) == "10-06-2026"


def test_feb29_seen_in_non_adjacent_leap_window(psa):
    # 29.02 around Dec 2025: 2024 is valid (past) -> started.
    assert psa("From 29.02", now=DEC) == "01-01-0000"


def test_feb29_no_valid_candidate(psa):
    # Around Jun 2026: none of 2025/2026/2027 is a leap year -> unknown.
    assert psa("From 29.02", now=datetime(2026, 6, 15)) == "01-01-9999"


def test_invalid_month_is_unknown(psa):
    assert psa("From 05.13", now=DEC) == "01-01-9999"


# ---------------------------------------------------------------------------
# Weekday "Sun 8 Mar" rollover
# ---------------------------------------------------------------------------
def test_weekday_march_seen_in_december_rolls(psa):
    assert psa("Sun 8 Mar", now=DEC) == "08-03-2026"


def test_weekday_future_same_year_kept(psa):
    assert psa("Sat 20 Dec", now=DEC) == "20-12-2025"


def test_weekday_recently_past_is_started(psa):
    assert psa("Mon 1 Dec", now=DEC) == "01-01-0000"


def test_weekday_bad_month_is_unknown(psa):
    assert psa("Mon 5 Xyz", now=DEC) == "01-01-9999"


# ---------------------------------------------------------------------------
# Unchanged branches
# ---------------------------------------------------------------------------
def test_explicit_year_past_is_started(psa):
    assert psa("From 05-03-2025", now=DEC) == "01-01-0000"


def test_explicit_year_future_kept(psa):
    assert psa("From 05-03-2026", now=DEC) == "05-03-2026"


def test_while_stock_lasts(psa):
    assert psa("While stock lasts", now=DEC) == "01-01-0000"


def test_unknown(psa):
    assert psa("Unknown", now=DEC) == "01-01-9999"
