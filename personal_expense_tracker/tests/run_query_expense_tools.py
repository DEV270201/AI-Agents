import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from db import get_engine, init_db
from tools import tool_list_expenses, tool_summarize_expenses


async def _run_query_expense_tools_self_tests() -> None:
    """Run with: ``python tests/run_query_expense_tools.py`` from the project root.

    Requires ``MYSQL_DATABASE_URL``.
    Deletes rows created for each test via unique ``notes`` markers.
    """
    await init_db()
    engine = get_engine()

    async def cleanup_markers(markers: list[str]) -> None:
        async with engine.begin() as conn:
            for marker in markers:
                await conn.execute(
                    text("DELETE FROM expenses WHERE notes = :marker"),
                    {"marker": marker},
                )

    async def insert_row(
        occurred_at: str, category: str, amount_cents: int, notes: str, currency: str = "USD"
    ) -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO expenses (occurred_at, amount, currency, category, notes)
                    VALUES (:occurred_at, :amount, :currency, :category, :notes)
                    """
                ),
                {
                    "occurred_at": occurred_at,
                    "amount": amount_cents,
                    "currency": currency,
                    "category": category,
                    "notes": notes,
                },
            )

    async def check_summarize_fixed_top3_and_no_id() -> None:
        markers = [
            "tool_self_test:sum:1",
            "tool_self_test:sum:2",
            "tool_self_test:sum:3",
            "tool_self_test:sum:4",
        ]
        await cleanup_markers(markers)
        try:
            # Same range, 4 rows; summarize should list exactly 3 highlights.
            await insert_row("2000-01-02", "food", 1000, markers[0])
            await insert_row("2000-01-03", "food", 3000, markers[1])
            await insert_row("2000-01-04", "shopping", 2000, markers[2])
            await insert_row("2000-01-05", "bills", 4000, markers[3])

            out = await tool_summarize_expenses("2000-01-01", "2000-01-10", sort_type="max")
            assert out.startswith("Summary 2000-01-01..2000-01-10 (UTC):"), out
            assert "By category:" in out and "Top 3" in out, out
            assert "id=" not in out, out
            assert out.count("notes=") == 3, out
        finally:
            await cleanup_markers(markers)

    async def check_summarize_tie_break_most_recent() -> None:
        markers = ["tool_self_test:tie:old", "tool_self_test:tie:new"]
        await cleanup_markers(markers)
        try:
            # Same amount, later date should appear earlier in Top 3.
            await insert_row("2000-02-01", "food", 5000, markers[0])
            await insert_row("2000-02-02", "food", 5000, markers[1])

            out = await tool_summarize_expenses("2000-02-01", "2000-02-10", sort_type="max")
            idx_new = out.find(markers[1])
            idx_old = out.find(markers[0])
            assert idx_new != -1 and idx_old != -1 and idx_new < idx_old, out
        finally:
            await cleanup_markers(markers)

    async def check_list_caps_topn_and_more_message() -> None:
        markers = [
            "tool_self_test:list:1",
            "tool_self_test:list:2",
            "tool_self_test:list:3",
            "tool_self_test:list:4",
            "tool_self_test:list:5",
            "tool_self_test:list:6",
        ]
        await cleanup_markers(markers)
        try:
            # 6 rows; list with top_n=10 should cap to 5 and show "more exist" hint.
            for i, m in enumerate(markers, start=1):
                await insert_row("2000-03-01", "entertainment", i * 100, m)

            out = await tool_list_expenses(
                "2000-03-01",
                "2000-03-10",
                category="entertainment",
                top_n=10,
                sort_type="max",
            )
            assert out.startswith("List 2000-03-01..2000-03-10 (UTC), category=entertainment:"), out
            assert "(requested 10, showing 5 max)" in out, out
            assert "More expenses exist in this period" in out, out
            assert out.count("notes=") == 5, out
        finally:
            await cleanup_markers(markers)

    async def check_future_end_date_rejected() -> None:
        future = date(2099, 12, 31).isoformat()
        out = await tool_summarize_expenses("2000-01-01", future)
        assert out.startswith("Error: end_date cannot be after "), out

    async def check_unknown_category_rejected() -> None:
        out = await tool_list_expenses("2000-01-01", "2000-01-10", category="crypto")
        assert "unknown category" in out and "allowed:" in out, out

    tests = (
        check_summarize_fixed_top3_and_no_id,
        check_summarize_tie_break_most_recent,
        check_list_caps_topn_and_more_message,
        check_future_end_date_rejected,
        check_unknown_category_rejected,
    )

    failed = 0
    for fn in tests:
        name = fn.__name__
        try:
            await fn()
            print(f"ok: {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {name}: {e}")

    if failed:
        raise SystemExit(f"{failed} test(s) failed")
    print("All expense query tool self-tests passed.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_run_query_expense_tools_self_tests())

