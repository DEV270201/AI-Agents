import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from db import get_engine, init_db
from tools import tool_add_expense


async def _run_add_expense_self_tests() -> None:
    """Run with: ``python tests/run_add_expense_tool.py`` from the project root.

  Requires ``MYSQL_DATABASE_URL``. Deletes rows created for each test via a unique
  ``notes`` marker.
    """
    await init_db()
    engine = get_engine()

    async def cleanup_notes(marker: str) -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM expenses WHERE notes = :marker"),
                {"marker": marker},
            )

    async def fetch_row(marker: str, columns: str) -> tuple | None:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT {columns} FROM expenses WHERE notes = :marker LIMIT 1"
                    ),
                    {"marker": marker},
                )
            ).fetchone()
        return row

    async def check_success() -> None:
        marker = "tool_self_test:check_success"
        await cleanup_notes(marker)
        try:
            out = await tool_add_expense(
                "2000-06-01",
                "food",
                12.50,
                currency="USD",
                notes=marker,
            )
            assert out.startswith("Logged expense id="), out
            assert "$12.50 USD" in out and "food" in out and marker in out, out
            row = await fetch_row(marker, "amount, category, notes")
            assert row == (1250, "food", marker), row
        finally:
            await cleanup_notes(marker)

    async def check_small_decimal_amount() -> None:
        marker = "tool_self_test:check_small_decimal"
        await cleanup_notes(marker)
        try:
            out = await tool_add_expense(
                "2000-01-01",
                "bills",
                0.01,
                notes=marker,
            )
            assert "$0.01 USD" in out, out
        finally:
            await cleanup_notes(marker)

    async def check_rounding_half_up() -> None:
        marker = "tool_self_test:check_rounding"
        await cleanup_notes(marker)
        try:
            out = await tool_add_expense(
                "2000-01-01",
                "shopping",
                "12.345",
                notes=marker,
            )
            row = await fetch_row(marker, "amount")
            assert row is not None and row[0] == 1235, row
            assert "$12.35 USD" in out, out
        finally:
            await cleanup_notes(marker)

    async def check_missing_amount() -> None:
        assert (await tool_add_expense("2000-01-01", "food", None)).startswith(
            "Error: missing amount"
        )

    async def check_unknown_category() -> None:
        r = await tool_add_expense("2000-01-01", "crypto", 1)
        assert "unknown category" in r and "allowed:" in r, r

    async def check_future_date() -> None:
        r = await tool_add_expense("2099-12-31", "food", 1)
        assert "cannot be after" in r and "(UTC)" in r, r

    async def check_invalid_occurred_at() -> None:
        assert (
            await tool_add_expense("05/09/2025", "food", 1)
        ) == "Error: invalid occurred_at"
        assert (
            await tool_add_expense("2025-02-30", "food", 1)
        ) == "Error: invalid occurred_at"

    async def check_notes_too_long() -> None:
        long_notes = "x" * 256
        r = await tool_add_expense("2000-01-01", "food", 1, notes=long_notes)
        assert r == "Error: notes exceed 255 characters", r

    async def check_non_positive_amount() -> None:
        assert (
            await tool_add_expense("2000-01-01", "food", 0)
            == "Error: amount must be positive"
        )

    async def check_invalid_currency() -> None:
        r = await tool_add_expense("2000-01-01", "food", 1, currency="US")
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
            await fn()
            print(f"ok: {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {name}: {e}")

    if failed:
        raise SystemExit(f"{failed} test(s) failed")
    print("All add_expense self-tests passed.")


if __name__ == "__main__":
    asyncio.run(_run_add_expense_self_tests())
