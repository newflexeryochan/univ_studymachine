"""Student-visible content, provenance, policy and private package boundaries."""

import hashlib
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

import pytest

from studymachine.artifacts import FILENAMES, render_package
from studymachine.policy import GenerationPolicy, PolicyViolation


@pytest.fixture
def package_inputs(tmp_path):
    def source(source_id, filename, category, text, location):
        data = text.encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        storage = tmp_path / "private" / digest
        storage.parent.mkdir(exist_ok=True)
        storage.write_bytes(data)
        return {"id": source_id, "filename": filename, "category": category, "status": "processed",
                "original_path": str(tmp_path / "private-input" / filename), "storage_path": str(storage),
                "sha256": digest, "file_type": Path(filename).suffix.lstrip("."), "page_count": 1,
                "sections": [{"location": location, "text": text}], "limitations": []}

    question1 = "1. f(x)=x²일 때 f′(3)을 구하시오.\n단, 정의역은 실수 전체이다."
    question2 = "2. f(x)=x³일 때 f′(2)를 구하시오."
    official = "공식 풀이 원문\n거듭제곱 미분법에 의해 f′(x)=2x. 따라서 f′(3)=6."
    reasoning = "정답표의 12를 유지한다. f′(x)=3x²이므로 f′(2)=3×2²=12이다."
    refs = [{"source_id": "lecture", "location": "slide:2"}]
    inputs = {
        "profile": {"subject": "미적분학", "exam_at": "2026-11-02T09:00:00+09:00", "timezone": "Asia/Seoul",
                    "scope": "극한과 거듭제곱 미분", "availability": {"2026-11-01": 90},
                    "preparation": "미분 공식은 익숙하지만 정의는 복습 필요", "target": "개념·계산 정확도", "format": "계산·서술"},
        "manifest": {"sources": [
            source("lecture", "강의 노트.md", "lecture_notes", "극한의 정의와 거듭제곱 미분법. f′(x)=nx^(n−1).", "slide:2"),
            source("exam", "중간고사.txt", "historical_exam", question1 + "\n" + question2, "page:1"),
            source("official", "공식 해설.txt", "official_solution", official + "\n정답표: 12", "page:1"),
        ]},
        "draft": {"topics": [
            {"id": "power", "title": "거듭제곱 미분", "prerequisites": ["limit"], "in_scope": True,
             "explanation": "다항식의 각 항을 미분할 때 지수를 계수로 내리고 지수를 하나 줄인다. 상수항은 0이다.",
             "definitions": ["도함수는 각 점에서의 순간변화율을 함수로 나타낸 것이다."],
             "formulas": ["f(x)=xⁿ이면 f′(x)=nxⁿ⁻¹; 적용 가능한 정의역을 먼저 확인한다."],
             "procedures": ["항과 계수를 구분 → 미분 공식 적용 → 지정한 점 대입 → 부호·계수 검산"],
             "common_mistakes": ["지수를 내린 뒤 원래 지수를 그대로 두지 않는다."],
             "references": refs, "evidence_kind": "source_backed"},
            {"id": "limit", "title": "극한", "in_scope": True,
             "explanation": "입력이 한 점에 가까워질 때 함수값이 가까워지는 값을 극한이라고 한다.",
             "references": refs, "evidence_kind": "source_backed"},
        ], "exams": [{"id": "midterm", "label": "제공된 중간고사", "source_id": "exam", "sitting_id": "sit1", "variant": "A"}],
            "questions": [
                {"id": "q1", "number": "1", "kind": "historical", "source_id": "exam", "location": "page:1",
                 "text": question1, "topic_ids": ["power"], "pattern": "미분 후 수치 대입", "method": "거듭제곱 미분법", "difficulty": "기초"},
                {"id": "q2", "number": "2", "kind": "historical", "source_id": "exam", "location": "page:1",
                 "text": question2, "topic_ids": ["power"]},
            ], "solutions": [
                {"id": "s1", "question_id": "q1", "origin": "official", "coverage": "complete", "text": official,
                 "references": [{"source_id": "official", "location": "page:1"}], "verification": "verified"},
                {"id": "s2", "question_id": "q2", "origin": "answer_key", "coverage": "answer_only", "text": "정답: 12",
                 "references": [{"source_id": "official", "location": "page:1"}], "verification": "unchecked"},
                {"id": "s3", "question_id": "q2", "origin": "ai", "coverage": "complete", "text": reasoning,
                 "references": refs, "verification": "verified"},
            ], "generated_questions": [], "limitations": []},
        "analysis": {"exam_count": 1, "sitting_count": 1, "question_count": 2,
                     "topics": [{"topic_id": "power", "exam_count": 1, "exam_denominator": 1,
                                 "question_count": 2, "historical_frequency": 1.0}], "limitations": []},
        "plan": {"start_date": "2026-11-01", "end_date": "2026-11-01", "conditional": False,
                 "days": [{"date": "2026-11-01", "available_minutes": 90, "buffer_minutes": 10, "blocks": [
                     {"topic_id": "power", "task": "원문 1·2번을 그대로 풀고 해설과 대조", "minutes": 35,
                      "priority": 1, "source_ids": ["lecture"], "question_ids": ["q1", "q2"],
                      "completion": "도함수와 대입 과정의 오류를 기록", "review": "당일 오류 복습"}]}],
                 "final_checklist": ["미분 공식의 적용 조건과 학생증을 확인한다."], "limitations": []},
        "mastery": {"observations": [], "topics": {}}, "errors": {"entries": []}, "qa": {"passed": True},
    }
    inputs["policy"] = GenerationPolicy.evaluate(inputs["manifest"], inputs["draft"]["questions"]).to_dict()
    return inputs


def render(tmp_path, inputs):
    return render_package(tmp_path / "output", **inputs)


def read(tmp_path, key):
    return (tmp_path / "output" / FILENAMES[key]).read_text(encoding="utf-8")


def no_history(inputs):
    inputs["manifest"]["sources"] = [s for s in inputs["manifest"]["sources"] if s["id"] == "lecture"]
    inputs["draft"].update(questions=[], exams=[], solutions=[])
    inputs["analysis"] = {}
    inputs["plan"] = {"conditional": True, "days": []}


def generated_item():
    return {"id": "g1", "label": "AI 생성 연습문제", "text": "f(x)=x⁴의 도함수를 구하시오.",
            "answer": "4x³", "explanation": "지수 4를 계수로 내리고 지수를 하나 줄인다.",
            "references": [{"source_id": "lecture", "location": "slide:2"}]}


def test_substantial_semantic_content_and_no_invented_progress(tmp_path, package_inputs):
    original = deepcopy(package_inputs)
    metadata = render(tmp_path, package_inputs)
    assert isinstance(metadata, list)
    assert package_inputs == original
    assert all(set(record) == {"filename", "source_ids", "status"} for record in metadata)
    names = {r["filename"] for r in metadata}
    assert set(FILENAMES.values()) - {FILENAMES["generated"]} <= names
    assert FILENAMES["generated"] not in names
    concepts = read(tmp_path, "concepts")
    assert concepts.index("## 극한") < concepts.index("## 거듭제곱 미분")
    for topic in package_inputs["draft"]["topics"]:
        assert topic["explanation"] in concepts
    assert package_inputs["draft"]["topics"][0]["formulas"][0] in concepts
    assert package_inputs["draft"]["topics"][0]["common_mistakes"][0] in concepts
    assert "숙련도는 평가 전" in read(tmp_path, "start")
    assert "[x]" not in read(tmp_path, "checklist")
    assert "실제 풀이 기록 없음" in read(tmp_path, "checklist")
    deps = {r["filename"]: set(r["source_ids"]) for r in metadata}
    assert deps[FILENAMES["concepts"]] == {"lecture"}
    assert deps[FILENAMES["solutions"]] == {"exam", "official", "lecture"}


def test_original_questions_and_official_text_survive_with_only_missing_ai_reasoning(tmp_path, package_inputs):
    render(tmp_path, package_inputs)
    index, solutions = read(tmp_path, "index"), read(tmp_path, "solutions")
    for q in package_inputs["draft"]["questions"]:
        assert q["text"] in index
    for solution in package_inputs["draft"]["solutions"]:
        assert solution["text"] in solutions
    assert "제공된 공식 해설" in solutions
    assert "제공된 정답표" in solutions
    assert "AI가 작성한 누락 풀이·추론 보충" in solutions
    assert solutions.index("정답: 12") < solutions.index("정답표의 12를 유지한다.")


def test_portable_citations_resolve_in_individual_files_and_allowlisted_zip(tmp_path, package_inputs):
    output = tmp_path / "output"
    output.mkdir()
    (output / "manifest.json").write_text("authoritative caller manifest", encoding="utf-8")
    (output / "unrelated-private.txt").write_text("do not package", encoding="utf-8")
    metadata = render(tmp_path, package_inputs)
    for record in metadata:
        path = output / record["filename"]
        assert path.is_file()
        assert set(record["source_ids"]) <= {"lecture", "exam", "official"}
        if path.suffix != ".md":
            continue
        content = path.read_text(encoding="utf-8")
        assert str(tmp_path / "private") not in content
        assert "original_path" not in content
        for target in re.findall(r"\]\(([^)]+)\)", content):
            parsed = urlsplit(target)
            assert not parsed.scheme
            linked = (path.parent / unquote(parsed.path)).resolve()
            assert linked.is_relative_to(output)
            assert linked.is_file(), target
            if parsed.fragment and linked.suffix == ".md":
                assert f'id="{parsed.fragment}"' in linked.read_text(encoding="utf-8")
    with ZipFile(output / "package.zip") as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {r["filename"] for r in metadata} - {"package.zip"}
        assert "manifest.json" not in archive.namelist()
        assert "unrelated-private.txt" not in archive.namelist()
        for source in package_inputs["manifest"]["sources"]:
            original = next(r for r in metadata if r["source_ids"] == [source["id"]] and ".original" in r["filename"])
            assert archive.read(original["filename"]) == Path(source["storage_path"]).read_bytes()
    assert (output / "manifest.json").read_text(encoding="utf-8") == "authoritative caller manifest"


@pytest.mark.parametrize("consent,include", [("yes", True), ("no", False), (None, False)])
def test_generated_artifact_requires_effective_permission_and_real_content(tmp_path, package_inputs, consent, include):
    no_history(package_inputs)
    package_inputs["policy"] = GenerationPolicy.evaluate(package_inputs["manifest"], consent=consent).to_dict()
    package_inputs["draft"]["generated_questions"] = [generated_item()] if include else []
    metadata = render(tmp_path, package_inputs)
    assert (FILENAMES["generated"] in {r["filename"] for r in metadata}) is include
    assert FILENAMES["history"] not in {r["filename"] for r in metadata}
    assert FILENAMES["solutions"] not in {r["filename"] for r in metadata}
    if include:
        content = read(tmp_path, "generated")
        assert "실제 기출문제가 아닙니다" in content
        for field in ("text", "answer", "explanation"):
            assert generated_item()[field] in content
        assert next(r for r in metadata if r["filename"] == FILENAMES["generated"])["source_ids"] == ["lecture"]


def test_allowed_without_generated_items_has_no_placeholder_artifact(tmp_path, package_inputs):
    no_history(package_inputs)
    package_inputs["policy"] = GenerationPolicy.evaluate(package_inputs["manifest"], consent="yes").to_dict()
    render(tmp_path, package_inputs)
    assert not (tmp_path / "output" / FILENAMES["generated"]).exists()


@pytest.mark.parametrize("history,consent,forged", [(True, "yes", True), (True, "no", False),
                                                  (False, None, True), (False, "no", False)])
def test_direct_renderer_api_fails_closed_before_writing(tmp_path, package_inputs, history, consent, forged):
    if not history:
        no_history(package_inputs)
    package_inputs["policy"] = {"allowed": forged, "consent": consent}
    package_inputs["draft"]["generated_questions"] = [generated_item()]
    with pytest.raises(PolicyViolation):
        render(tmp_path, package_inputs)
    assert not (tmp_path / "output").exists()


def test_caller_cannot_forge_allowed_even_without_generated_items(tmp_path, package_inputs):
    package_inputs["policy"] = {"allowed": True, "consent": "yes"}
    with pytest.raises(PolicyViolation, match="central"):
        render(tmp_path, package_inputs)


def test_unreadable_history_is_not_a_history_report_or_generation_consent(tmp_path, package_inputs):
    no_history(package_inputs)
    package_inputs["manifest"]["sources"].append({"id": "reject", "filename": "기출.pdf", "category": "historical_exam",
        "status": "failed", "sha256": None, "sections": [], "limitations": ["읽을 수 없는 파일"]})
    package_inputs["policy"] = GenerationPolicy.evaluate(package_inputs["manifest"], consent="yes").to_dict()
    metadata = render(tmp_path, package_inputs)
    names = {r["filename"] for r in metadata}
    assert FILENAMES["history"] not in names
    assert FILENAMES["generated"] not in names
    assert "읽기 실패" in read(tmp_path, "inventory")
    assert "읽을 수 없는 파일" in read(tmp_path, "inventory")
    assert "새 연습문제 생성 금지" in read(tmp_path, "usage")


def test_supplied_exercises_get_solutions_and_index_but_not_historical_report(tmp_path, package_inputs):
    package_inputs["manifest"]["sources"][1]["category"] = "assignment"
    for q in package_inputs["draft"]["questions"]:
        q["kind"] = "exercise"
    package_inputs["policy"] = GenerationPolicy.evaluate(package_inputs["manifest"]).to_dict()
    names = {r["filename"] for r in render(tmp_path, package_inputs)}
    assert FILENAMES["history"] not in names
    assert FILENAMES["solutions"] in names
    assert "## 提供" not in read(tmp_path, "index")
    assert "## 제공 연습문제" in read(tmp_path, "index")


def test_optional_fields_missing_content_and_unresolved_solutions_are_honest(tmp_path):
    metadata = render_package(tmp_path / "output", {}, {}, {}, {}, {}, {}, {}, {}, {})
    assert isinstance(metadata, list)
    assert "상세 설명" not in read(tmp_path, "concepts")
    assert "개념 설명이 제공되지 않았습니다" in read(tmp_path, "concepts")
    assert next(r for r in metadata if r["filename"] == FILENAMES["concepts"])["status"] == "partial"
    assert "학습 블록이 없습니다" in read(tmp_path, "schedule")
    assert not (tmp_path / "output" / FILENAMES["solutions"]).exists()


def test_nonblocking_cautions_do_not_downgrade_complete_artifacts(tmp_path, package_inputs):
    caution = "과거 빈도는 미래 출제 확률이 아닙니다."
    package_inputs["analysis"]["limitations"] = [caution]
    package_inputs["plan"]["limitations"] = ["실제 학습 속도에 따라 소요 시간이 달라질 수 있습니다."]
    package_inputs["manifest"]["sources"][0]["limitations"] = ["자료와 설명을 함께 확인하세요."]
    metadata = render(tmp_path, package_inputs)
    assert all(r["status"] == "complete" for r in metadata)
    assert caution in read(tmp_path, "start")
    assert caution in read(tmp_path, "history")


def test_missing_reasoning_conflicts_and_actual_observations_are_visible(tmp_path, package_inputs):
    package_inputs["draft"]["solutions"] = package_inputs["draft"]["solutions"][:2]
    package_inputs["draft"]["solutions"][0]["verification"] = "conflict"
    package_inputs["mastery"] = {"observations": [{"question_id": "q2", "correct": False,
        "observed_at": "2026-11-01", "review_due": "2026-11-02", "note": "계수 누락"}], "topics": {}}
    package_inputs["errors"] = {"entries": [{"question_id": "q2", "reason": "계수 누락", "review_due": "2026-11-02"}]}
    metadata = render(tmp_path, package_inputs)
    assert next(r for r in metadata if r["filename"] == FILENAMES["solutions"])["status"] == "partial"
    assert "미해결·풀이 보충 대기" in read(tmp_path, "solutions")
    assert "제공된 원문을 유지" in read(tmp_path, "solutions")
    assert "계수 누락" in read(tmp_path, "checklist")
    assert "2026-11-02" in read(tmp_path, "checklist")
    assert "오답 기록" in read(tmp_path, "checklist")
    assert "[x]" not in read(tmp_path, "checklist")


def test_alternative_plans_final_checklist_and_qualified_difficulty(tmp_path, package_inputs):
    package_inputs["plan"]["alternatives"] = {key: {"label": label, "days": deepcopy(package_inputs["plan"]["days"]),
        "limitations": ["가용 시간 안에서 선택하세요."]} for key, label in
        [("minimal", "최소 학습안"), ("realistic", "기본 학습안"), ("intensive", "집중 학습안")]}
    render(tmp_path, package_inputs)
    schedule = read(tmp_path, "schedule")
    for label in ("최소 학습안", "기본 학습안", "집중 학습안"):
        assert label in schedule
    assert "학습 배정: 35분" in schedule
    assert package_inputs["plan"]["final_checklist"][0] in schedule
    assert "원문 1·2번을 그대로 풀고 해설과 대조" in schedule
    history = read(tmp_path, "history")
    assert "난이도: 기초 — 제공된 정성 평가" in history
    assert "난이도: 미평가" in history
    assert "1 / 1" in history
    assert "미분 후 수치 대입" in history
    assert "출제 확률이나 성적 보장을 뜻하지 않습니다" in history


def test_renderer_retires_its_stale_conditional_outputs_on_successful_rerun(tmp_path, package_inputs):
    render(tmp_path, package_inputs)
    no_history(package_inputs)
    package_inputs["policy"] = GenerationPolicy.evaluate(package_inputs["manifest"], consent="yes").to_dict()
    package_inputs["draft"]["generated_questions"] = [generated_item()]
    render(tmp_path, package_inputs)
    assert not (tmp_path / "output" / FILENAMES["history"]).exists()
    assert not (tmp_path / "output" / FILENAMES["solutions"]).exists()
    package_inputs["draft"]["generated_questions"] = []
    package_inputs["policy"] = GenerationPolicy.evaluate(package_inputs["manifest"], consent="no").to_dict()
    render(tmp_path, package_inputs)
    assert not (tmp_path / "output" / FILENAMES["generated"]).exists()
    with ZipFile(tmp_path / "output" / "package.zip") as archive:
        assert FILENAMES["generated"] not in archive.namelist()


def test_hash_mismatch_is_disclosed_and_rejected_inputs_are_not_copied(tmp_path, package_inputs):
    package_inputs["manifest"]["sources"][0]["sha256"] = "0" * 64
    reject = deepcopy(package_inputs["manifest"]["sources"][2])
    reject.update(id="rejected", filename="untrusted.ps1", file_type="ps1", status="failed", sha256=None, sections=[])
    package_inputs["manifest"]["sources"].append(reject)
    metadata = render(tmp_path, package_inputs)
    assert not any(".original" in r["filename"] and r["source_ids"] in (["lecture"], ["rejected"]) for r in metadata)
    lecture_copy = next(r for r in metadata if r["source_ids"] == ["lecture"] and r["filename"].startswith("sources/"))
    assert "해시가 자료 기록과 달라" in (tmp_path / "output" / lecture_copy["filename"]).read_text(encoding="utf-8")
    assert lecture_copy["status"] == "partial"
