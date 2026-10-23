"""Preserve provided solutions, request only missing reasoning, record actual results."""

from datetime import date, timedelta


def solution_coverage(draft):
    required, reused, conflicts = [], [], []
    for question in draft["questions"]:
        if question.get("is_context"):
            continue
        matches = [s for s in draft["solutions"] if s["question_id"] == question["id"]]
        supplied = [s for s in matches if s["origin"] != "ai"]
        complete = [s for s in supplied if s["coverage"] == "complete"]
        additions = [s for s in matches if s["origin"] == "ai"]
        if complete and additions:
            raise ValueError(f"Duplicate AI replacement of supplied complete solution: {question['id']}")
        reused.extend(s["id"] for s in supplied)
        conflicts.extend(s["id"] for s in matches if s.get("verification") == "conflict")
        if not complete and not any(s["coverage"] == "complete" for s in additions):
            required.append(question["id"])
    return {"missing": required, "reused": reused, "conflicts": conflicts}


def record_result(state, question_id, correct, note="", observed_at=None):
    if type(correct) is not bool:
        raise ValueError("correct must be boolean and describe a real student observation")
    question = next((q for q in state["draft"]["questions"] if q["id"] == question_id), None)
    if question is None or question.get("is_context"):
        raise ValueError("Unknown independent supplied question")
    observed = date.fromisoformat(observed_at) if observed_at else date.today()
    entry = {"question_id": question_id, "correct": correct, "note": note,
             "observed_at": observed.isoformat(),
             "review_due": (observed + timedelta(days=3 if correct else 1)).isoformat()}
    state["mastery_state"]["observations"].append(entry)
    for topic in question["topic_ids"]:
        state["mastery_state"]["topics"][topic] = {
            "status": "observed_correct" if correct else "needs_review", "last_observation": entry,
        }
    if not correct:
        state["error_log"]["entries"].append(entry)
    return entry
