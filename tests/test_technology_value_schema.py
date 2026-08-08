import json
from pathlib import Path

from jsonschema import Draft202012Validator


def test_relevance_batch_schema_accepts_structured_technology_value():
    schema = json.loads(Path("schemas/relevance-batch.schema.json").read_text(encoding="utf-8"))
    payload = {
        "results": [
            {
                "candidate_id": "c1",
                "relevant": True,
                "score": 82,
                "reason": "存在明确的系统机制变化。",
                "fulltext_required": True,
                "technology_value": {
                    "novelty": {"score": 4, "reason": "introduces a new scheduling mechanism"},
                    "architecture_impact": {"score": 5, "reason": "changes the runtime data path"},
                    "industry_signal": {"score": 3, "reason": "supported by a primary platform artifact"},
                    "project_alignment": {"score": 5, "reason": "changes a current design hypothesis"}
                }
            }
        ]
    }
    Draft202012Validator(schema).validate(payload)


def test_relevance_batch_schema_remains_backward_compatible_for_unfinished_runs():
    schema = json.loads(Path("schemas/relevance-batch.schema.json").read_text(encoding="utf-8"))
    payload = {
        "results": [
            {
                "candidate_id": "legacy",
                "relevant": True,
                "score": 80,
                "reason": "legacy unfinished run",
                "fulltext_required": True
            }
        ]
    }
    Draft202012Validator(schema).validate(payload)
