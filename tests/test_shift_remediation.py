"""Tests for shared shift remediation logic."""

import os
import sys
from datetime import datetime
from unittest.mock import ANY, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask_app.models.shift import Shift
from flask_app.utils import scheduler_tasks


class TestNormalizedEndTime:
    """Tests for the shared normalized end-time rule."""

    def test_before_cutoff_maps_to_330_pm_same_day(self):
        created_at = datetime(2026, 3, 31, 7, 3, 0)

        assert Shift.normalized_end_time(created_at) == datetime(
            2026, 3, 31, 15, 30, 0
        )

    def test_at_or_after_cutoff_maps_to_start_time(self):
        created_at = datetime(2026, 3, 31, 15, 30, 0)

        assert Shift.normalized_end_time(created_at) == created_at


class TestWeekdayShiftRemediation:
    """Tests for the single-pass remediation orchestration."""

    def test_run_weekday_shift_remediation_returns_structured_counts(self):
        with (
            patch.object(
                Shift,
                "_close_open_shifts_where",
                side_effect=[4, 2],
            ) as mock_close,
            patch.object(
                Shift,
                "_fix_multiday_shifts_where",
                return_value=3,
            ) as mock_fix_multiday,
        ):
            summary = Shift.run_weekday_shift_remediation()

        assert summary == {
            "today_closed": 4,
            "older_open_closed": 2,
            "multiday_corrected": 3,
            "total_affected": 9,
        }
        mock_close.assert_has_calls(
            [
                call("DATE(created_at) = CURDATE()"),
                call("DATE(created_at) < CURDATE()"),
            ]
        )
        mock_fix_multiday.assert_called_once_with()

    def test_run_weekday_shift_remediation_is_idempotent_when_nothing_left(self):
        with (
            patch.object(Shift, "_close_open_shifts_where", side_effect=[0, 0]),
            patch.object(Shift, "_fix_multiday_shifts_where", return_value=0),
        ):
            summary = Shift.run_weekday_shift_remediation()

        assert summary == {
            "today_closed": 0,
            "older_open_closed": 0,
            "multiday_corrected": 0,
            "total_affected": 0,
        }

    def test_scheduler_task_logs_completion_summary(self):
        fake_summary = {
            "today_closed": 5,
            "older_open_closed": 1,
            "multiday_corrected": 2,
            "total_affected": 8,
        }

        with (
            patch.object(Shift, "run_weekday_shift_remediation", return_value=fake_summary),
            patch.object(scheduler_tasks, "get_scheduler_logger") as mock_get_logger,
        ):
            logger = mock_get_logger.return_value
            result = scheduler_tasks.run_weekday_shift_remediation()

        assert result == fake_summary
        logger.info.assert_any_call("SHIFT_REMEDIATION_START at=%s", ANY)
        logger.info.assert_any_call(
            "SHIFT_REMEDIATION_COMPLETE at=%s today_closed=%s older_open_closed=%s multiday_corrected=%s total_affected=%s",
            ANY,
            5,
            1,
            2,
            8,
        )
