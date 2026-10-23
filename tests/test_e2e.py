"""Public-workflow acceptance tests using explicit hand-authored semantic stubs.

No live model or automatic semantic extraction is tested. All deterministic
modules run normally, with runtime material and state outside Git in tmp_path.
Assertions target persisted data and delivered artifacts, not diagnostic prose.
"""

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import zipfile

import pytest

from studymachine import workflow
from studymachine.policy import PolicyViolation


FIXTURES = Path(__file__).parent / "fixtures"
REPOSITORY = Path(__file__).resolve().parents[1]
GENERATED_ARTIFACT = "09_AI생성_연습문제_및_해설.md"
HISTORY_ARTIFACT = "03_기출문제_출제경향_분석.md"
SOLUTIONS_ARTIFACT = "04_기출문제_해설가이드.md"
INDEX_ARTIFACT = "07_제공문제_인덱스.md"
COMMON_ARTIFACTS = {
    "00_시험대비_안내.md", "01_시험범위_자료검증.md", "02_시험범위_개념총정리.md",
    "05_시험일까지_학습계획.md", "06_복습_체크리스트.md", "08_학습_진행방법.md",
}
CATEGORIES = {
    "course.txt": "lecture_notes", "exam_a.txt": "historical_exam",
    "exam_b.txt": "historical_exam", "exam_c.txt": "historical_exam",
    "official_complete.txt": "official_solution", "official_partial.txt": "official_solution",
    "answer_key.txt": "answer_key", "exercise.txt": "assignment",
}
AI_QUESTIONS = {
    "complete": {"q-b1", "q-c1", "q-exercise"},
    "none": {"q-a1a", "q-a1b", "q-a2", "q-b1", "q-c1", "q-exercise"},
    "partial": {"q-a1b", "q-a2", "q-b1", "q-c1", "q-exercise"},
    "answer_key": {"q-a1a", "q-a1b", "q-a2", "q-b1", "q-c1", "q-exercise"},
}


@pytest.fixture
def stubs():
    return json.loads((FIXTURES / "semantic_stubs.json").read_text(encoding="utf-8"))


@pytest.fixture
def make_course(tmp_path, stubs):
    """Copy only synthetic inputs and prepare through the public workflow API."""
    assert not any((p / ".git").exists() for p in (tmp_path, *tmp_path.parents))
    counter = 0

    def create(names=("course.txt", "exam_a.txt"), *, profile=None, consent="no"):
        nonlocal counter
        counter += 1
        folder = tmp_path / f"course-{counter}"
        uploads = folder / "uploads"
        uploads.mkdir(parents=True)
        inputs, categories = {}, {}
        for name in names:
            destination = ("past_exam_unreadable.pdf" if name == "corrupt_history.pdf.txt" else name)
            path = uploads / destination
            shutil.copyfile(FIXTURES / name, path)
            inputs[destination] = path.read_bytes()
            if name in CATEGORIES:
                categories[destination] = CATEGORIES[name]
        if profile is None:
            profile = deepcopy(stubs["course_profile"])
            profile["exam_at"] = (date.today() + timedelta(days=14)).isoformat() + "T14:00:00+09:00"
            profile["generation_consent"] = consent
        root = folder / "private-state"
        prepared = workflow.prepare(root, list(uploads.iterdir()), profile=profile, categories=categories)
        return {"root": root, "uploads": uploads, "inputs": inputs, "prepared": prepared, "stubs": stubs}

    return create


def _draft(course, coverage="none", *, generated=False):
    """Bind fixture source aliases to observed IDs/locations; supply no semantics."""
    stub = course["stubs"]
    sources = {s["filename"]: s for s in course["prepared"]["source_manifest"]["sources"]}
    questions = [deepcopy(q) for q in stub["questions"] if q["source_id"] in sources]
    question_ids = {q["id"] for q in questions}
    supplied_group = {"complete": "official_complete", "partial": "official_partial",
                      "answer_key": "answer_key"}.get(coverage)
    supplied = deepcopy(stub["solutions"].get(supplied_group, []))
    additions = [deepcopy(s) for s in stub["solutions"]["ai_stub"]
                 if s["question_id"] in AI_QUESTIONS[coverage]]
    draft = {
        "schema_version": 1, "topics": deepcopy(stub["topics"]),
        "exams": [deepcopy(e) for e in stub["exams"] if e["source_id"] in sources],
        "questions": questions,
        "solutions": [s for s in supplied + additions if s["question_id"] in question_ids],
        "generated_questions": deepcopy(stub["generated_questions"]) if generated else [],
        "limitations": [],
    }

    def bind(value):
        if isinstance(value, list):
            return [bind(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: bind(item) for key, item in value.items()}
        if "source_id" in value:
            source = sources[value["source_id"]]
            result["source_id"] = source["id"]
            if "location" in value:
                result["location"] = source["sections"][0]["location"]
        return result

    return bind(draft)


def _finish(course, draft):
    # Use a public ISO date, never a planner-specific object or patched clock.
    return workflow.finish(course["root"], draft, start_date=date.today().isoformat())


def _package(result):
    """Check the on-disk and ZIP deliveries against the authoritative manifest."""
    output = Path(result["output_dir"])
    run = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert run == result["run_manifest"]
    assert run["schema_version"] == 1
    assert result["stage"] == run["status"]
    artifacts = run["artifacts"]
    names = [a["filename"] for a in artifacts]
    assert len(names) == len(set(names))
    assert COMMON_ARTIFACTS <= set(names)
    source_ids = {s["id"] for s in run["sources"]}
    for artifact in artifacts:
        relative = PurePosixPath(artifact["filename"])
        assert not relative.is_absolute() and ".." not in relative.parts
        assert set(artifact["source_ids"]) <= source_ids
        path = output / artifact["filename"]
        assert path.resolve().is_relative_to(output.resolve())
        assert path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        assert path.read_text(encoding="utf-8").strip()
    expected = set(names) | {"manifest.json"}
    disk_files = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    assert disk_files == expected | {"package.zip"}
    with zipfile.ZipFile(output / "package.zip") as bundle:
        assert bundle.testzip() is None
        assert len(bundle.namelist()) == len(set(bundle.namelist()))
        assert set(bundle.namelist()) == expected
        for name in bundle.namelist():
            member = PurePosixPath(name)
            assert not member.is_absolute() and ".." not in member.parts
            assert "\\" not in name
            assert bundle.read(name) == (output / name).read_bytes()
        assert json.loads(bundle.read("manifest.json")) == run
    return output, run, set(names)


def _no_generation(result, names):
    run = result["run_manifest"]
    assert result["generation_policy"]["allowed"] is False
    assert run["generation_policy"] == result["generation_policy"]
    assert run["new_question_count"] == 0
    assert result["draft"]["generated_questions"] == []
    assert GENERATED_ARTIFACT not in names
    assert not (Path(result["output_dir"]) / GENERATED_ARTIFACT).exists()


def _originals(course, result):
    for filename, expected in course["inputs"].items():
        assert (course["uploads"] / filename).read_bytes() == expected
    for source in result["source_manifest"]["sources"]:
        expected = course["inputs"][source["filename"]]
        assert source["sha256"] == hashlib.sha256(expected).hexdigest()
        assert Path(source["original_path"]).read_bytes() == expected
    # The retained private originals survive independently of the uploads.
    stored = [p.read_bytes() for p in (course["root"] / "materials").rglob("*") if p.is_file()]
    assert all(data in stored for data in course["inputs"].values())


def _feasible_plan(result):
    plan = result["run_manifest"]["plan"]
    assert plan["conditional"] is False
    assert plan["days"]
    blocks = [b for day in plan["days"] for b in day["blocks"]]
    assert blocks and any(b["review"] for b in blocks)
    question_ids = {q["id"] for q in result["draft"]["questions"] if not q.get("is_context")}
    source_ids = {s["id"] for s in result["source_manifest"]["sources"]}
    for day in plan["days"]:
        assert 0 <= day["available_minutes"] <= 180
        assert 0 <= day["buffer_minutes"] <= day["available_minutes"]
        assert sum(b["minutes"] for b in day["blocks"]) + day["buffer_minutes"] <= day["available_minutes"]
        for block in day["blocks"]:
            assert block["minutes"] > 0 and block["task"] and block["completion"]
            assert set(block["source_ids"]) <= source_ids
            assert set(block["question_ids"]) <= question_ids


def _fresh_resume(course):
    result = subprocess.run(
        [sys.executable, str(REPOSITORY / "scripts" / "study.py"), "resume", "--state", str(course["root"])],
        cwd=REPOSITORY, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True, encoding="utf-8", timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _portable_index_links(output, index):
    """Resolve delivered Markdown links and HTML anchors without deriving hashes."""
    links = []
    for href in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", index):
        parsed = urlsplit(href)
        assert not parsed.scheme and not parsed.netloc and not parsed.query
        target = (output / unquote(parsed.path)).resolve()
        assert target.is_relative_to(output.resolve()) and target.is_file()
        fragment = unquote(parsed.fragment)
        section = None
        if target.suffix == ".md" and fragment:
            text = target.read_text(encoding="utf-8")
            anchor = re.search(rf"<[^>]+\bid=[\"']{re.escape(fragment)}[\"'][^>]*>", text)
            assert anchor is not None, f"Broken packaged anchor: {href}"
            following = text[anchor.end():]
            section = re.split(r"<[^>]+\bid=[\"']", following, maxsplit=1)[0]
        links.append((target.relative_to(output.resolve()).as_posix(), section))
    assert links
    return links


@pytest.mark.parametrize(
    ("coverage", "solution_file", "ai_ids", "supplied_count"),
    [
        ("complete", "official_complete.txt", set(), 3),
        ("none", None, {"q-a1a", "q-a1b", "q-a2"}, 0),
        ("partial", "official_partial.txt", {"q-a1b", "q-a2"}, 2),
        ("answer_key", "answer_key.txt", {"q-a1a", "q-a1b", "q-a2"}, 3),
    ],
    ids=["complete-official", "no-solutions", "partial-subquestion", "answer-key-only"],
)
def test_historical_solution_scenarios(make_course, coverage, solution_file, ai_ids, supplied_count):
    files = ["course.txt", "exam_a.txt"] + ([solution_file] if solution_file else [])
    course = make_course(files)
    draft = _draft(course, coverage)
    untouched = deepcopy(draft)
    result = _finish(course, draft)
    output, run, names = _package(result)
    assert result["stage"] == "complete"
    assert run["validation"]["passed"] is True
    assert {HISTORY_ARTIFACT, SOLUTIONS_ARTIFACT, INDEX_ARTIFACT} <= names
    assert run["analysis"]["question_count"] == 3
    assert run["analysis"]["exam_count"] == 1
    assert result["draft"]["questions"] == draft["questions"]
    assert draft == untouched, "finish must not mutate the caller's semantic draft"
    solutions = result["draft"]["solutions"]
    assert {s["question_id"] for s in solutions if s["origin"] == "ai"} == ai_ids
    supplied = [s for s in solutions if s["origin"] != "ai"]
    assert len(supplied) == supplied_count
    assert set(run["validation"]["solution_coverage"]["reused"]) == {s["id"] for s in supplied}
    assert run["validation"]["solution_coverage"]["missing"] == []
    assert all(s["verification"] == "verified" for s in solutions if s["origin"] == "ai")
    guide = (output / SOLUTIONS_ARTIFACT).read_text(encoding="utf-8")
    index = (output / INDEX_ARTIFACT).read_text(encoding="utf-8")
    sources = {s["id"]: s for s in result["source_manifest"]["sources"]}
    artifact_metadata = {a["filename"]: a for a in run["artifacts"]}
    links = _portable_index_links(output, index)
    index_metadata = next(a for a in run["artifacts"] if a["filename"] == INDEX_ARTIFACT)
    for question in draft["questions"]:
        assert question["text"] in index
        assert question["source_id"] in index_metadata["source_ids"]
        # Evidence can use portable filenames; its actual link and section must
        # resolve to the original question and the matching manifest source.
        assert any(
            section is not None and question["text"] in section and question["location"] in section
            and question["source_id"] in artifact_metadata[filename]["source_ids"]
            for filename, section in links
        )
        source = sources[question["source_id"]]
        assert any(
            section is None and question["source_id"] in artifact_metadata[filename]["source_ids"]
            and hashlib.sha256((output / filename).read_bytes()).hexdigest() == source["sha256"]
            for filename, section in links
        )
    for solution in solutions:
        assert solution["text"] in guide
    assert result["mastery_state"] == {"schema_version": 1, "observations": [], "topics": {}}
    assert result["error_log"] == {"schema_version": 1, "entries": []}
    _no_generation(result, names)
    _originals(course, result)
    _feasible_plan(result)


@pytest.mark.parametrize(("answer_value", "expected_consent"), [("예", "yes"), ("아니요", "no"), (None, None)],
                         ids=["yes", "no", "unanswered"])
def test_no_history_explicit_consent(make_course, answer_value, expected_consent):
    course = make_course(("course.txt", "exercise.txt"), consent=None)
    assert course["prepared"]["stage"] == "awaiting_intake"
    assert [q["field"] for q in course["prepared"]["intake"]] == ["generation_consent"]
    assert len(course["prepared"]["intake"][0]["choices"]) == 2
    answers = {} if answer_value is None else {"generation_consent": answer_value}
    answered = workflow.answer(course["root"], answers)
    assert answered["profile"]["generation_consent"] == expected_consent
    assert answered["stage"] == "awaiting_semantics" and answered["intake"] == []
    result = _finish(course, _draft(course, generated=expected_consent == "yes"))
    output, run, names = _package(result)
    assert result["stage"] == "complete"
    assert HISTORY_ARTIFACT not in names
    assert run["analysis"]["exam_count"] == run["analysis"]["question_count"] == 0
    assert result["generation_policy"]["historical_present"] is False
    assert run["consent_record"] == expected_consent
    assert result["draft"]["questions"][0]["kind"] == "exercise"
    if expected_consent == "yes":
        assert result["generation_policy"]["allowed"] is True
        assert run["new_question_count"] == 1 and GENERATED_ARTIFACT in names
        generated = result["draft"]["generated_questions"][0]
        text = (output / GENERATED_ARTIFACT).read_text(encoding="utf-8")
        for field in ("label", "text", "answer", "explanation"):
            assert generated[field] in text
        assert generated["label"] == "AI 생성 연습문제"
        assert generated["references"]
    else:
        _no_generation(result, names)
    _originals(course, result)
    _feasible_plan(result)


@pytest.mark.parametrize("case", ["history-despite-yes", "no-history-no", "no-history-unanswered", "unreadable-despite-yes"])
def test_forbidden_generated_content_raises(make_course, case):
    names = ["course.txt"]
    consent = "no"
    if case == "history-despite-yes":
        names.append("exam_a.txt")
        consent = "yes"
    elif case == "unreadable-despite-yes":
        names.append("corrupt_history.pdf.txt")
        consent = "yes"
    elif case == "no-history-unanswered":
        consent = None
    course = make_course(names, consent=consent)
    if course["prepared"]["stage"] == "awaiting_intake":
        workflow.answer(course["root"], {})
    draft = _draft(course, generated=True)
    with pytest.raises(PolicyViolation):
        _finish(course, draft)
    resumed = _fresh_resume(course)
    assert resumed["stage"] == "awaiting_semantics"
    assert resumed["draft"] is None and resumed["run_manifest"] is None
    assert not Path(resumed["output_dir"]).exists()
    _originals(course, resumed)


def test_unreadable_history_is_partial_and_never_absence(make_course):
    # No category override for the corrupt input: suspected history must be detected.
    course = make_course(("course.txt", "corrupt_history.pdf.txt"), consent="yes")
    prepared = course["prepared"]
    assert "generation_consent" not in {q["field"] for q in prepared["intake"]}
    history = next(s for s in prepared["source_manifest"]["sources"] if s["filename"].endswith(".pdf"))
    assert history["category"] == "historical_exam"
    assert history["status"] in {"failed", "partial"}
    assert history["sections"] == [] and history["limitations"]
    assert prepared["generation_policy"]["historical_present"] is True
    assert prepared["generation_policy"]["unreadable_history"] is True
    result = _finish(course, _draft(course))
    output, run, names = _package(result)
    assert result["stage"] == "partial"
    assert run["validation"]["passed"] is False
    assert run["limitations"] and run["validation"]["blockers"]
    assert result["draft"]["questions"] == []
    assert next(s for s in run["sources"] if s["id"] == history["id"])["status"] == history["status"]
    inventory = (output / "01_시험범위_자료검증.md").read_text(encoding="utf-8")
    assert history["filename"] in inventory
    assert "일차방정식" in (output / "02_시험범위_개념총정리.md").read_text(encoding="utf-8")
    _no_generation(result, names)
    _originals(course, result)


@pytest.mark.parametrize("with_history", [True, False], ids=["history", "no-history"])
def test_intake_is_one_batch_of_at_most_eight_and_resumable(make_course, with_history):
    files = ("course.txt", "exam_a.txt") if with_history else ("course.txt",)
    course = make_course(files, profile={"schema_version": 1, "course_id": "synthetic-unknown"})
    first = course["prepared"]
    assert first["stage"] == "awaiting_intake"
    fields = [q["field"] for q in first["intake"]]
    assert 1 <= len(fields) <= 8 and len(fields) == len(set(fields))
    assert ("generation_consent" in fields) is (not with_history)
    assert _fresh_resume(course)["intake"] == first["intake"]
    repeated = workflow.prepare(course["root"], [], profile={"subject": "재입력 과목"})
    assert repeated["intake"] == first["intake"]
    answered = workflow.answer(course["root"], {})
    assert answered["stage"] == "awaiting_semantics" and answered["intake"] == []
    assert answered["profile"].get("generation_consent") is None
    assert _fresh_resume(course)["intake"] == []
    with pytest.raises(ValueError):
        workflow.answer(course["root"], {})
    assert workflow.resume(course["root"])["intake"] == []


@pytest.mark.parametrize("with_history", [True, False])
def test_intake_suppresses_reliably_known_fields(make_course, stubs, with_history):
    known = {field: deepcopy(stubs["course_profile"][field])
             for field in ("course_id", "subject", "scope", "format", "preparation", "timezone")}
    known["exam_at"] = (date.today() + timedelta(days=14)).isoformat() + "T14:00:00+09:00"
    files = ("course.txt", "exam_a.txt") if with_history else ("course.txt",)
    course = make_course(files, profile=known)
    fields = {q["field"] for q in course["prepared"]["intake"]}
    assert fields.isdisjoint(known)
    assert {"availability", "target", "instructor_guidance"} <= fields
    assert ("generation_consent" in fields) is (not with_history)
    assert len(fields) <= 8
    workflow.answer(course["root"], {})
    resumed = _fresh_resume(course)
    assert all(resumed["profile"][field] == value for field, value in known.items())
    assert resumed["intake"] == []


def test_finish_requires_intake_then_allows_conditional_package(make_course, stubs):
    profile = deepcopy(stubs["course_profile"])
    profile["exam_at"] = profile["availability"] = None
    course = make_course(("course.txt",), profile=profile)
    draft = _draft(course)
    with pytest.raises(ValueError):
        _finish(course, draft)
    assert not (course["root"] / "output").exists()
    assert _fresh_resume(course)["stage"] == "awaiting_intake"
    workflow.answer(course["root"], {})
    result = _finish(course, draft)
    _, run, names = _package(result)
    assert result["stage"] == "partial" and run["validation"]["passed"] is False
    assert run["plan"]["conditional"] is True
    assert run["plan"]["days"] == []
    assert result["profile"]["exam_at"] is None and result["profile"]["availability"] is None
    assert run["limitations"]
    _no_generation(result, names)


def test_historical_frequencies_use_variants_sittings_and_leaf_denominators(make_course):
    course = make_course(("course.txt", "exam_a.txt", "exam_b.txt", "exam_c.txt", "exercise.txt"))
    result = _finish(course, _draft(course))
    _, run, names = _package(result)
    analysis = run["analysis"]
    assert result["stage"] == "complete"
    assert (analysis["exam_count"], analysis["sitting_count"], analysis["question_count"]) == (3, 2, 5)
    topics = {t["topic_id"]: t for t in analysis["topics"]}
    for topic_id, question_count in (("t-equation", 3), ("t-derivative", 2)):
        row = topics[topic_id]
        assert row["exam_count"] == 2 and row["exam_denominator"] == 3
        assert row["question_count"] == question_count
        assert row["historical_frequency"] == pytest.approx(2 / 3)
    assert topics["t-equation"]["sitting_count"] == 1
    assert topics["t-derivative"]["sitting_count"] == 2
    for row in topics.values():
        assert row["sitting_denominator"] == 2 and row["question_denominator"] == 5
    patterns = {row["pattern"]: row for row in analysis["patterns"]}
    assert patterns["일차방정식 계산"]["question_count"] == 3
    assert patterns["거듭제곱 미분"]["question_count"] == 2
    assert all(row["exam_denominator"] == 3 for row in patterns.values())
    assert analysis["limitations"]  # Descriptive historical evidence has explicit limits.
    _no_generation(result, names)
    _feasible_plan(result)


@pytest.mark.parametrize("invalid", ["topic-source", "topic-location", "question-source", "question-location", "solution-source", "generated-source"])
def test_invalid_source_references_are_rejected_without_publishing(make_course, invalid):
    course = make_course(consent="yes") if invalid != "generated-source" else make_course(("course.txt",), consent="yes")
    draft = _draft(course, generated=invalid == "generated-source")
    if invalid.startswith("topic"):
        reference = draft["topics"][0]["references"][0]
    elif invalid.startswith("question"):
        reference = draft["questions"][1]
    elif invalid == "solution-source":
        reference = draft["solutions"][0]["references"][0]
    else:
        reference = draft["generated_questions"][0]["references"][0]
    reference["location" if invalid.endswith("location") else "source_id"] = "not-an-ingested-reference"
    with pytest.raises(ValueError):
        _finish(course, draft)
    resumed = workflow.resume(course["root"])
    assert resumed["stage"] == "awaiting_semantics" and resumed["run_manifest"] is None
    assert not Path(resumed["output_dir"]).exists()
    _originals(course, resumed)


@pytest.mark.parametrize("mutation", ["question-text", "question-number", "official-text", "correction-text"])
def test_original_text_and_identity_are_immutable_across_resume(make_course, mutation):
    course = make_course(("course.txt", "exam_a.txt", "official_complete.txt"))
    draft = _draft(course, "complete")
    initial = _finish(course, draft)
    output, _, _ = _package(initial)
    before_state = (course["root"] / "state.json").read_bytes()
    before_outputs = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    changed = deepcopy(draft)
    with pytest.raises(ValueError):
        if mutation == "correction-text":
            workflow.correct(course["root"], {"q-a1a": {"text": "1-(가). 방정식 x+30=50의 해를 구하시오."}})
        else:
            if mutation == "question-text":
                changed["questions"][1]["text"] = "1-(가). 방정식 x+30=50의 해를 구하시오."
            elif mutation == "question-number":
                changed["questions"][1]["number"] = "99"
            else:
                changed["solutions"][0]["text"] += " 임의로 바꾼 해는 99이다."
            _finish(course, changed)
    assert (course["root"] / "state.json").read_bytes() == before_state
    assert {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()} == before_outputs
    assert _fresh_resume(course)["draft"] == initial["draft"]
    _originals(course, workflow.resume(course["root"]))


def test_complete_official_solution_rejects_duplicate_ai_explanation(make_course):
    course = make_course(("course.txt", "exam_a.txt", "official_complete.txt"))
    draft = _draft(course, "complete")
    draft["solutions"].append(_draft(course, "none")["solutions"][0])
    with pytest.raises(ValueError):
        _finish(course, draft)
    assert workflow.resume(course["root"])["run_manifest"] is None
    assert not (course["root"] / "output").exists()


@pytest.mark.parametrize("duplicate", ["question", "exam-variant"])
def test_duplicate_historical_import_is_rejected(make_course, duplicate):
    course = make_course()
    draft = _draft(course)
    if duplicate == "question":
        record = deepcopy(draft["questions"][1])
        record["id"] = "duplicate-question"
        draft["questions"].append(record)
    else:
        record = deepcopy(draft["exams"][0])
        record["id"] = "duplicate-exam"
        draft["exams"].append(record)
    with pytest.raises(ValueError):
        _finish(course, draft)
    assert workflow.resume(course["root"])["run_manifest"] is None


@pytest.mark.parametrize("problem", ["missing", "unresolved", "conflict"])
def test_incomplete_or_conflicting_solutions_are_reported_partial(make_course, problem):
    course = make_course()
    draft = _draft(course)
    solution = next(s for s in draft["solutions"] if s["question_id"] == "q-a2")
    if problem == "missing":
        draft["solutions"].remove(solution)
    elif problem == "unresolved":
        solution.update(coverage="unresolved", verification="unresolved", note="해설 검증 미완료")
    else:
        solution["verification"] = "conflict"
    result = _finish(course, draft)
    _, run, names = _package(result)
    assert result["stage"] == "partial" and run["validation"]["passed"] is False
    assert run["validation"]["blockers"] and run["limitations"]
    coverage = run["validation"]["solution_coverage"]
    if problem == "conflict":
        assert solution["id"] in coverage["conflicts"]
    else:
        assert "q-a2" in coverage["missing"]
    _no_generation(result, names)


def test_real_progress_and_classification_corrections_survive_fresh_sessions(make_course):
    course = make_course(("course.txt", "exam_a.txt", "exam_b.txt", "exam_c.txt"))
    initial_draft = _draft(course)
    first = _finish(course, initial_draft)
    assert _fresh_resume(course)["mastery_state"]["observations"] == []
    today = date.today()
    wrong = workflow.record(course["root"], "q-a1a", False, note="양변 연산을 놓침", observed_at=today.isoformat())
    right = workflow.record(course["root"], "q-a2", True, note="원래 함수와 대조함", observed_at=today.isoformat())
    assert wrong["review_due"] == (today + timedelta(days=1)).isoformat()
    assert right["review_due"] == (today + timedelta(days=3)).isoformat()
    progress = _fresh_resume(course)
    assert progress["mastery_state"]["observations"] == [wrong, right]
    assert progress["error_log"]["entries"] == [wrong]
    assert progress["mastery_state"]["topics"]["t-equation"]["status"] == "needs_review"
    assert progress["mastery_state"]["topics"]["t-derivative"]["status"] == "observed_correct"
    overlay = {"topic_ids": ["t-equation"], "pattern": "수동 수정 분류", "method": "원문 검토 후 분류 수정",
               "confidence": 1, "needs_review": False}
    corrected = workflow.correct(course["root"], {"q-a2": overlay})
    assert corrected["intake"] == []
    # Re-submit the old host draft: persisted human corrections still take precedence.
    result = _finish(course, initial_draft)
    resumed = _fresh_resume(course)
    assert resumed["draft"] == result["draft"]
    assert resumed["mastery_state"] == progress["mastery_state"]
    assert resumed["error_log"] == progress["error_log"]
    corrected_question = next(q for q in resumed["draft"]["questions"] if q["id"] == "q-a2")
    original_question = next(q for q in initial_draft["questions"] if q["id"] == "q-a2")
    assert all(corrected_question[field] == value for field, value in overlay.items())
    for field in ("id", "text", "number", "source_id", "location", "exam_id"):
        assert corrected_question[field] == original_question[field]
    _, run, names = _package(resumed)
    topics = {t["topic_id"]: t for t in run["analysis"]["topics"]}
    assert topics["t-equation"]["question_count"] == 4
    assert topics["t-derivative"]["question_count"] == 1
    assert topics["t-derivative"]["historical_frequency"] == pytest.approx(1 / 3)
    assert resumed["intake"] == []
    assert {t["id"] for t in resumed["draft"]["topics"]} == {t["id"] for t in first["draft"]["topics"]}
    _no_generation(resumed, names)
    _originals(course, resumed)


@pytest.mark.parametrize("revoked", ["no", None], ids=["explicit-no", "consent-withdrawn"])
def test_consent_revocation_removes_stale_09_from_directory_manifest_and_zip(make_course, revoked):
    course = make_course(("course.txt", "exercise.txt"), consent=None)
    workflow.answer(course["root"], {"generation_consent": "예"})
    initial = _finish(course, _draft(course, generated=True))
    old_output, old_run, old_names = _package(initial)
    assert old_run["new_question_count"] == 1 and GENERATED_ARTIFACT in old_names
    assert (old_output / GENERATED_ARTIFACT).is_file()
    result = workflow.replan(course["root"], {"generation_consent": revoked}, start_date=date.today().isoformat())
    output, run, names = _package(result)
    assert output == old_output and result["stage"] == "complete"
    assert run["consent_record"] == revoked
    assert result["intake"] == []
    _no_generation(result, names)
    resumed = _fresh_resume(course)
    assert resumed["profile"]["generation_consent"] == revoked
    assert resumed["draft"]["generated_questions"] == []
    assert resumed["run_manifest"] == run
    _originals(course, resumed)


def test_solution_only_input_cannot_be_reverse_engineered_into_original_questions(make_course):
    course = make_course(("course.txt", "official_complete.txt"))
    draft = _draft(course)
    result = _finish(course, draft)
    _, run, names = _package(result)
    assert result["draft"]["questions"] == [] and result["draft"]["solutions"] == []
    assert run["analysis"]["question_count"] == 0
    assert HISTORY_ARTIFACT not in names and SOLUTIONS_ARTIFACT not in names
    source = next(s for s in result["source_manifest"]["sources"] if s["filename"] == "official_complete.txt")
    fabricated = deepcopy(course["stubs"]["questions"][-1])
    fabricated.update(source_id=source["id"], location=source["sections"][0]["location"],
                      text=source["sections"][0]["text"])
    invalid = deepcopy(draft)
    invalid["questions"].append(fabricated)
    with pytest.raises(ValueError):
        _finish(course, invalid)
    assert _fresh_resume(course)["draft"]["questions"] == []
    _no_generation(result, names)


def test_permitted_but_missing_generation_is_partial(make_course):
    course = make_course(("course.txt",), consent="yes")
    result = _finish(course, _draft(course))
    _, run, names = _package(result)
    assert result["generation_policy"]["allowed"] is True
    assert result["stage"] == "partial" and run["validation"]["passed"] is False
    assert run["new_question_count"] == 0 and run["validation"]["blockers"]
    assert GENERATED_ARTIFACT not in names
