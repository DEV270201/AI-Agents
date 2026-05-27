import random
import re
import time
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional, Union

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from db import get_engine

_ALLOWED_CATEGORIES = frozenset(
    {"food", "bills", "entertainment", "shopping", "travel"}
)
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

_SUMMARIZE_TOP_N = 3
_LIST_DEFAULT_TOP_N = 3
_LIST_MAX_TOP_N = 5


def _add_jitter() -> float:
    jitter_time = random.uniform(0.1, 1.5)
    return jitter_time


def _parse_iso_date_strict(value: str) -> date:
    if not isinstance(value, str) or not _ISO_DATE_PATTERN.fullmatch(value):
        raise ValueError("occurred_at must be YYYY-MM-DD")
    return date.fromisoformat(value)


def _major_units_to_cents(amount: Union[int, float, str, Decimal]) -> int:
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("amount is not a valid number") from None
    quantized = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cents = int(quantized * 100)
    return cents


def _format_observation_money(cents: int, currency: str) -> str:
    major = Decimal(cents) / Decimal(100)
    quantized = major.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if currency == "USD":
        return f"${quantized} USD"
    return f"{quantized} {currency}"


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _default_calendar_week_range(ref_day: date) -> tuple[date, date]:
    """Return (monday_of_current_utc_week, ref_day), both inclusive."""
    start = ref_day.fromordinal(ref_day.toordinal() - ref_day.weekday())
    return start, ref_day


def _resolve_date_range(
    start_date: Optional[str], end_date: Optional[str]
) -> tuple[Optional[date], Optional[date], Optional[str]]:
    """Parse and validate a date range. Returns (start, end, error_str)."""
    ref_day = _utc_today()
    if not start_date or not end_date:
        start, end = _default_calendar_week_range(ref_day)
        return start, end, None

    try:
        start = _parse_iso_date_strict(start_date)
    except ValueError:
        return None, None, "Error: invalid start_date"

    try:
        end = _parse_iso_date_strict(end_date)
    except ValueError:
        return None, None, "Error: invalid end_date"

    if start > end:
        return None, None, "Error: start_date must be on or before end_date"

    if start > ref_day:
        return (
            None,
            None,
            f"Error: start_date cannot be after {ref_day.isoformat()} (UTC)",
        )
    if end > ref_day:
        return None, None, f"Error: end_date cannot be after {ref_day.isoformat()} (UTC)"

    return start, end, None


def _normalize_sort_type(sort_type: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return (sql_dir, error_str)."""
    if sort_type is None:
        return "DESC", None
    norm = str(sort_type).strip().lower()
    if norm in ("max", "highest", "heavy", "expensive", "largest", "top"):
        return "DESC", None
    if norm in ("min", "lowest", "light", "cheapest", "smallest", "bottom"):
        return "ASC", None
    return None, "Error: sort_type must be max or min"


def _normalize_list_top_n(top_n: Optional[int]) -> tuple[int, bool]:
    capped = False
    if top_n is None or isinstance(top_n, bool):
        return _LIST_DEFAULT_TOP_N, capped
    try:
        n = int(top_n)
    except (TypeError, ValueError):
        return _LIST_DEFAULT_TOP_N, capped
    if n <= 0:
        return _LIST_DEFAULT_TOP_N, capped
    if n > _LIST_MAX_TOP_N:
        return _LIST_MAX_TOP_N, True
    return n, capped


def _normalize_category_optional(category: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if category is None or not str(category).strip():
        return None, None
    norm = str(category).strip().lower()
    if norm not in _ALLOWED_CATEGORIES:
        allowed = ", ".join(sorted(_ALLOWED_CATEGORIES))
        return None, f"Error: unknown category {category!r}; allowed: {allowed}"
    return norm, None


def _format_notes_part(notes: Optional[str]) -> str:
    if notes is None:
        return "none"
    notes_display = str(notes).replace('"', '\\"')
    return f"\"{notes_display}\""


async def tool_add_expense(
    occurred_at: str,
    category: str,
    amount: Optional[Union[int, float, str, Decimal]] = None,
    *,
    currency: str = "USD",
    notes: Optional[str] = None,
) -> str:
    """Insert one expense row. Returns a fixed-format string for the agent/LLM.

    ``occurred_at`` must be ISO ``YYYY-MM-DD`` (agent resolves natural language).
    ``amount`` is in major currency units (e.g. ``12.50``); converted to integer cents inside.

    ``occurred_at`` must not be after **today's calendar date in UTC** (computed inside; not
    passed by the caller).
    """

    ref_day = datetime.now(timezone.utc).date()

    try:
        occurred_day = _parse_iso_date_strict(occurred_at)
    except ValueError:
        return "Error: invalid occurred_at"

    if occurred_day > ref_day:
        return f"Error: occurred_at cannot be after {ref_day.isoformat()} (UTC)"

    if category is None or not str(category).strip():
        return "Error: missing category"
    cat_norm = str(category).strip().lower()
    if cat_norm not in _ALLOWED_CATEGORIES:
        allowed = ", ".join(sorted(_ALLOWED_CATEGORIES))
        return f"Error: unknown category {category!r}; allowed: {allowed}"

    cur = (currency or "USD").strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(cur):
        return f"Error: invalid currency {currency!r} (use 3-letter ISO, e.g. USD)"

    if notes is not None and len(notes) > 255:
        return "Error: notes exceed 255 characters"

    if amount is None or isinstance(amount, bool):
        return "Error: missing amount"
    try:
        cents = _major_units_to_cents(amount)
    except ValueError:
        return "Error: invalid amount"

    if cents <= 0:
        return "Error: amount must be positive"

    sql_notes: Optional[str] = None if notes is None else str(notes)

    try:
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    INSERT INTO expenses (occurred_at, amount, currency, category, notes)
                    VALUES (:occurred_at, :amount, :currency, :category, :notes)
                    """
                ),
                {
                    "occurred_at": occurred_day.isoformat(),
                    "amount": cents,
                    "currency": cur,
                    "category": cat_norm,
                    "notes": sql_notes,
                },
            )
            new_id = getattr(result, "lastrowid", None)
            if not new_id:
                last_id = await conn.execute(text("SELECT LAST_INSERT_ID()"))
                new_id = last_id.scalar_one()

            notes_display = "" if sql_notes is None else sql_notes.replace('"', '\\"')
            notes_part = "none" if sql_notes is None else f'"{notes_display}"'
            money = _format_observation_money(cents, cur)
            return (
                f"Logged expense id={new_id}: {money} on {occurred_day.isoformat()}, "
                f"category={cat_norm}, notes={notes_part}."
            )
    except (SQLAlchemyError) as e:
        return f"Error: database {e}"

async def tool_analyze_text_and_action(text: str) -> str:
    from llm import call_LLM

    prompt = f"""
You can only allowed to perform these actions. Nothing outside it.
1. Fix grammatical mistakes
2. Summarize the given text
3. Rephrase text

{text}

Only return the transformed text
"""
    return call_LLM(prompt=prompt)


async def tool_summarize_expenses(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    *,
    sort_type: Optional[str] = None,
) -> str:
    """Summarize expenses in a UTC date range (inclusive).

    If start/end are omitted, defaults to the current UTC calendar week (Mon..today).
    Always returns exactly 3 ranked rows (heavy/light) depending on sort_type (max/min).
    """
    start, end, err = _resolve_date_range(start_date, end_date)
    if err:
        return err

    sort_dir, sort_err = _normalize_sort_type(sort_type)
    if sort_err:
        return sort_err

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            totals_rows = (
                await conn.execute(
                    text(
                        """
                        SELECT currency, COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total
                        FROM expenses
                        WHERE occurred_at BETWEEN :start AND :end
                        GROUP BY currency
                        ORDER BY currency ASC
                        """
                    ),
                    {"start": start.isoformat(), "end": end.isoformat()},
                )
            ).fetchall()

            if not totals_rows:
                return (
                    f"Summary {start.isoformat()}..{end.isoformat()} (UTC): "
                    "no expenses in this period."
                )

            by_cat_rows = (
                await conn.execute(
                    text(
                        """
                        SELECT currency, category, COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total
                        FROM expenses
                        WHERE occurred_at BETWEEN :start AND :end
                        GROUP BY currency, category
                        ORDER BY currency ASC, total DESC, category ASC
                        """
                    ),
                    {"start": start.isoformat(), "end": end.isoformat()},
                )
            ).fetchall()

            top_rows = (
                await conn.execute(
                    text(
                        f"""
                        SELECT occurred_at, amount, currency, category, notes
                        FROM expenses
                        WHERE occurred_at BETWEEN :start AND :end
                        ORDER BY amount {sort_dir}, occurred_at DESC
                        LIMIT {_SUMMARIZE_TOP_N}
                        """
                    ),
                    {"start": start.isoformat(), "end": end.isoformat()},
                )
            ).fetchall()

        totals_parts: list[str] = []
        for cur, cnt, total in totals_rows:
            money = _format_observation_money(int(total), str(cur))
            totals_parts.append(f"{cnt} expenses, total {money}")

        # currency -> list of (category, total, cnt) sorted by total desc from SQL
        cat_map: dict[str, list[tuple[str, int, int]]] = {}
        for cur, cat, cnt, total in by_cat_rows:
            cat_map.setdefault(str(cur), []).append((str(cat), int(total), int(cnt)))

        cat_parts: list[str] = []
        most_spent_parts: list[str] = []
        for cur in sorted(cat_map.keys()):
            entries = cat_map[cur]
            rendered = []
            for cat, total, cnt in entries:
                rendered.append(f"{cat} {_format_observation_money(total, cur)} ({cnt})")
            cat_parts.append(f"{cur}: " + "; ".join(rendered))
            top_cat, top_total, _ = entries[0]
            most_spent_parts.append(
                f"{cur} most spent: {top_cat} {_format_observation_money(top_total, cur)}"
            )

        top_label = "largest" if sort_dir == "DESC" else "smallest"
        top_parts: list[str] = []
        for occurred_at, amount, cur, cat, notes in top_rows:
            money = _format_observation_money(int(amount), str(cur))
            notes_part = _format_notes_part(notes)
            top_parts.append(
                f"{money} on {occurred_at}, category={cat}, notes={notes_part}"
            )

        return (
            f"Summary {start.isoformat()}..{end.isoformat()} (UTC): "
            + " | ".join(totals_parts)
            + ".\nBy category: "
            + " | ".join(cat_parts)
            + ".\n"
            + " | ".join(most_spent_parts)
            + f".\nTop 3 ({top_label}): "
            + "; ".join(top_parts)
            + "."
        )
    except SQLAlchemyError as e:
        return f"Error: database {e}"


async def tool_list_expenses(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    *,
    category: Optional[str] = None,
    top_n: Optional[int] = None,
    sort_type: Optional[str] = None,
) -> str:
    """List ranked expenses (top/bottom N) for a UTC date range (inclusive)."""
    start, end, err = _resolve_date_range(start_date, end_date)
    if err:
        return err

    sort_dir, sort_err = _normalize_sort_type(sort_type)
    if sort_err:
        return sort_err

    cat_norm, cat_err = _normalize_category_optional(category)
    if cat_err:
        return cat_err

    n, capped = _normalize_list_top_n(top_n)

    where = "occurred_at BETWEEN :start AND :end"
    params: dict[str, object] = {"start": start.isoformat(), "end": end.isoformat()}
    if cat_norm is not None:
        where += " AND category = :category"
        params["category"] = cat_norm

    limit = n + 1  # fetch one extra to detect "more exist"

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"""
                        SELECT occurred_at, amount, currency, category, notes
                        FROM expenses
                        WHERE {where}
                        ORDER BY amount {sort_dir}, occurred_at DESC
                        LIMIT {limit}
                        """
                    ),
                    params,
                )
            ).fetchall()

        if not rows:
            return (
                f"List {start.isoformat()}..{end.isoformat()} (UTC): no matching expenses."
            )

        more_exist = len(rows) > n
        rows = rows[:n]

        prefix = f"List {start.isoformat()}..{end.isoformat()} (UTC)"
        if cat_norm is not None:
            prefix += f", category={cat_norm}"
        prefix += ":"

        rendered = []
        for occurred_at, amount, cur, cat, notes in rows:
            money = _format_observation_money(int(amount), str(cur))
            notes_part = _format_notes_part(notes)
            rendered.append(
                f"{money} on {occurred_at}, category={cat}, notes={notes_part}."
            )

        extra = []
        if capped:
            extra.append(f"(requested {top_n}, showing {_LIST_MAX_TOP_N} max)")
        if more_exist:
            extra.append(
                "More expenses exist in this period; view the full list in the application."
            )

        tail = ""
        if extra:
            tail = "\n" + " ".join(extra)

        return prefix + "\n" + "\n".join(rendered) + tail
    except SQLAlchemyError as e:
        return f"Error: database {e}"
