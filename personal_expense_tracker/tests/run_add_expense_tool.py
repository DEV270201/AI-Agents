import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import init_db, get_connection
from tools import tool_add_expense


def _run_add_expense_self_tests() -> None:
    """Run with: ``python tools.py`` from the project root.

    Uses the real database from ``get_connection()`` and deletes rows created for
    each test via a unique ``notes`` marker.
    """
    init_db()

    def cleanup_notes(marker: str) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM expenses WHERE notes = ?", (marker,))
            conn.commit()
        finally:
            conn.close()

    def check_success() -> None:
        marker = "tool_self_test:check_success"
        cleanup_notes(marker)
        try:
            out = tool_add_expense(
                "2000-06-01",
                "food",
                12.50,
                currency="USD",
                notes=marker,
            )
            assert out.startswith("Logged expense id="), out
            assert "$12.50 USD" in out and "food" in out and marker in out, out
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT amount, category, notes FROM expenses WHERE notes = ?",
                    (marker,),
                ).fetchone()
            finally:
                conn.close()
            assert row == (1250, "food", marker), row
        finally:
            cleanup_notes(marker)

    def check_small_decimal_amount() -> None:
        marker = "tool_self_test:check_small_decimal"
        cleanup_notes(marker)
        try:
            out = tool_add_expense(
                "2000-01-01",
                "bills",
                0.01,
                notes=marker,
            )
            assert "$0.01 USD" in out, out
        finally:
            cleanup_notes(marker)

    def check_rounding_half_up() -> None:
        marker = "tool_self_test:check_rounding"
        cleanup_notes(marker)
        try:
            out = tool_add_expense(
                "2000-01-01",
                "shopping",
                "12.345",
                notes=marker,
            )
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT amount FROM expenses WHERE notes = ?", (marker,)
                ).fetchone()
            finally:
                conn.close()
            assert row[0] == 1235, row
            assert "$12.35 USD" in out, out
        finally:
            cleanup_notes(marker)

    def check_missing_amount() -> None:
        assert tool_add_expense("2000-01-01", "food", None).startswith(
            "Error: missing amount"
        )

    def check_unknown_category() -> None:
        r = tool_add_expense("2000-01-01", "crypto", 1)
        assert "unknown category" in r and "allowed:" in r, r

    def check_future_date() -> None:
        r = tool_add_expense("2099-12-31", "food", 1)
        assert "cannot be after" in r and "(UTC)" in r, r

    def check_invalid_occurred_at() -> None:
        assert tool_add_expense("05/09/2025", "food", 1) == "Error: invalid occurred_at"
        assert tool_add_expense("2025-02-30", "food", 1) == "Error: invalid occurred_at"

    def check_notes_too_long() -> None:
        long_notes = "x" * 256
        r = tool_add_expense("2000-01-01", "food", 1, notes=long_notes)
        assert r == "Error: notes exceed 255 characters", r

    def check_non_positive_amount() -> None:
        assert (
            tool_add_expense("2000-01-01", "food", 0) == "Error: amount must be positive"
        )

    def check_invalid_currency() -> None:
        r = tool_add_expense("2000-01-01", "food", 1, currency="US")
        assert "invalid currency" in r, r

    test_fns = (
        check_success,
        check_small_decimal_amount,
        check_rounding_half_up,
        check_missing_amount,
        check_unknown_category,
        check_future_date,
        check_invalid_occurred_at,
        check_notes_too_long,
        check_non_positive_amount,
        check_invalid_currency,
    )

    failed = 0
    for fn in test_fns:
        name = fn.__name__
        try:
            fn()
            print(f"ok: {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {name}: {e}")

    if failed:
        raise SystemExit(f"{failed} test(s) failed")
    print("All add_expense self-tests passed.")


if __name__ == "__main__":
    _run_add_expense_self_tests()