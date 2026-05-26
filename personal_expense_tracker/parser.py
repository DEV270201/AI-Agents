# this file is responsible for understanding the output of LLM
import json
import re


def _normalize_json_literals(text: str) -> str:
    """Map Python-style booleans to JSON booleans."""
    text = text.replace(": True", ": true")
    text = text.replace(": False", ": false")
    text = text.replace(":True", ": true")
    text = text.replace(":False", ": false")
    return text


def _strip_model_observation_lines(text: str) -> str:
    """Remove lines the model must not emit (only the app adds Observations)."""
    return re.sub(r"^Observation:.*$", "", text, flags=re.MULTILINE).strip()


def parse_response(response: str) -> dict:
    """Parse the first JSON object from an LLM response.

    Handles markdown fences, Python-style booleans, hallucinated Observation lines,
    and multiple JSON objects in one reply (uses only the first object).
    """
    clean = re.sub(r"```json|```", "", response).strip()
    clean = _strip_model_observation_lines(clean)
    clean = _normalize_json_literals(clean)

    start = clean.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", clean, 0)

    decoder = json.JSONDecoder()
    data, _end = decoder.raw_decode(clean, start)
    if not isinstance(data, dict):
        raise json.JSONDecodeError("Expected a JSON object", clean, start)
    return data


def response_contains_model_observation(response: str) -> bool:
    """True if the model echoed an Observation line (invalid output)."""
    return bool(re.search(r"^Observation:", response, flags=re.MULTILINE))
