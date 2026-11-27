"""Offline evaluation of the lexical layer on ``eval/assistant-questions.json``.

A question is relevant-answered when a top-3 document is one of its expected
documents, or its title contains one of the question's keywords. Questions with
no expected documents must not be answered confidently.
"""

from __future__ import annotations

from typing import Any

from .retrieval import LexicalIndex, assess

THRESHOLDS = {"lexical_recall_at_20": 0.85, "direct_answer_relevance": 0.85}


def _relevant(doc: dict[str, Any], question: dict[str, Any]) -> bool:
    if doc["id"] in question.get("expected", []):
        return True
    return any(keyword and keyword in doc["title"] for keyword in question.get("keywords", []))


def evaluate(index: LexicalIndex, questions: list[dict[str, Any]]) -> dict[str, Any]:
    with_expected = [q for q in questions if q.get("expected")]
    unanswerable = [q for q in questions if not q.get("expected")]
    recall_hits = direct = direct_relevant = deferred = abstained = 0
    misses: list[str] = []
    for question in with_expected:
        result = assess(index, question["question"])
        top = [hit["doc"] for hit in result["hits"]]
        if any(_relevant(doc, question) for doc in top):
            recall_hits += 1
        else:
            misses.append(question["id"])
        if result["state"] == "confident":
            direct += 1
            direct_relevant += any(_relevant(doc, question) for doc in top[:3])
        else:
            deferred += 1
    for question in unanswerable:
        result = assess(index, question["question"])
        abstained += result["state"] != "confident"

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 3) if denominator else 1.0

    report = {
        "questions": len(questions),
        "lexical_recall_at_20": ratio(recall_hits, len(with_expected)),
        "recall_misses": misses,
        "direct_answers": direct,
        "direct_answer_relevance": ratio(direct_relevant, direct),
        "deferred_to_refine": deferred,
        "unanswerable": len(unanswerable),
        "unanswerable_not_answered": f"{abstained}/{len(unanswerable)}",
        "thresholds": THRESHOLDS,
    }
    report["pass"] = (
        report["lexical_recall_at_20"] >= THRESHOLDS["lexical_recall_at_20"]
        and report["direct_answer_relevance"] >= THRESHOLDS["direct_answer_relevance"]
        and abstained == len(unanswerable)
    )
    return report
