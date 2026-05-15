# this file is responsible for understanding the output of LLM 
import json
import re

def parse_response(response: str):
    # strip markdown fences if model adds them anyway
    clean = re.sub(r"```json|```", "", response).strip()
    
    # to avoid the agent wasting a step in case the LLM returned incompatible JSON values 
    clean = clean.replace(": True", ": true")
    clean = clean.replace(": False", ": false")
    clean = clean.replace(":True", ": true")
    clean = clean.replace(":False", ": false")
   
    return json.loads(clean)