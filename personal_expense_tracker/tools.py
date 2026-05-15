import random
import re
import sqlite3
import time
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional, Union
from db import get_connection, init_db

_ALLOWED_CATEGORIES = frozenset(
    {"food", "bills", "entertainment", "shopping", "travel"}
)
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


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


def tool_add_expense(
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

    connection = get_connection()
    try:
        ref_day = datetime.now(timezone.utc).date()

        try:
            occurred_day = _parse_iso_date_strict(occurred_at)
        except ValueError:
            return "Error: invalid occurred_at"

        if occurred_day > ref_day:
            return (
                f"Error: occurred_at cannot be after {ref_day.isoformat()} (UTC)"
            )

        if category is None or not str(category).strip():
            return "Error: missing category"
        cat_norm = str(category).strip().lower()
        if cat_norm not in _ALLOWED_CATEGORIES:
            allowed = ", ".join(sorted(_ALLOWED_CATEGORIES))
            return (
                f"Error: unknown category {category!r}; "
                f"allowed: {allowed}"
            )

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

        cur_sql = connection.cursor()
        cur_sql.execute(
            """
            INSERT INTO expenses (occurred_at, amount, currency, category, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (occurred_day.isoformat(), cents, cur, cat_norm, sql_notes),
        )
        connection.commit()
        new_id = cur_sql.lastrowid

        notes_display = "" if sql_notes is None else sql_notes.replace('"', '\\"')
        notes_part = "none" if sql_notes is None else f'"{notes_display}"'
        money = _format_observation_money(cents, cur)
        return (
            f"Logged expense id={new_id}: {money} on {occurred_day.isoformat()}, "
            f"category={cat_norm}, notes={notes_part}."
        )
    except sqlite3.Error as e:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
        return f"Error: database {e}"
    finally:
        connection.close()

def tool_analyze_text_and_action(text: str) -> str:
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
