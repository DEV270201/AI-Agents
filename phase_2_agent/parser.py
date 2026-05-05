# this file is responsible for understanding the output of LLM 
import json
import re

def parse_response(response: str):
    # strip markdown fences if model adds them anyway
   clean = re.sub(r"```json|```", "", response).strip()
   return json.loads(clean)