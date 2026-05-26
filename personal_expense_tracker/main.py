# this file is responsible for running the main loop for agents

import asyncio
import json
import re
from datetime import datetime, timezone

from dotenv import load_dotenv

from db import init_db
from llm import call_LLM
from memory import load_memory, save_memory
from parser import parse_response, response_contains_model_observation
from tools import (
    tool_add_expense,
    tool_analyze_text_and_action,
)

TOOLS = {
    "text_fixer": tool_analyze_text_and_action,
    "add_expense": tool_add_expense,
}

_LOGGED_EXPENSE_MARKER = "Logged expense id="
_AMOUNT_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:bucks?|dollars?|usd|\$)",
    re.IGNORECASE,
)

BASE_SYSTEM_PROMPT = """You are an agent. Respond ONLY with single raw JSON.

CRITICAL: Output ONE single JSON object per response. Nothing else.
Do not write explanations. Do not show what comes next. Do not write multiple JSONs.
Never write lines starting with "Observation:" — only the application adds those after tools run.
Just one JSON object and nothing else.

USE this Schema when using a tool:
{"thought": "...", "tool": "tool_name", "args": {"key":"value"}, "done": false}

USE this Schema when you already have the answer:
{"thought": "...", "tool": null, "args": null, "done": true, "answer": "..."}

Available tools:
- text_fixer(text)                       → summarizes, fixes and rephrases text ... args: {"text": "the text to fix or rephrase"}
- add_expense(occurred_at, category, amount, currency?, notes?)
                                         → logs one expense; required: occurred_at (ISO YYYY-MM-DD), category (food, entertainment, bills, shopping, travel) if it fits and amount; optional: currency (default USD), notes (short context: where/what/how e.g. merchant or activity); resolve today/yesterday/last week/last month from the UTC reference line to a specific ISO date
                                         args: {"occurred_at": "2026-05-15", "category": "food", "amount": 12.50, "currency": "USD", "notes": "Starbucks"}

STRICT RULES:
- ONE JSON per response, nothing before or after it
- Every JSON must have the "done" field set to true or false
- If the user asks for multiple things, do one task per step using separate tool calls
- Only SET done:true after ALL tasks are completed, not after just one
- Only SET done:true after you see Observation lines confirming each add_expense succeeded
- When done:true, your answer must include results from ALL tasks
- If the MEMORY block above contains relevant facts about the user, use them in your answers
- For add_expense: use JSON keys occurred_at, category, amount (and optional currency, notes); resolve dates to ISO using the UTC reference before calling; read the Observation and confirm to the user on success; on Error, fix or ask — do not claim the expense was logged; never pass slash dates or words in args; if the date cannot be resolved to one ISO date, ask the user for day, month, and year before calling

"""


def _utc_reference_line() -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    print(f"UTC reference (expense dates): today's calendar date is {today}.\n")
    return f"UTC reference (expense dates): today's calendar date is {today}.\n"


def build_system_prompt(memory_block: str = "") -> str:
    parts = []
    if memory_block:
        parts.append(memory_block)
    parts.append(BASE_SYSTEM_PROMPT)
    parts.append(_utc_reference_line())
    return "\n".join(parts)


def _expected_expense_log_count(user_input: str) -> int | None:
    """Heuristic: how many separate expenses the user mentioned (if detectable)."""
    amounts = _AMOUNT_PATTERN.findall(user_input)
    if len(amounts) >= 2:
        return len(amounts)
    if re.search(r"\banother\b", user_input, re.IGNORECASE) and len(amounts) == 1:
        return 2
    return None


def _successful_expense_log_count(task_context: str) -> int:
    return task_context.count(_LOGGED_EXPENSE_MARKER)


def _premature_done_message(user_input: str, task_context: str) -> str | None:
    """Return a correction Observation if done:true is not allowed yet."""
    expected = _expected_expense_log_count(user_input)
    if expected is None:
        return None
    actual = _successful_expense_log_count(task_context)
    if actual < expected:
        return (
            f"You set done:true but only {actual}/{expected} expenses have a successful "
            f"'{_LOGGED_EXPENSE_MARKER}' Observation. Call add_expense once per remaining "
            "expense, then set done:true."
        )
    return None


# user_input -> task given by the user
# system_prompt -> memory + base system prompt
async def run_agent(user_input: str, system_prompt: str) -> str:
    main_context = system_prompt

    task_context = f"\nUSER: {user_input}\n"

    # this loop is to prevent the agent from running indefinitely
    for step in range(5):
        print(f"\n--- Step {step + 1} ---")

        response = call_LLM(prompt=main_context + task_context)
        print(f"LLM output:\n{response}\n")

        try:
            data = parse_response(response)
        except json.JSONDecodeError as error:
            print("ERROR:  => ", str(error))
            task_context += (
                f"\n{response}\nObservation: Invalid JSON. "
                "Respond with exactly one raw JSON object and nothing else.\n"
            )
            continue

        print(f"Thought: {data.get('thought')}")

        if data.get("done"):
            if response_contains_model_observation(response):
                task_context += (
                    f"\n{response}\nObservation: Do not include 'Observation:' lines in "
                    "your output. Respond with exactly one JSON object only.\n"
                )
                continue

            premature = _premature_done_message(user_input, task_context)
            if premature:
                task_context += f"\n{response}\nObservation: {premature}\n"
                continue

            return data.get("answer", "No answer provided."), task_context

        tool_name = data.get("tool")
        args = data.get("args", {})

        if not tool_name or tool_name not in TOOLS:
            task_context += (
                f"\n{response}\nObservation: Unknown tool '{tool_name}'. "
                f"Available: {list(TOOLS.keys())}\n"
            )
            continue

        # Execute the tool
        result = await TOOLS[tool_name](**args)
        print(f"Tool '{tool_name}' returned: {result}")

        task_context += f"\n{response}\nObservation: Tool '{tool_name}' returned -> {result}\n"

    return "Max steps reached without a final answer.", task_context


async def main():

    # load memory from previous sessions
    memory_block = load_memory()
    if memory_block:
        print("[memory] Loaded memory from previous sessions.\n")
    else:
        print("[memory] No previous memory found. Starting fresh.\n")
    system_prompt = build_system_prompt(memory_block)

    full_session_context = ""  # accumulates all queries this session

    print("Agent ready. Type your query (or 'quit' to exit).\n")
    while True:
        user_input = (await asyncio.to_thread(input, "You: ")).strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break

        print(f"\n{'='*50}")
        answer, context = await run_agent(user_input, system_prompt)
        full_session_context += context  # accumulate across queries
        print(f"\nAgent: {answer}")
        print(f"{'='*50}\n")

    if full_session_context:
        save_memory(full_session_context)
    print("\nSession ended. Goodbye.")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
