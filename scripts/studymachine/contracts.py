"""Versioned JSON schemas plus cross-record provenance invariants."""

import re
from copy import deepcopy

from jsonschema import Draft202012Validator


def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required)}


def array(item):
    return {"type": "array", "items": item}


S = {"type": "string"}
N = {"type": "number"}
B = {"type": "boolean"}
STRINGS = array(S)
REF = obj({"source_id": S, "location": S}, ("source_id", "location"))
REFS = {**array(REF), "minItems": 1}
VERSION = {"const": 1}
TOPIC = obj({
    "id": S, "title": S, "prerequisites": STRINGS, "in_scope": B,
    "importance": {"type": "number", "minimum": 0, "maximum": 5},
    "weakness": {"type": "number", "minimum": 0, "maximum": 1},
    "estimated_minutes": {"type": "integer", "minimum": 1}, "explanation": {"type": "string", "minLength": 1},
    "definitions": STRINGS, "formulas": STRINGS, "procedures": STRINGS, "common_mistakes": STRINGS,
    "references": REFS, "evidence_kind": {"enum": ["source_backed", "ai_interpretation"]},
}, ("id", "title", "prerequisites", "in_scope", "estimated_minutes", "explanation", "references", "evidence_kind"))
QUESTION = obj({
    "id": S, "number": S, "kind": {"enum": ["historical", "exercise"]},
    "source_id": S, "location": S, "text": S, "topic_ids": STRINGS,
    "exam_id": {"type": ["string", "null"]}, "parent_id": {"type": ["string", "null"]},
    "pattern": {"type": ["string", "null"]}, "method": {"type": ["string", "null"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "needs_review": B, "is_context": B,
}, ("id", "number", "kind", "source_id", "location", "text", "topic_ids", "confidence"))
SOLUTION = obj({
    "id": S, "question_id": S, "origin": {"enum": ["official", "student", "answer_key", "ai"]},
    "coverage": {"enum": ["complete", "partial", "answer_only", "unresolved"]}, "text": S,
    "references": REFS, "verification": {"enum": ["verified", "unchecked", "conflict", "unresolved"]}, "note": S,
}, ("id", "question_id", "origin", "coverage", "text", "references", "verification"))
EXAM = obj({"id": S, "label": S, "source_id": S, "sitting_id": S, "variant": S},
           ("id", "label", "source_id", "sitting_id", "variant"))
GENERATED = obj({"id": S, "label": {"const": "AI 생성 연습문제"}, "text": S, "answer": S,
                 "explanation": S, "references": REFS},
                ("id", "label", "text", "answer", "explanation", "references"))
SOURCE = obj({
    "id": S, "filename": S, "original_path": S, "sha256": {"type": ["string", "null"]}, "file_type": S,
    "category": {"enum": ["syllabus", "lecture_slides", "textbook", "lecture_notes", "assignment",
                           "historical_exam", "official_solution", "student_solution", "answer_key", "formula_sheet", "other"]},
    "status": {"enum": ["processed", "partial", "failed"]},
    "sections": array(obj({"location": S, "text": S}, ("location", "text"))),
    "page_count": {"type": ["integer", "null"]}, "limitations": STRINGS,
    "topic_ids": STRINGS, "question_ids": STRINGS,
}, ("id", "filename", "original_path", "sha256", "file_type", "category", "status", "sections", "limitations"))
SCHEMAS = {
    "course_profile": obj({"schema_version": VERSION, "course_id": S, "subject": {"type": ["string", "null"]},
        "exam_at": {"type": ["string", "null"]}, "timezone": S, "scope": {"type": ["string", "null"]},
        "availability": {"type": ["object", "null"], "additionalProperties": {"type": "integer", "minimum": 0, "maximum": 1440}},
        "language": S, "generation_consent": {"enum": ["yes", "no", None]}}, ("schema_version", "course_id")),
    "source_manifest": obj({"schema_version": VERSION, "sources": array(SOURCE)}, ("schema_version", "sources")),
    "topic_registry": obj({"schema_version": VERSION, "topics": array(TOPIC)}, ("schema_version", "topics")),
    "exam_question_registry": obj({"schema_version": VERSION, "exams": array(EXAM), "questions": array(QUESTION)}, ("schema_version", "exams", "questions")),
    "solution_registry": obj({"schema_version": VERSION, "solutions": array(SOLUTION)}, ("schema_version", "solutions")),
    "generation_policy": obj({"schema_version": VERSION, "allowed": B, "consent": {"enum": ["yes", "no", None]},
        "historical_present": B, "unreadable_history": B, "reason": S}, ("schema_version", "allowed", "consent", "historical_present", "unreadable_history", "reason")),
    "exam_analysis": obj({"schema_version": VERSION, "exam_count": {"type": "integer", "minimum": 0},
        "sitting_count": {"type": "integer", "minimum": 0}, "question_count": {"type": "integer", "minimum": 0},
        "topics": array({"type": "object"}), "patterns": array({"type": "object"}), "limitations": STRINGS}, ("schema_version", "exam_count", "question_count", "topics")),
    "study_plan": obj({"schema_version": VERSION, "mode": S, "conditional": B, "days": array({"type": "object"}),
        "assumptions": STRINGS, "limitations": STRINGS, "unscheduled": array({})}, ("schema_version", "mode", "conditional", "days")),
    "mastery_state": obj({"schema_version": VERSION, "observations": array({"type": "object"}), "topics": {"type": "object"}}, ("schema_version", "observations", "topics")),
    "error_log": obj({"schema_version": VERSION, "entries": array({"type": "object"})}, ("schema_version", "entries")),
    "run_manifest": obj({"schema_version": VERSION, "status": {"enum": ["complete", "partial"]},
        "artifacts": array(obj({"filename": S, "source_ids": STRINGS, "status": S}, ("filename", "source_ids", "status"))),
        "generation_policy": {"type": "object"}, "limitations": STRINGS, "validation": {"type": "object"}},
        ("schema_version", "status", "artifacts", "generation_policy", "limitations", "validation")),
}
DRAFT = obj({"schema_version": VERSION, "topics": array(TOPIC), "exams": array(EXAM),
             "questions": array(QUESTION), "solutions": array(SOLUTION), "generated_questions": array(GENERATED),
             "limitations": STRINGS, "localized_documents": {"type": "object", "additionalProperties": S}},
            ("schema_version", "topics", "exams", "questions", "solutions", "generated_questions", "limitations"))

COUNT = {"type": "integer", "minimum": 0}
FRACTION = {"type": "number", "minimum": 0, "maximum": 1}
FREQUENCY = obj({"topic_id": S, "pattern": S, "exam_count": COUNT, "exam_denominator": COUNT,
                 "historical_frequency": FRACTION, "question_count": COUNT,
                 "question_denominator": COUNT, "question_share": FRACTION,
                 "sitting_count": COUNT, "sitting_denominator": COUNT, "sitting_frequency": FRACTION},
                ("exam_count", "exam_denominator", "historical_frequency", "question_count"))
BLOCK = obj({"topic_id": {"type": ["string", "null"]}, "task": S,
             "minutes": {"type": "integer", "minimum": 1}, "priority": {"type": "integer", "minimum": 1},
             "source_ids": STRINGS, "question_ids": STRINGS, "completion": S, "review": B},
            ("topic_id", "task", "minutes", "priority", "source_ids", "question_ids", "completion", "review"))
DAY = obj({"date": S, "available_minutes": {"type": ["integer", "null"], "minimum": 0, "maximum": 1440},
           "buffer_minutes": COUNT, "blocks": array(BLOCK)}, ("date", "available_minutes", "buffer_minutes", "blocks"))
SCHEMAS["exam_analysis"]["properties"]["topics"] = array(FREQUENCY)
SCHEMAS["exam_analysis"]["properties"]["patterns"] = array(FREQUENCY)
SCHEMAS["study_plan"]["properties"].update({"days": array(DAY), "start_date": S,
    "end_date": {"type": ["string", "null"]}, "unscheduled": array(obj({"topic_id": S,
        "remaining_minutes": COUNT, "reason": S}, ("topic_id", "remaining_minutes", "reason")))})


def validate(name, value):
    Draft202012Validator(DRAFT if name == "draft" else SCHEMAS[name]).validate(value)


def schema_documents():
    return {name: {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"urn:univ-studymachine:v1:{name}", **deepcopy(schema)}
            for name, schema in {**SCHEMAS, "semantic_draft": DRAFT}.items()}


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def validate_draft(draft, manifest, previous=None):
    validate("draft", draft)
    validate("source_manifest", manifest)
    sources = {s["id"]: s for s in manifest["sources"]}
    if len(sources) != len(manifest["sources"]):
        raise ValueError("Duplicate source ID")
    maps = {}
    for key in ("topics", "exams", "questions", "solutions", "generated_questions"):
        maps[key] = {item["id"]: item for item in draft[key]}
        if len(maps[key]) != len(draft[key]):
            raise ValueError(f"Duplicate IDs in {key}")
    if set(maps["generated_questions"]) & set(maps["questions"]):
        raise ValueError("Generated question IDs collide with supplied questions")

    def ref_text(ref):
        if ref["source_id"] not in sources:
            raise ValueError(f"Unknown source: {ref['source_id']}")
        sections = sources[ref["source_id"]]["sections"]
        section = next((s for s in sections if s["location"] == ref["location"]), None)
        if section is None:
            raise ValueError(f"Unknown source location: {ref}")
        return section["text"]

    for key in ("topics", "solutions", "generated_questions"):
        for item in draft[key]:
            for ref in item["references"]:
                ref_text(ref)
    for topic in draft["topics"]:
        if not set(topic["prerequisites"]) <= maps["topics"].keys():
            raise ValueError("Unknown prerequisite")
    seen = set()
    for exam in draft["exams"]:
        if exam["source_id"] not in sources or sources[exam["source_id"]]["category"] != "historical_exam":
            raise ValueError("Exam must reference an identified historical source")
    for q in draft["questions"]:
        text = ref_text(q)
        if q["text"] and normalized(q["text"]) not in normalized(text):
            raise ValueError(f"Question wording differs from original: {q['id']}")
        identity = (q["source_id"], q["location"], q["number"])
        if identity in seen:
            raise ValueError("Duplicate question identity")
        seen.add(identity)
        if not set(q["topic_ids"]) <= maps["topics"].keys():
            raise ValueError("Unknown question topic")
        if q.get("parent_id") and q["parent_id"] not in maps["questions"]:
            raise ValueError("Unknown parent question")
        if q["kind"] == "historical":
            exam = maps["exams"].get(q.get("exam_id"))
            if not exam or exam["source_id"] != q["source_id"]:
                raise ValueError("Historical question needs its original exam source")
        if sources[q["source_id"]]["category"] in ("official_solution", "student_solution", "answer_key"):
            raise ValueError("Cannot reconstruct fictional questions from solutions")
        q["needs_review"] = q.get("needs_review", False) or q["confidence"] < .7
    for solution in draft["solutions"]:
        if solution["coverage"] == "complete" and not solution["text"].strip():
            raise ValueError("Complete solution cannot be empty")
        if solution["question_id"] not in maps["questions"]:
            raise ValueError("Unmatched solution")
        if solution["origin"] != "ai":
            text = " ".join(ref_text(r) for r in solution["references"])
            if normalized(solution["text"]) not in normalized(text):
                raise ValueError("Supplied solution changed from its source")
            categories = {sources[r["source_id"]]["category"] for r in solution["references"]}
            expected = {"official": "official_solution", "student": "student_solution", "answer_key": "answer_key"}[solution["origin"]]
            if expected not in categories:
                raise ValueError("Supplied solution origin disagrees with source category")
    if previous:
        old_topics = {normalized(t["title"]): t["id"] for t in previous["topics"]}
        for topic in draft["topics"]:
            if normalized(topic["title"]) in old_topics and old_topics[normalized(topic["title"])] != topic["id"]:
                raise ValueError("Existing topic IDs must remain stable")
        old_q = {q["id"]: q for q in previous["questions"]}
        if not set(old_q) <= maps["questions"].keys():
            raise ValueError("Previously registered original questions cannot be removed")
        for q in draft["questions"]:
            if q["id"] in old_q and any(q.get(k) != old_q[q["id"]].get(k) for k in ("text", "number", "source_id", "location")):
                raise ValueError("Existing question identity is immutable")
        for original in previous["solutions"]:
            if original["origin"] == "ai":
                continue
            current = maps["solutions"].get(original["id"])
            protected = ("question_id", "origin", "coverage", "text", "references")
            if current is None or any(current.get(k) != original.get(k) for k in protected):
                raise ValueError("Previously supplied solutions must be preserved; flag discrepancies in verification/note")
    return draft
