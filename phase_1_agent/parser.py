# this file is responsible for understanding the output of LLM 
import re

def parse_action(response: str):
    match = re.search(r"Action:\s*(\w+)\[(.*?)\]", response, re.DOTALL)
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2).strip()


def has_final_answer(response: str) -> bool:
    return "Final Answer:" in response