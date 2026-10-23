"""Checkpointed host-agent orchestration: inventory -> one intake -> semantics -> package."""

import hashlib
import re
import shutil
import tempfile
import uuid
import zipfile
from copy import deepcopy
from pathlib import Path

from .contracts import validate, validate_draft
from .intake import apply_answers, intake_batch
from .learning import record_result, solution_coverage
from .policy import GenerationPolicy
from .state import load_state, private_root, save_json


def prepare(root, paths, profile=None, categories=None, defer_intake=False):
    from .ingestion import ingest

    root = private_root(root)
    if (root / "state.json").exists():
        return resume(root)
    profile = {"schema_version": 1, "course_id": "course-" + uuid.uuid4().hex[:16],
               "language": "ko", **(profile or {})}
    validate("course_profile", profile)
    state = {"schema_version": 1, "stage": "inventoried", "course_profile": profile,
             "source_manifest": ingest(paths, root / "materials", categories),
             "mastery_state": {"schema_version": 1, "observations": [], "topics": {}},
             "error_log": {"schema_version": 1, "entries": []}, "corrections": {}, "intake_answered": False}
    validate("source_manifest", state["source_manifest"])
    state["intake"] = intake_batch(profile, state["source_manifest"])
    state["stage"] = "inventoried" if defer_intake else "awaiting_intake" if state["intake"] else "awaiting_semantics"
    save_json(root / "state.json", state)
    return resume(root)


def open_intake(root, facts=None):
    root = private_root(root)
    state = load_state(root)
    if state["stage"] != "inventoried":
        raise ValueError("Only preliminary inventory may open the one student intake")
    state["course_profile"].update(facts or {})
    validate("course_profile", state["course_profile"])
    state["intake"] = intake_batch(state["course_profile"], state["source_manifest"])
    state["stage"] = "awaiting_intake" if state["intake"] else "awaiting_semantics"
    save_json(root / "state.json", state)
    return resume(root)


def review_sources(root, reviews):
    """Import the hosting agent's actual visual reading, never automatic OCR guesses."""
    root = private_root(root)
    state = load_state(root)
    if state["stage"] not in ("inventoried", "awaiting_semantics"):
        raise ValueError("Source review is permitted before intake or during semantic processing")
    sources = {s["id"]: s for s in state["source_manifest"]["sources"]}
    for review in reviews:
        source = sources.get(review["source_id"])
        if not source:
            raise ValueError("Unknown reviewed source")
        if review.get("method") not in ("multimodal", "native_manual") or not review.get("note"):
            raise ValueError("Review requires its actual method and an inspection note")
        if "sections" in review:
            source["sections"] = review["sections"]
        if "category" in review:
            source["category"] = review["category"]
        if "status" in review:
            source["status"] = review["status"]
        # Unreadable sections remain partial; no false full extraction status.
        if source["status"] == "processed" and not source["sections"] and source["file_type"] != "zip":
            raise ValueError("An empty source cannot be marked fully processed")
        if review.get("history_resolution"):
            if source["status"] != "processed" or not source["sections"] or source["category"] == "historical_exam":
                raise ValueError("History suspicion requires an actual complete reading of a nonhistorical source to resolve")
            if any(q["kind"] == "historical" and q["source_id"] == source["id"] for q in state.get("draft", {}).get("questions", [])):
                raise ValueError("Confirmed historical questions cannot be reclassified to unlock generation")
            source.setdefault("initial_history_suspicion", bool(source.get("suspected_history") or source.get("unreadable_history")))
            source["suspected_history"] = False
            source["unreadable_history"] = False
            source["history_resolution"] = review["history_resolution"]
        source["limitations"] = review.get("limitations", source["limitations"])
        source.setdefault("reviews", []).append(review)
    validate("source_manifest", state["source_manifest"])
    save_json(root / "state.json", state)
    return resume(root)


def answer(root, answers):
    root = private_root(root)
    state = load_state(root)
    if state["intake_answered"] or state["stage"] not in ("awaiting_intake", "awaiting_semantics"):
        raise ValueError("Intake has already been consumed; resume without asking a second batch")
    state["course_profile"] = apply_answers(state["course_profile"], answers,
                                            [q["field"] for q in state["intake"]])
    validate("course_profile", state["course_profile"])
    state["intake_answered"] = True
    state["stage"] = "awaiting_semantics"
    save_json(root / "state.json", state)
    return resume(root)


def resume(root):
    state = load_state(root)
    policy = GenerationPolicy.evaluate(state["source_manifest"], state.get("draft", {}).get("questions", []),
                                       state["course_profile"].get("generation_consent"))
    return {"stage": state["stage"], "intake": state["intake"] if state["stage"] == "awaiting_intake" else [],
            "profile": state["course_profile"], "source_manifest": state["source_manifest"],
            "generation_policy": policy.to_dict(), "mastery_state": state["mastery_state"],
            "error_log": state["error_log"], "draft": state.get("draft"),
            "run_manifest": state.get("run_manifest"), "output_dir": str(Path(root).resolve() / "output")}


def _quality(state, draft, plan, coverage):
    limitations = list(draft["limitations"]) + list(plan.get("limitations", []))
    blockers = []
    for source in state["source_manifest"]["sources"]:
        if source.get("storage_path") and source.get("sha256"):
            original = Path(source["storage_path"])
            if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != source["sha256"]:
                blockers.append(f"보존 원본 사본의 무결성을 확인하지 못했습니다: {source['filename']}")
        if source["status"] != "processed":
            blockers.append(f"자료 처리 제한: {source['filename']} ({source['status']})")
        limitations.extend(source["limitations"])
        archive_with_members = source["file_type"] == "zip" and any(s.get("archive_parent_id") == source["id"] for s in state["source_manifest"]["sources"])
        if source["category"] == "historical_exam" and not archive_with_members and not any(q["source_id"] == source["id"] for q in draft["questions"]):
            blockers.append(f"기출 문항을 확인하지 못한 자료: {source['filename']}")
    if not any(t["in_scope"] for t in draft["topics"]):
        blockers.append("검증된 시험 범위 개념이 없어 개념 자료가 불완전합니다.")
    if coverage["missing"]:
        blockers.append("풀이가 미완료인 제공 문항: " + ", ".join(coverage["missing"]))
    if coverage["conflicts"]:
        blockers.append("원본 풀이와 검산 결과의 충돌: " + ", ".join(coverage["conflicts"]))
    if any(q.get("needs_review") for q in draft["questions"]):
        blockers.append("확인이 필요한 문항 분류 또는 판독 결과가 있습니다.")
    if plan.get("conditional"):
        blockers.append("시험 일정·범위·공부 가능 시간 중 미확정 정보가 있어 조건부 계획입니다.")
    if plan.get("unscheduled"):
        limitations.append("가용 시간에 포함하지 못한 학습 활동이 있습니다. 계획의 미배정 목록을 확인하세요.")
    for day in plan["days"]:
        if sum(b["minutes"] for b in day["blocks"]) + day.get("buffer_minutes", 0) > (day["available_minutes"] or 0):
            raise ValueError("Schedule exceeds daily availability")
        if any(b["minutes"] <= 0 for b in day["blocks"]):
            raise ValueError("Nonpositive study block")
    unchecked = [s["id"] for s in draft["solutions"] if s["verification"] in ("unchecked", "unresolved")]
    if unchecked:
        limitations.append("검산이 완료되지 않은 해설: " + ", ".join(unchecked))
    limitations = list(dict.fromkeys(limitations + blockers))
    return {"passed": not blockers, "blockers": blockers, "limitations": limitations,
            "source_traceability": "validated", "scheduling_arithmetic": "validated",
            "generation_policy": "validated", "solution_coverage": coverage,
            "unchecked_solutions": unchecked, "semantic_correctness": "host_agent_review_required"}


def localize_documents(directory, artifacts, draft, language):
    """Host translations retain filenames, original statements and navigable evidence."""
    if language in (None, "ko", "ko-KR", "한국어"):
        return True
    translations = draft.get("localized_documents")
    if not translations:
        return False
    names = {a["filename"] for a in artifacts if a["filename"].endswith(".md") and "/" not in a["filename"]}
    if set(translations) != names:
        raise ValueError("Localization must cover exactly the applicable Markdown artifacts")
    link_pattern = r"\]\(([^)]+)\)"
    for name in names:
        path = directory / name
        original = path.read_text(encoding="utf-8")
        translated = translations[name]
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError("Localized artifact is empty")
        if not set(re.findall(link_pattern, original)) <= set(re.findall(link_pattern, translated)):
            raise ValueError("Localization removed source or navigation links")
        anchor_pattern = r'<[^>]+\bid=[\"\x27]([^\"\x27]+)[\"\x27]'
        if not set(re.findall(anchor_pattern, original)) <= set(re.findall(anchor_pattern, translated)):
            raise ValueError("Localization removed navigation anchors")
        for question in draft["questions"]:
            if question["text"] and question["text"] in original and question["text"] not in translated:
                raise ValueError("Localization must preserve the exact original question statements")
        for solution in draft["solutions"]:
            if solution["origin"] != "ai" and solution["text"] and solution["text"] in original and solution["text"] not in translated:
                raise ValueError("Localization must preserve supplied original solutions")
        path.write_text(translated, encoding="utf-8")
    return True


def finish(root, draft, start_date=None):
    from .artifacts import render_package
    from .planning import analyze_exams, build_plan, order_topics

    root = private_root(root)
    state = load_state(root)
    if state["stage"] in ("inventoried", "awaiting_intake"):
        raise ValueError("Consume the single intake answer (possibly empty) before producing the package")
    draft = deepcopy(draft)
    for q in draft.get("questions", []):
        q.update(state["corrections"].get(q["id"], {}))
    validate_draft(draft, state["source_manifest"], state.get("draft"))
    for source in state["source_manifest"]["sources"]:
        source["topic_ids"] = [t["id"] for t in draft["topics"] if any(r["source_id"] == source["id"] for r in t["references"])]
        source["question_ids"] = [q["id"] for q in draft["questions"] if q["source_id"] == source["id"]]
    policy = GenerationPolicy.evaluate(state["source_manifest"], draft["questions"],
                                       state["course_profile"].get("generation_consent"))
    policy.assert_generation(draft["generated_questions"])
    if policy.allowed and not draft["generated_questions"]:
        draft["limitations"].append("새 문제 생성에 동의했으나 생성 문제가 아직 준비되지 않았습니다.")
    coverage = solution_coverage(draft)
    order_topics(draft["topics"])
    analysis = analyze_exams(draft)
    effective_topics = deepcopy(draft["topics"])
    for t in effective_topics:
        observed = state["mastery_state"]["topics"].get(t["id"])
        if observed:
            t["weakness"] = 1.0 if observed["status"] == "needs_review" else .25
    plan = build_plan(state["course_profile"], effective_topics, draft["questions"], analysis, start_date)
    if state["mastery_state"]["observations"]:
        plan.setdefault("assumptions", []).append("실제 문항 관찰에서 오답은 취약도 1, 정답은 0.25로 임시 반영했습니다. 검증된 숙련도 점수는 아닙니다.")
    for name, value in (("exam_analysis", analysis), ("study_plan", plan),
                        ("generation_policy", policy.to_dict()), ("mastery_state", state["mastery_state"]),
                        ("error_log", state["error_log"])):
        validate(name, value)
    qa = _quality(state, draft, plan, coverage)
    if policy.allowed and not draft["generated_questions"]:
        qa["passed"] = False
        qa["blockers"].append("동의한 새 연습문제 생성이 미완료입니다.")
    # Persist semantic work before expensive rendering. Any interrupted rebuild
    # advertises a resumable stage, never the previous package as a fresh success.
    state["draft"] = draft
    state["stage"] = "awaiting_semantics"
    save_json(root / "state.json", state)
    stage = Path(tempfile.mkdtemp(prefix=".package-", dir=root))
    try:
        artifacts = render_package(stage, state["course_profile"], state["source_manifest"], draft,
                                   analysis, plan, policy.to_dict(), state["mastery_state"], state["error_log"], qa)
        # Verify the renderer's contract; ignore its archive until the authoritative manifest is saved.
        artifacts = [a for a in artifacts if a["filename"] not in ("manifest.json", "package.zip")]
        localized = localize_documents(stage, artifacts, draft, state["course_profile"].get("language"))
        if not localized:
            qa["passed"] = False
            qa["limitations"].append("요청 언어의 문서 번역이 아직 준비되지 않았습니다. 원문과 출처를 보존한 번역이 필요합니다.")
            qa["blockers"].append("요청 언어 번역 미완료")
        incomplete_artifacts = [a["filename"] for a in artifacts if a["status"] == "partial"]
        if incomplete_artifacts:
            qa["passed"] = False
            message = "일부 결과물에 미완료 내용 또는 출처 연결 제한이 있습니다: " + ", ".join(incomplete_artifacts)
            qa["blockers"].append(message)
            qa["limitations"].append(message)
        all_sources = {s["id"] for s in state["source_manifest"]["sources"]}
        for artifact in artifacts:
            path = (stage / artifact["filename"]).resolve()
            if not path.is_relative_to(stage.resolve()) or not path.is_file() or path.is_symlink():
                raise ValueError("Invalid output artifact path")
            if not set(artifact["source_ids"]) <= all_sources:
                raise ValueError("Invalid artifact source dependency")
            artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        run = {"schema_version": 1, "status": "complete" if qa["passed"] else "partial",
               "artifacts": artifacts, "generation_policy": policy.to_dict(),
               "limitations": qa["limitations"], "validation": qa,
               "sources": state["source_manifest"]["sources"], "analysis": analysis, "plan": plan,
               "consent_record": state["course_profile"].get("generation_consent"),
               "new_question_count": len(draft["generated_questions"]), "package": "package.zip"}
        validate("run_manifest", run)
        save_json(stage / "manifest.json", run)
        with zipfile.ZipFile(stage / "package.zip", "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(stage.rglob("*")):
                if path.is_file() and path.name != "package.zip":
                    if path.is_symlink():
                        raise ValueError("Symlink output is not supported")
                    bundle.write(path, path.relative_to(stage).as_posix())
        with zipfile.ZipFile(stage / "package.zip") as bundle:
            if bundle.testzip():
                raise ValueError("Corrupt package")
        output = root / "output"
        backup = root / ".previous-output"
        if backup.exists():
            shutil.rmtree(backup)
        if output.exists():
            output.rename(backup)
        try:
            stage.rename(output)
        except Exception:
            if backup.exists():
                backup.rename(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        # Persist only after output validation. A crash before this point leaves resumable old state.
        state.update({"draft": draft, "analysis": analysis, "plan": plan,
                      "generation_policy": policy.to_dict(), "run_manifest": run, "stage": run["status"]})
        save_json(root / "state.json", state)
        return resume(root)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def record(root, question_id, correct, note="", observed_at=None):
    root = private_root(root)
    state = load_state(root)
    if "draft" not in state:
        raise ValueError("Produce the initial package before recording actual results")
    entry = record_result(state, question_id, correct, note, observed_at)
    state["stage"] = "awaiting_semantics"
    save_json(root / "state.json", state)
    # Regenerate checklists and replan without adding intake or new questions.
    finish(root, state["draft"], observed_at)
    return entry


def correct(root, corrections):
    root = private_root(root)
    state = load_state(root)
    allowed = {"topic_ids", "pattern", "method", "confidence", "needs_review"}
    known = {q["id"] for q in state.get("draft", {}).get("questions", [])}
    for qid, fields in corrections.items():
        if qid not in known or not set(fields) <= allowed:
            raise ValueError("Corrections may change classification, never original question identity")
        state["corrections"].setdefault(qid, {}).update(fields)
    # Validate prospective state before writing correction overlay.
    draft = deepcopy(state["draft"])
    for q in draft["questions"]:
        q.update(state["corrections"].get(q["id"], {}))
    validate_draft(draft, state["source_manifest"], state["draft"])
    state["stage"] = "awaiting_semantics"
    save_json(root / "state.json", state)
    return finish(root, draft)


def replan(root, updates=None, start_date=None):
    root = private_root(root)
    state = load_state(root)
    updates = updates or {}
    allowed = {"exam_at", "scope", "availability", "preparation", "target", "instructor_guidance", "timezone", "language", "generation_consent"}
    if not set(updates) <= allowed:
        raise ValueError("Unsupported profile update")
    state["course_profile"].update(updates)
    validate("course_profile", state["course_profile"])
    draft = deepcopy(state["draft"])
    policy = GenerationPolicy.evaluate(state["source_manifest"], draft["questions"],
                                       state["course_profile"].get("generation_consent"))
    if not policy.allowed:
        draft["generated_questions"] = []
    state["stage"] = "awaiting_semantics"
    save_json(root / "state.json", state)
    return finish(root, draft, start_date)
