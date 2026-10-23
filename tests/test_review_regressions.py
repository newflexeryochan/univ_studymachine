"""Executable regressions for the bounded source/policy/localization review.

Semantic content is the existing explicit hand-authored test stub, not model
output. Localization examples test document structure, not translation quality.
The public workflow and real deterministic modules run against external tmp_path
storage. Shared fixtures are imported without changing their source file.
"""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re

import pytest
import test_e2e as shared_e2e

from studymachine import workflow
from studymachine.policy import PolicyViolation
from test_e2e import (
    GENERATED_ARTIFACT,
    INDEX_ARTIFACT,
    _draft,
    _finish,
    _package,
)


# Register shared fixtures without importing the earlier module's test cases.
make_course = shared_e2e.make_course
stubs = shared_e2e.stubs


def _snapshot(course):
    root = course["root"]
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _assert_preserved(course, previous, snapshot):
    after = _snapshot(course)
    assert {name: data for name, data in after.items() if name != "state.json"} == {
        name: data for name, data in snapshot.items() if name != "state.json"
    }, "A rejected validation must preserve the published package and source bytes"
    current = workflow.resume(course["root"])
    assert current == previous, "A rejected validation must preserve the previous public checkpoint"
    assert _snapshot(course) == snapshot, "A rejected validation must preserve state, sources, and package bytes"
    if previous["stage"] == "complete":
        assert current["run_manifest"]["validation"]["passed"] is True
        _package(current)


def _unreadable_source(course):
    source = next(s for s in course["prepared"]["source_manifest"]["sources"] if s["file_type"] == "pdf")
    assert source["status"] == "failed" and source["sections"] == []
    assert source["suspected_history"] is True and source["unreadable_history"] is True
    return source


def test_reclassifying_unreadable_history_retains_generation_prohibition(make_course):
    course = make_course(("course.txt", "corrupt_history.pdf.txt"), consent="yes")
    source = _unreadable_source(course)
    reviewed = workflow.review_sources(course["root"], [{
        "source_id": source["id"], "method": "native_manual",
        "note": "읽을 수 없는 원본은 그대로이며 분류만 기타로 변경한 테스트", "category": "other",
    }])
    retained = next(s for s in reviewed["source_manifest"]["sources"] if s["id"] == source["id"])
    assert retained["category"] == "other"
    assert retained["status"] == "failed" and retained["sections"] == []
    assert retained["suspected_history"] is True and retained["unreadable_history"] is True
    assert reviewed["generation_policy"]["allowed"] is False
    assert reviewed["generation_policy"]["historical_present"] is True
    assert reviewed["generation_policy"]["unreadable_history"] is True
    before = _snapshot(course)
    with pytest.raises(PolicyViolation):
        _finish(course, _draft(course, generated=True))
    _assert_preserved(course, reviewed, before)
    assert not (Path(reviewed["output_dir"]) / GENERATED_ARTIFACT).exists()


@pytest.mark.parametrize("invalid", ["failed", "partial", "processed-empty", "still-historical"])
def test_explicit_history_resolution_requires_a_full_nonhistorical_reading(make_course, invalid):
    course = make_course(("course.txt", "corrupt_history.pdf.txt"), consent="yes")
    source = _unreadable_source(course)
    review = {
        "source_id": source["id"], "method": "native_manual", "note": "역사 자료 의심 해제의 검증 테스트",
        "category": "other", "history_resolution": "기출이 아닌 자료라는 명시적 판독 주장",
    }
    if invalid == "partial":
        review.update(status="partial", sections=[{"location": "page:1", "text": "일부 구간만 확인됨"}])
    elif invalid == "processed-empty":
        review.update(status="processed", sections=[])
    elif invalid == "still-historical":
        review.update(status="processed", category="historical_exam",
                      sections=[{"location": "page:1", "text": "합성 기출문제 원문"}])
    previous = workflow.resume(course["root"])
    before = _snapshot(course)
    with pytest.raises(ValueError):
        workflow.review_sources(course["root"], [review])
    _assert_preserved(course, previous, before)
    assert workflow.resume(course["root"])["generation_policy"]["allowed"] is False


def test_full_nonhistorical_review_can_resolve_a_filename_false_positive(tmp_path, stubs):
    # The misleading filename triggers suspicion; the entire TXT is course notes.
    assert not any((p / ".git").exists() for p in (tmp_path, *tmp_path.parents))
    uploaded = tmp_path / "past_exam_notes.txt"
    uploaded.write_bytes((Path(__file__).parent / "fixtures" / "course.txt").read_bytes())
    original_bytes = uploaded.read_bytes()
    profile = deepcopy(stubs["course_profile"])
    profile["generation_consent"] = "yes"
    root = tmp_path / "private"
    initial = workflow.prepare(root, [uploaded], profile=profile, defer_intake=True)
    source = initial["source_manifest"]["sources"][0]
    assert source["status"] == "processed" and source["sections"]
    assert initial["generation_policy"]["allowed"] is False
    result = workflow.review_sources(root, [{
        "source_id": source["id"], "method": "native_manual", "note": "합성 TXT 전체를 대조하여 강의노트임을 확인",
        "category": "lecture_notes", "status": "processed", "sections": deepcopy(source["sections"]),
        "history_resolution": "이름에만 기출 표시가 있고 본문 전체는 일차방정식과 미분의 강의노트임",
    }])
    resolved = result["source_manifest"]["sources"][0]
    assert resolved["id"] == source["id"] and resolved["sha256"] == source["sha256"]
    assert resolved["sections"] == source["sections"]
    assert resolved["initial_history_suspicion"] is True
    assert resolved["suspected_history"] is False and resolved["unreadable_history"] is False
    assert resolved["history_resolution"]
    assert result["generation_policy"]["allowed"] is True
    assert uploaded.read_bytes() == original_bytes


def test_generation_rejection_preserves_the_previous_complete_package(make_course):
    course = make_course(("course.txt", "exam_a.txt", "official_complete.txt"), consent="yes")
    draft = _draft(course, "complete")
    previous = _finish(course, draft)
    assert previous["stage"] == "complete"
    before = _snapshot(course)
    rejected = deepcopy(draft)
    rejected["generated_questions"] = _draft(course, "complete", generated=True)["generated_questions"]
    with pytest.raises(PolicyViolation):
        _finish(course, rejected)
    _assert_preserved(course, previous, before)


@pytest.mark.parametrize("replacement", ["drop", "substitute", "reuse-id-as-ai"])
def test_previous_official_solutions_cannot_be_removed_or_replaced(make_course, replacement):
    course = make_course(("course.txt", "exam_a.txt", "official_complete.txt"))
    draft = _draft(course, "complete")
    previous = _finish(course, draft)
    assert previous["stage"] == "complete"
    assert len(previous["run_manifest"]["validation"]["solution_coverage"]["reused"]) == 3
    before = _snapshot(course)
    rejected = deepcopy(draft)
    if replacement == "drop":
        rejected["solutions"] = []
    elif replacement == "substitute":
        rejected["solutions"] = _draft(course, "none")["solutions"]
    else:
        ai = deepcopy(_draft(course, "none")["solutions"][0])
        ai["id"] = rejected["solutions"][0]["id"]
        rejected["solutions"][0] = ai
    with pytest.raises(ValueError):
        _finish(course, rejected)
    _assert_preserved(course, previous, before)


@pytest.mark.parametrize("removed", [("q-a2",), ("q-a-context", "q-a1a", "q-a1b")],
                         ids=["leaf", "context-and-subquestions"])
def test_previous_original_questions_cannot_be_deleted(make_course, removed):
    # AI-only solutions keep this independent of the supplied-solution guard.
    course = make_course(("course.txt", "exam_a.txt"))
    draft = _draft(course, "none")
    previous = _finish(course, draft)
    assert previous["stage"] == "complete"
    before = _snapshot(course)
    rejected = deepcopy(draft)
    rejected["questions"] = [q for q in rejected["questions"] if q["id"] not in removed]
    rejected["solutions"] = [s for s in rejected["solutions"] if s["question_id"] not in removed]
    with pytest.raises(ValueError):
        _finish(course, rejected)
    _assert_preserved(course, previous, before)


def test_localization_missing_anchors_preserves_published_package_and_pending_draft(make_course):
    course = make_course(("course.txt", "exam_a.txt", "official_complete.txt"))
    draft = _draft(course, "complete")
    korean = _finish(course, draft)
    assert korean["stage"] == "complete"
    translations = {
        path.name: "Structural localization test stub; not a real translation.\n\n" + path.read_text(encoding="utf-8")
        for path in Path(korean["output_dir"]).glob("*.md")
    }
    workflow.replan(course["root"], {"language": "en"}, start_date=date.today().isoformat())
    localized = deepcopy(draft)
    localized["localized_documents"] = translations
    previous = _finish(course, localized)
    assert previous["stage"] == "complete" and previous["profile"]["language"] == "en"
    _package(previous)
    before = _snapshot(course)
    rejected = deepcopy(localized)
    original_index = rejected["localized_documents"][INDEX_ARTIFACT]
    assert re.search(r'<a\b[^>]*\bid=["\x27][^"\x27]+["\x27][^>]*></a>', original_index)
    rejected_index = re.sub(r"<a\b[^>]*></a>\s*", "", original_index)
    assert rejected_index != original_index
    assert re.findall(r"\]\(([^)]+)\)", rejected_index) == re.findall(r"\]\(([^)]+)\)", original_index)
    assert all(q["text"] in rejected_index for q in draft["questions"])
    rejected["localized_documents"][INDEX_ARTIFACT] = rejected_index
    with pytest.raises(ValueError):
        _finish(course, rejected)
    # Render-time validation keeps the published package and checkpoints pending
    # semantic work for repair, rather than advertising a fresh complete run.
    after = _snapshot(course)
    assert {name: data for name, data in after.items() if name != "state.json"} == {
        name: data for name, data in before.items() if name != "state.json"
    }
    current = workflow.resume(course["root"])
    assert current["stage"] == "awaiting_semantics"
    assert current["run_manifest"] == previous["run_manifest"]
    assert current["draft"] == rejected
    for field in ("profile", "source_manifest", "mastery_state", "error_log", "output_dir"):
        assert current[field] == previous[field]
    checkpoint = json.loads((course["root"] / "state.json").read_text(encoding="utf-8"))
    assert checkpoint["stage"] == "awaiting_semantics" and checkpoint["draft"] == rejected
    assert checkpoint["run_manifest"] == previous["run_manifest"]
    _package(previous)
