import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import parse_response, response_contains_model_observation


def test_single_json() -> None:
    raw = '{"thought": "x", "tool": "add_expense", "args": {}, "done": false}'
    data = parse_response(raw)
    assert data["tool"] == "add_expense"
    assert data["done"] is False


def test_first_json_when_multiple() -> None:
    raw = """{"thought": "log movie", "tool": "add_expense", "args": {"amount": 12}, "done": false}
Observation: Tool 'add_expense' returned -> Logged expense id=5: $12.00 USD
{"thought": "done", "tool": null, "args": null, "done": true, "answer": "ok"}"""
    data = parse_response(raw)
    assert data["tool"] == "add_expense"
    assert data["done"] is False


def test_strips_hallucinated_observation_before_parse() -> None:
    raw = """{"thought": "log", "tool": "add_expense", "args": {}, "done": false}
Observation: Tool 'add_expense' returned -> fake"""
    data = parse_response(raw)
    assert data["tool"] == "add_expense"


def test_response_contains_model_observation() -> None:
    assert response_contains_model_observation("Observation: foo")
    assert not response_contains_model_observation('{"done": true}')


if __name__ == "__main__":
    test_single_json()
    test_first_json_when_multiple()
    test_strips_hallucinated_observation_before_parse()
    test_response_contains_model_observation()
    print("All parser tests passed.")
