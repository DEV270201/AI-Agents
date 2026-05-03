# this file is responsible for talking with the LLM 

import requests

OLLAMA_URL="http://localhost:11434/api/generate"
LLM_MODEL="phi3"

def call_LLM(prompt: str, timeout: int = 60) -> str:
    try:
        # for attempt in range(retries+1):
            response = requests.post(
            OLLAMA_URL,
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                 "options": {
                "stop": ["Observation:"]  # ← stop HERE, let your code write the observation
            }
            },

            timeout=timeout
            )
            
            # I will raise error if the status code is not in 200s 
            response.raise_for_status()
            data = response.json()

            return data.get("response", "").strip()
    
    except requests.exceptions.Timeout:
        print("Error: LLM request timed out ....")
        return "Error: LLM request timed out ...."
    
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Ollama ....")
        return "Error: Could not connect to Ollama. Is it running?"

    except Exception as e:
        print(f"Error: {str(e)}")
        return f"Error: {str(e)}"