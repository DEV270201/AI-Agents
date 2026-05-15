# this file is responsible for running the main loop for agents

from datetime import datetime, timezone
import json

from llm import call_LLM
from memory import load_memory, save_memory
from parser import parse_response
from tools import (
    tool_add_expense,
    tool_analyze_text_and_action,
)

TOOLS = {
    "text_fixer": tool_analyze_text_and_action,
    "add_expense": tool_add_expense,
}

BASE_SYSTEM_PROMPT = """You are an agent. Respond ONLY with single raw JSON.

CRITICAL: Output ONE single JSON object per response. Nothing else.
Do not write explanations. Do not show what comes next. Do not write multiple JSONs.
Just one JSON object and nothing else.

USE this Schema when using a tool:
{"thought": "...", "tool": "tool_name", "args": {"key":"value"}, "done": False}

USE this Schema when you already have the answer:
{"thought": "...", "tool": null, "args": null, "done": True, "answer": "..."}

Available tools:
- text_fixer(text)                       → summarizes, fixes and rephrases text ... args: {"text": "the text to fix or rephrase"}
- add_expense(occurred_at, category, amount, currency?, notes?)
                                         → logs one expense; required: occurred_at (ISO YYYY-MM-DD), category (food, entertainment, bills, shopping, travel) if it fits and amount; optional: currency (default USD), notes (short context: where/what/how e.g. merchant or activity); resolve today/yesterday/last week/last month from the UTC reference line to a specific ISO date
                                         args: {"occurred_at": "2026-05-15", "category": "food", "amount": 12.50, "currency": "USD", "notes": "Starbucks"}

STRICT RULES:
- ONE JSON per response, nothing before or after it
- Every JSON must have the "done" field set to true or false
- If the user asks for multiple things, do one task per step using separate tool calls
- Only SET done:True after ALL tasks are completed, not after just one
- When done:True, your answer must include results from ALL tasks
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

# user_input -> task given by the user
# system_prompt -> memory + base system prompt 
def run_agent(user_input: str, system_prompt: str) -> str:
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
            task_context += f"\n{response}\nObservation: Invalid JSON. You must respond with raw JSON only.\n"
            continue

        print(f"Thought: {data.get('thought')}")

        # clean exit
        if data.get("done"):
            return data.get("answer", "No answer provided."), task_context

        tool_name = data.get("tool")
        args = data.get("args", {})

        if not tool_name or tool_name not in TOOLS:
            task_context += f"\n{response}\nObservation: Unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}\n"
            continue

        # Execute the tool
        result = TOOLS[tool_name](**args)
        print(f"Tool '{tool_name}' returned: {result}")

        task_context += f"\n{response}\nObservation: Tool '{tool_name}' returned -> {result}\n"

    return "Max steps reached without a final answer.", task_context


def main():
    # load memory from previous sessions
    memory_block = load_memory()
    if memory_block:
        print("[memory] Loaded memory from previous sessions.\n")
    else:
        print("[memory] No previous memory found. Starting fresh.\n")
    system_prompt = build_system_prompt(memory_block)
 
    full_session_context = ""           # accumulates all queries this session
 
    print("Agent ready. Type your query (or 'quit' to exit).\n")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break
 
        print(f"\n{'='*50}")
        answer, context = run_agent(user_input, system_prompt)
        full_session_context += context   # accumulate across queries
        print(f"\nAgent: {answer}")
        print(f"{'='*50}\n")
 
    if full_session_context:
        save_memory(full_session_context)
    print("\nSession ended. Goodbye.")


if __name__ == "__main__":
    main()