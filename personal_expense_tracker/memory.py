# this file helps the agent in retain its memory

import json
import requests
from datetime import datetime
from pathlib import Path as path
from llm import call_LLM
from parser import parse_response

cwd = path.cwd()
DATA_DIR = rf"{cwd}\memory"
data_dir = path(DATA_DIR)
MEMORY_FILE = "memory.json"
memory_file_path = path(fr'{DATA_DIR}\{MEMORY_FILE}')

def load_memory() -> str:
    # Reads memory.json and returns a formatted string ready to be prepended to the system prompt.  Returns "" on first run.
    if not memory_file_path.exists():
        return ""
    
    with open(memory_file_path, "r", encoding='utf-8') as f:
        data = json.load(f)
    
    facts = data.get("facts", [])
    history = data.get("history", [])

    if not facts and not history:
        return ""
    
    parts = ["=== MEMORY FROM PREVIOUS SESSIONS ==="]
    
    if facts:
        parts.append("Known facts about the User: ")
        for fact in facts:
            parts.append(f"  - {fact}")
        
    if history:
        parts.append("Recent session summaries:")
        for entry in history[-5:]:          # only last 5 sessions
            parts.append(f"  - {entry}")
    
    parts.append("=== END OF MEMORY ===\n")
    return "\n".join(parts)


def extract_facts(context: str) -> dict:

#    Sends the full session context to the LLM and asks it to pull out facts worth remembering.  Returns {"facts": [...], "summary": "..."}.
    prompt = f"""You are a memory extraction assistant.
 
Read the conversation below and extract information worth remembering for future sessions.
 
Extract ONLY:
- Identity facts (name, location, job, age)
- USER preferences (food, lifestyle, programming languages, models, frameworks, APIs)
- Decisions the user made ("chose X over Y")
- Results of queries the user asked about
 
IGNORE:
- Pleasantries and filler ("ok", "thanks", "got it")
- Intermediate reasoning steps
- Anything already obvious from context
- Anything that is not a fact or preference of the user
- Do not record any expenses, transactions, or financial information
 
Respond with ONLY a raw JSON object. NO markdown, NO explanation outside the JSON:
{{
  "facts": ["fact 1", "fact 2"],
  "summary": "one sentence describing what this session was about"
}}
 
CONVERSATION:
{context}
"""
    raw = call_LLM(prompt)

    if "Error" in raw:
         return {"facts": [], "summary": ""}
 
    try:
        clean = parse_response(raw)
        return clean
    except json.JSONDecodeError:
        print(f"[memory] extract_facts: could not parse JSON — got:\n{raw}")
        return {"facts": [], "summary": ""}


def save_memory(context: str) -> None:
    # 1. Calls extract_facts() to get new facts + a session summary.
    # 2. Merges them into memory.json (deduplicates facts, appends summary).
    
    print("\n[memory] Extracting facts from this session...")
    extracted = extract_facts(context)
 
    new_facts   = extracted.get("facts", [])
    new_summary = extracted.get("summary", "")
 
    # load existing memory (or start fresh)
    if memory_file_path.exists():
        with open(memory_file_path, "r") as f:
            data = json.load(f)
    else:
        data = {"facts": [], "history": []}
 
    existing_facts = data.get("facts", [])
    existing_history = data.get("history", [])
 
    # merge facts — only add ones that aren't already stored
    for fact in new_facts:
        if fact not in existing_facts:
            existing_facts.append(fact)
 
    # append session summary with a timestamp
    if new_summary:
        dated = f"[{datetime.now().strftime('%Y-%m-%d')}] {new_summary}"
        existing_history.append(dated)
 
    data["facts"]   = existing_facts
    data["history"] = existing_history
 
    with open(memory_file_path, "w") as f:
        json.dump(data, f, indent=2)
 
    print(f"[memory] Saved {len(new_facts)} new fact(s). memory.json updated.")





