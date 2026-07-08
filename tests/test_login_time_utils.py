from datetime import datetime, timezone

from login.time_utils import ensure_utc_datetime, is_newer_than_issued_at


class TestLoginTimeUtils:

    def test_ensure_utc_datetime_marks_naive_as_utc(self):
        dt = datetime(2026, 5, 20, 13, 0, 0)
        normalized = ensure_utc_datetime(dt)
        assert normalized is not None
        assert normalized.tzinfo == timezone.utc
        assert normalized.hour == 13

    def test_is_newer_than_issued_at_handles_naive_database_datetime(self):
        password_changed_at = datetime(2026, 5, 20, 13, 0, 1)
        issued_at = datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc).timestamp()
        assert is_newer_than_issued_at(password_changed_at, issued_at) is True

    def test_is_newer_than_issued_at_returns_false_for_older_timestamp(self):
        password_changed_at = datetime(2026, 5, 20, 12, 59, 59, tzinfo=timezone.utc)
        issued_at = datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc).timestamp()
        assert is_newer_than_issued_at(password_changed_at, issued_at) is False
