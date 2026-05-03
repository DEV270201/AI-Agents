# this file is responsible for running the main loop for agents 

from tools import tool_analyze_text_and_action, tool_calculator, tool_get_user_profile
from llm import call_LLM
from parser import has_final_answer, parse_action

TOOLS = {
    "calculator": tool_calculator,
    "public_api_user_profile": tool_get_user_profile,
    "text_fixer": tool_analyze_text_and_action
}

SYSTEM_PROMPT = """You are an AI agent that reasons step by step and uses tools.

Available tools:
- calculator(expression)                 → evaluates math like 5*7 or 100/4
- public_api_user_profile(user_id)         → fetches data from an external API
- text_fixer(text)                       → summarizes, fixes and rephrases text

STRICT RULES:
1. Use ONE tool per step, then WAIT for the Observation.
2. Once you have enough information, you MUST write Final Answer.
3. Do NOT call a tool again if you already have the result.
4. Do NOT invent Observations. Wait for them.

Format (follow EXACTLY):
Thought: your reasoning
Action: tool_name[input]

After receiving the Observation, either call another tool OR write:
Final Answer: your answer to the user
"""

def run_agent(user_input: str) -> str:
    context = SYSTEM_PROMPT + f"\nUSER: {user_input}\n"
    
    # this loop is to prevent the agent from running indefinitely 
    for step in range(5):
        print(f"\n--- Step {step + 1} ---")

        response = call_LLM(prompt=context)
        print(f"LLM output:\n{response}\n")

        if has_final_answer(response):
            return response
        
        tool_name, tool_input = parse_action(response)

        if tool_name is None:
            #LLM is not following the format. Give feedback
            context += f"\n{response}\nObservation: Please follow the format exactly: Action: tool_name[input]\n"
            continue

        if tool_name not in TOOLS:
            context += f"\n{response}\nObservation: Unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}\n"
            continue

        # Execute the tool
        result = TOOLS[tool_name](tool_input)
        print(f"Tool '{tool_name}' returned: {result}")

        context += f"\n{response}\nObservation: {result}\n"
    
    return "Max steps reached without a final answer."


def main():
   if __name__ == "__main__":
    queries = [
        "What is 25 * 13?",
        "rephrase this text: I Devansh. I play cricket. I like bowling fast",
        "Fetch user information from external API for user id: 1",
        "'Fix the grammar: She do not like the food' and calculate 10+20",
    ]
    for q in queries:
        print(f"\n{'='*50}")
        print(f"Query: {q}")
        print(f"{'='*50}")
        print(run_agent(q))

if __name__ == "__main__":
    main()