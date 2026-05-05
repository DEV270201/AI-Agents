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
- Use ONE tool per step, then WAIT for the Observation
- After getting an Observation, Analyze it and if you have the answer return Final Answer IMMEDIATELY
- Do NOT call a tool again if you already have the result
- Do NOT invent Observation. Wait for them (it will be provided to you)


EXAMPLE 1 — single tool:

User: What is 10 + 5?
Thought: I need to calculate 10 + 5.
Action: calculator[10+5]
Observation: Tool calculator returned -> 15
Thought: I have the answer. The answer is 15
Final Answer: 10 + 5 = 15

---
EXAMPLE 2 — two tools in sequence:

User: Fix grammar and calculate 3*4: she do not like food
Thought: I need to fix the grammar first.
Action: text_fixer[she do not like food]
Observation: Tool text_fixer returned -> She does not like food.
Thought: Grammar is fixed. Now I need to calculate 3*4.
Action: calculator[3*4]
Observation: Tool calculator returned -> 12
Thought: Both tasks are done. I have all the answers.
Final Answer: Corrected sentence: She does not like food. And 3 * 4 = 12.

---
EXAMPLE 3 — api call, then conclude immediately:

User: Fetch user with id 1
Thought: I need to fetch user data for id 1.
Action: public_api_user_profile[1]
Observation: Tool public_api_user_profile returned -> Name: Leanne Graham, Email: Sincere@april.biz
Thought: I have the user data. I do not need any more tools.
Final Answer: User 1 is Leanne Graham, email: Sincere@april.biz.

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