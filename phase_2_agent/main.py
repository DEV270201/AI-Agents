# this file is responsible for running the main loop for agents 

from tools import tool_analyze_text_and_action, tool_calculator, tool_get_user_profile
from llm import call_LLM
from parser import parse_response
from memory import load_memory, save_memory
import json

TOOLS = {
    "calculator": tool_calculator,
    "public_api_user_profile": tool_get_user_profile,
    "text_fixer": tool_analyze_text_and_action
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
- calculator(expression)                 → evaluates math like 5*7 or 100/4 ... args: {"expression": "math expression like 25*13"}
- public_api_user_profile(user_id)       → fetches data from an external API ...  args: {"user_id": "the numeric id like 1"} 
- text_fixer(text)                       → summarizes, fixes and rephrases text ... args: {"text": "the text to fix or rephrase"}

STRICT RULES:
- ONE JSON per response, nothing before or after it
- Every JSON must have the "done" field set to true or false
- If the user asks for multiple things, do one task per step using separate tool calls
- Only SET done:True after ALL tasks are completed, not after just one
- When done:True, your answer must include results from ALL tasks
- Do not call the same tool twice with the same input
- If the MEMORY block above contains relevant facts about the user, use them in your answers

"""

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
    # queries = [
    #     "What is 25 * 13?",
    #     "rephrase this text: I Devansh. I play cricket. I like bowling fast",
    #     "Fetch user information from external API for user id: 2",
    #     "'Fix the grammar: Jennifer is a girl. She do not like the food' and calculate 10+20",
    # ]
    # for q in queries:
    #     print(f"\n{'='*50}")
    #     print(f"Query: {q}")
    #     print(f"{'='*50}")
        # print(run_agent(q))

    memory_block = load_memory()
    if memory_block:
        print("[memory] Loaded memory from previous sessions.\n")
        system_prompt = memory_block + "\n" + BASE_SYSTEM_PROMPT
    else:
        print("[memory] No previous memory found. Starting fresh.\n")
        system_prompt = BASE_SYSTEM_PROMPT
 
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