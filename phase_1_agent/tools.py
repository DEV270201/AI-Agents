import requests
from typing import Optional
import random 
import time
from llm import call_LLM

USER_URL="https://jsonplaceholder.typicode.com/users"

def _add_jitter() -> float:
    jitter_time = random.uniform(0.1, 1.5)
    return jitter_time


def tool_calculator(expression: str):
    try:
        return str(eval(expression))
    except Exception as e:
        print("Error while performing some calculations: ", str(e))
        return f"Error: {str(e)}"
    

def tool_get_user_profile(user_id: int, timeout: int = 5, retries: int = 2) -> Optional[dict]:
    for attempt in range(retries+1):
        try:
            response = requests.request(
                method="GET",
                url=f"{USER_URL}/{user_id}",
                timeout=timeout
            )
        
            # I will raise error if the status code is not in 200s 
            response.raise_for_status()

            return response.json()
        
        except requests.exceptions.Timeout:
            print(f"Attempt {attempt+1} | Timeout error occurred ....")
            sleep_time = _add_jitter()
            print(f"Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        except requests.exceptions.ConnectionError:
            print(f"Attempt {attempt+1} | Connection error occurred ....")
            sleep_time = _add_jitter()
            print(f"Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        except requests.exceptions.HTTPError as e:
            print(f"Attempt {attempt+1} | HTTP error: {str(e)} ....")
            break
        
        except ValueError:
            print(f"Attempt {attempt+1} | Invalid JSON response ....")
            break
        
        return None


def tool_analyze_text_and_action(text: str)-> str:
    prompt = f"""   
You can only allowed to perform these actions. Nothing outside it.
1. Fix grammatical mistakes
2. Summarize the given text
3. Rephrase text

{text}

Only return the transformed text
"""
    return call_LLM(prompt=prompt)




