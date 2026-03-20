"""Tests for shift utility functions: count_workdays and enrich_with_possible_hours."""

import sys
import os
from datetime import date
from unittest.mock import patch

# Add project root to path so we can import without Flask context
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask_app.models.shift import (
    count_workdays,
    enrich_with_possible_hours,
    format_seconds_as_hms,
    HOURS_PER_WORKDAY,
)


class TestCountWorkdays:
    """Tests for count_workdays(start_date, end_date)."""

    def test_full_week(self):
        """Mon Jan 6 to Fri Jan 10 = 5 workdays."""
        workdays, capped = count_workdays(date(2025, 1, 6), date(2025, 1, 10))
        assert workdays == 5
        assert capped == date(2025, 1, 10)

    def test_q1_2026_full_quarter(self):
        """Jan 1 - Mar 31, 2026 has 63 workdays (verified by calendar)."""
        with patch("flask_app.models.shift.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 2)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            workdays, capped = count_workdays(date(2026, 1, 1), date(2026, 3, 31))
        assert workdays == 64
        assert capped == date(2026, 3, 31)

    def test_weekend_only_range(self):
        """Sat-Sun range = 0 workdays."""
        # Jan 4-5, 2025 is Sat-Sun
        workdays, capped = count_workdays(date(2025, 1, 4), date(2025, 1, 5))
        assert workdays == 0

    def test_single_weekday(self):
        """Single Monday = 1 workday."""
        workdays, capped = count_workdays(date(2025, 1, 6), date(2025, 1, 6))
        assert workdays == 1

    def test_single_weekend_day(self):
        """Single Saturday = 0 workdays."""
        workdays, capped = count_workdays(date(2025, 1, 4), date(2025, 1, 4))
        assert workdays == 0

    def test_future_date_capped_at_today(self):
        """End date in the future gets capped at today."""
        with patch("flask_app.models.shift.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 20)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            workdays, capped = count_workdays(date(2026, 3, 16), date(2026, 3, 31))
        assert capped == date(2026, 3, 20)
        # Mar 16 (Mon) through Mar 20 (Fri) = 5 workdays
        assert workdays == 5

    def test_past_date_not_capped(self):
        """Past end date is not capped — boss checking Q1 in April."""
        with patch("flask_app.models.shift.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 2)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            workdays, capped = count_workdays(date(2026, 1, 1), date(2026, 3, 31))
        assert capped == date(2026, 3, 31)
        assert workdays == 64

    def test_start_after_end_returns_zero(self):
        """Reversed date range returns 0 workdays."""
        workdays, capped = count_workdays(date(2025, 1, 10), date(2025, 1, 6))
        assert workdays == 0


class TestEnrichWithPossibleHours:
    """Tests for enrich_with_possible_hours(employee_data, workdays)."""

    def _make_emp(self, total_seconds):
        """Helper to create a minimal employee dict."""
        return {
            "total_seconds": total_seconds,
            "total_hours_formatted": format_seconds_as_hms(total_seconds),
        }

    def test_basic_enrichment(self):
        """65 workdays × 6.5h = 422.5h = 1,521,000 seconds."""
        emp = self._make_emp(100000)
        enrich_with_possible_hours([emp], 65)
        expected_possible = 65 * HOURS_PER_WORKDAY * 3600
        assert emp["possible_seconds"] == expected_possible
        assert emp["utilization_pct"] == round(100000 / expected_possible * 100, 1)

    def test_zero_workdays_gives_none_utilization(self):
        """Zero workdays should produce None utilization (not division by zero)."""
        emp = self._make_emp(50000)
        enrich_with_possible_hours([emp], 0)
        assert emp["possible_seconds"] == 0
        assert emp["utilization_pct"] is None

    def test_over_100_percent(self):
        """Employee working more than possible hours shows >100%."""
        possible_for_one_day = HOURS_PER_WORKDAY * 3600  # 23400
        emp = self._make_emp(possible_for_one_day * 2)  # Double the possible
        enrich_with_possible_hours([emp], 1)
        assert emp["utilization_pct"] == 200.0

    def test_possible_hours_formatted(self):
        """Possible hours string is correctly formatted."""
        emp = self._make_emp(0)
        enrich_with_possible_hours([emp], 10)
        # 10 days × 6.5h = 65h = 65:00:00
        assert emp["possible_hours_formatted"] == "65:00:00"

    def test_multiple_employees_same_possible(self):
        """All employees get the same possible hours."""
        emps = [self._make_emp(10000), self._make_emp(20000), self._make_emp(30000)]
        enrich_with_possible_hours(emps, 5)
        expected = 5 * HOURS_PER_WORKDAY * 3600
        for emp in emps:
            assert emp["possible_seconds"] == expected
        # But utilization differs
        assert (
            emps[0]["utilization_pct"]
            < emps[1]["utilization_pct"]
            < emps[2]["utilization_pct"]
        )
