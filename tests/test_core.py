"""Policy, state and intake invariants without a simulated language engine."""

import json

import pytest

from studymachine.contracts import schema_documents, validate
from studymachine.intake import apply_answers, intake_batch
from studymachine.learning import solution_coverage
from studymachine.policy import GenerationPolicy, PolicyViolation
from studymachine.state import load_state, private_root, save_json
from studymachine import workflow


def manifest(history=False, status="processed"):
    return {"schema_version": 1, "sources": [{"id": "source", "filename": "exam.pdf" if history else "notes.txt",
        "original_path": "source", "sha256": None, "file_type": "pdf" if history else "txt",
        "category": "historical_exam" if history else "lecture_notes", "status": status,
        "sections": [{"location": "page:1", "text": "자료"}] if status == "processed" else [], "limitations": []}]}


@pytest.mark.parametrize("history,status,consent,allowed", [
    (True, "processed", "yes", False), (True, "failed", "yes", False),
    (False, "processed", "yes", True), (False, "processed", "no", False),
    (False, "processed", None, False),
])
def test_central_policy(history, status, consent, allowed):
    policy = GenerationPolicy.evaluate(manifest(history, status), consent=consent)
    assert policy.allowed is allowed
    validate("generation_policy", policy.to_dict())
    if not allowed:
        with pytest.raises(PolicyViolation):
            policy.assert_generation([{"text": "unauthorized"}])


def test_historical_question_blocks_misclassified_source():
    p = GenerationPolicy.evaluate(manifest(), [{"kind": "historical"}], "yes")
    assert not p.allowed


def test_intake_one_batch_max_eight_known_values_suppressed():
    batch = intake_batch({}, manifest())
    assert len(batch) == 8
    assert sum(q["field"] == "generation_consent" for q in batch) == 1
    known = {"subject": "미적분", "exam_at": "2030-10-20", "scope": "1장", "format": "계산"}
    assert not set(known) & {q["field"] for q in intake_batch(known, manifest())}
    assert "generation_consent" not in {q["field"] for q in intake_batch({}, manifest(True, "failed"))}


def test_unanswered_permission_never_becomes_consent():
    assert apply_answers({}, {}) .get("generation_consent") is None
    assert apply_answers({}, {"generation_consent": "예"})["generation_consent"] == "yes"
    with pytest.raises(ValueError):
        apply_answers({}, {"generation_consent": "maybe"})


def test_answer_key_needs_reasoning_and_official_not_replaced():
    d = {"questions": [{"id": "q1"}, {"id": "q2"}], "solutions": [
        {"id": "s1", "question_id": "q1", "origin": "official", "coverage": "complete"},
        {"id": "s2", "question_id": "q2", "origin": "answer_key", "coverage": "answer_only"}]}
    assert solution_coverage(d) == {"missing": ["q2"], "reused": ["s1", "s2"], "conflicts": []}
    d["solutions"].append({"id": "s3", "question_id": "q1", "origin": "ai", "coverage": "complete"})
    with pytest.raises(ValueError, match="Duplicate"):
        solution_coverage(d)


def test_state_unknown_versions_and_repository_isolation(tmp_path):
    save_json(tmp_path / "state.json", {"schema_version": 99})
    with pytest.raises(ValueError, match="migration"):
        load_state(tmp_path)
    fake_repo = tmp_path / "repository"
    (fake_repo / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="outside"):
        private_root(fake_repo / "student-data")


def test_atomic_json_rejects_nonfinite_without_corrupting_checkpoint(tmp_path):
    path = tmp_path / "checkpoint.json"
    save_json(path, {"schema_version": 1})
    with pytest.raises(ValueError):
        save_json(path, {"bad": float("nan")})
    assert json.loads(path.read_text()) == {"schema_version": 1}


def test_preliminary_review_then_single_intake(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("과목: 선형대수\n시험 범위: 벡터", encoding="utf-8")
    root = tmp_path / "private"
    result = workflow.prepare(root, [source], defer_intake=True)
    assert result["stage"] == "inventoried" and result["intake"] == []
    src = result["source_manifest"]["sources"][0]
    workflow.review_sources(root, [{"source_id": src["id"], "method": "native_manual",
                                  "note": "본문에서 강의노트임을 확인", "category": "lecture_notes"}])
    result = workflow.open_intake(root, {"subject": "선형대수", "scope": "벡터"})
    assert not {"subject", "scope"} & {q["field"] for q in result["intake"]}
    workflow.answer(root, {})
    assert workflow.resume(root)["intake"] == []
    with pytest.raises(ValueError):
        workflow.answer(root, {})
    with pytest.raises(ValueError):
        workflow.open_intake(root, {})


def test_published_schemas_match_authority():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for name, schema in schema_documents().items():
        assert json.loads((root / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8")) == schema


def test_localization_preserves_evidence_and_originals(tmp_path):
    name = "04_기출문제_해설가이드.md"
    body = "안내 [원문](sources/source.txt)\n1. 원문 문제\n교수 원문 풀이"
    (tmp_path / name).write_text(body, encoding="utf-8")
    draft = {"questions": [{"text": "1. 원문 문제"}], "solutions": [{"origin": "official", "text": "교수 원문 풀이"}],
             "localized_documents": {name: "Guide [source](sources/source.txt)\n1. 원문 문제\n교수 원문 풀이"}}
    meta = [{"filename": name}]
    assert workflow.localize_documents(tmp_path, meta, draft, "en")
    draft["localized_documents"][name] = "Guide without sources or original"
    with pytest.raises(ValueError, match="links"):
        workflow.localize_documents(tmp_path, meta, draft, "en")


def test_unavailable_localization_does_not_claim_success(tmp_path):
    assert not workflow.localize_documents(tmp_path, [], {}, "en")
    assert workflow.localize_documents(tmp_path, [], {}, "ko")


def test_cli_json_is_utf8_under_legacy_console_encoding(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    source = tmp_path / "강의노트.txt"
    source.write_text("행렬의 정의", encoding="utf-8")
    root = tmp_path / "course"
    workflow.prepare(root, [source], defer_intake=True)
    command = Path(__file__).resolve().parents[1] / "scripts" / "study.py"
    result = subprocess.run([sys.executable, str(command), "resume", "--state", str(root)],
                            capture_output=True, env={**os.environ, "PYTHONIOENCODING": "ascii"}, timeout=30)
    assert result.returncode == 0, result.stderr.decode("utf-8")
    data = json.loads(result.stdout.decode("utf-8"))
    assert data["source_manifest"]["sources"][0]["filename"] == "강의노트.txt"


def test_multitopic_questions_wait_for_all_required_topics():
    from studymachine.planning import build_plan
    topics = [{"id": "foundation", "title": "선수 개념", "prerequisites": [], "estimated_minutes": 100},
              {"id": "advanced", "title": "후속 개념", "prerequisites": ["foundation"], "estimated_minutes": 150}]
    questions = [{"id": "q", "kind": "historical", "topic_ids": ["foundation", "advanced"]}]
    profile = {"exam_at": "2030-01-12T10:00:00+09:00", "timezone": "Asia/Seoul", "scope": "두 개념",
               "availability": {weekday: 90 for weekday in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}}
    plan = build_plan(profile, topics, questions, {}, "2030-01-01")
    finished_advanced = max(day["date"] for day in plan["days"] for block in day["blocks"]
                            if block["topic_id"] == "advanced" and not block["review"])
    links = [(day["date"], block) for day in plan["days"] for block in day["blocks"] if block["question_ids"]]
    assert links
    assert all(day >= finished_advanced or block["topic_id"] == "advanced" for day, block in links)
    assert not any(block["question_ids"] for day in plan["days"] for block in day["blocks"]
                   if block["topic_id"] == "foundation" and not block["review"])
