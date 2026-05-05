# this file is responsible for running the main loop for agents 

from tools import tool_analyze_text_and_action, tool_calculator, tool_get_user_profile
from llm import call_LLM
from parser import parse_response
import json

TOOLS = {
    "calculator": tool_calculator,
    "public_api_user_profile": tool_get_user_profile,
    "text_fixer": tool_analyze_text_and_action
}

SYSTEM_PROMPT = """You are an agent. Respond ONLY with single raw JSON.

CRITICAL: Output ONE single JSON object per response. Nothing else.
Do not write explanations. Do not show what comes next. Do not write multiple JSONs.
Just one JSON object and nothing else.

USE this Schema when using a tool:
{"thought": "...", "tool": "tool_name", "args": {"key":"value"}, "done": False}

USE this Schema when you already have the answer:
{"thought": "...", "tool": null, "args": null, "done": True, "answer": "..."}

Available tools:
- calculator(expression)                 → evaluates math like 5*7 or 100/4 ... args: {"expression": "math expression like 25*13"}
- public_api_user_profile(user_id)       → fetches data from an external API ...  args: {"user_id": "the numeric id like 1"} 
- text_fixer(text)                       → summarizes, fixes and rephrases text ... args: {"text": "the text to fix or rephrase"}

STRICT RULES:
- ONE JSON per response, nothing before or after it
- Every JSON must have the "done" field set to True or False
- If the user asks for multiple things, do one task per step using separate tool calls
- Only SET done:True after ALL tasks are completed, not after just one
- When done:True, your answer must include results from ALL tasks
- Do not call the same tool twice with the same input

"""

def run_agent(user_input: str) -> str:
    context = SYSTEM_PROMPT + f"\nUSER: {user_input}\n"
    
    # this loop is to prevent the agent from running indefinitely 
    for step in range(5):
        print(f"\n--- Step {step + 1} ---")

        response = call_LLM(prompt=context)
        print(f"LLM output:\n{response}\n")

        try:
            data = parse_response(response)
        except json.JSONDecodeError:
            context += f"\n{response}\nObservation: Invalid JSON. You must respond with raw JSON only.\n"
            continue

        print(f"Thought: {data.get('thought')}")

        # clean exit
        if data.get("done"):
            return data.get("answer", "No answer provided.")

        tool_name = data.get("tool")
        args = data.get("args", {})

        if not tool_name or tool_name not in TOOLS:
            context += f"\n{response}\nObservation: Unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}\n"
            continue

        # Execute the tool
        result = TOOLS[tool_name](**args)
        print(f"Tool '{tool_name}' returned: {result}")

        context += f"\n{response}\nObservation: Tool '{tool_name}' returned -> {result}\n"
    
    return "Max steps reached without a final answer."


def main():
    queries = [
        "What is 25 * 13?",
        "rephrase this text: I Devansh. I play cricket. I like bowling fast",
        "Fetch user information from external API for user id: 2",
        "'Fix the grammar: Jennifer is a girl. She do not like the food' and calculate 10+20",
    ]
    for q in queries:
        print(f"\n{'='*50}")
        print(f"Query: {q}")
        print(f"{'='*50}")
        print(run_agent(q))

if __name__ == "__main__":
    main()