"""Render supplied semantic study content; never generate questions or mastery.

The caller owns schema/policy validation and the authoritative manifest. The
returned metadata describes real files only. The convenience ZIP has an explicit
file list, and the caller may replace it after finalizing manifest.json.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from .policy import GenerationPolicy, PolicyViolation


FILENAMES = {
    "start": "00_시험대비_안내.md",
    "inventory": "01_시험범위_자료검증.md",
    "concepts": "02_시험범위_개념총정리.md",
    "history": "03_기출문제_출제경향_분석.md",
    "solutions": "04_기출문제_해설가이드.md",
    "schedule": "05_시험일까지_학습계획.md",
    "checklist": "06_복습_체크리스트.md",
    "index": "07_제공문제_인덱스.md",
    "usage": "08_학습_진행방법.md",
    "generated": "09_AI생성_연습문제_및_해설.md",
}

_CATEGORIES = {
    "syllabus": "강의계획서", "lecture_slides": "강의 슬라이드", "textbook": "교재",
    "lecture_notes": "강의 노트", "assignment": "과제·제공 연습문제",
    "historical_exam": "기출문제", "official_solution": "공식·교수자 해설",
    "student_solution": "학생 작성 해설", "answer_key": "정답표",
    "formula_sheet": "공식표", "other": "기타 자료",
}
_STATUSES = {"processed": "처리됨", "partial": "일부만 처리됨", "failed": "읽기 실패"}
_ORIGINS = {"official": "제공된 공식 해설", "student": "제공된 학생 해설",
            "answer_key": "제공된 정답표", "ai": "AI가 작성한 누락 풀이·추론 보충"}
_COVERAGE = {"complete": "전체 해설", "partial": "일부 해설", "answer_only": "정답만 있음",
             "unresolved": "미해결"}
_VERIFICATION = {"verified": "검증됨", "unchecked": "미검증", "conflict": "불일치 확인 필요",
                 "unresolved": "검증 미해결"}
_DOCUMENT_SUFFIXES = {
    ".pdf", ".ppt", ".pptx", ".doc", ".docx", ".txt", ".md", ".csv", ".tsv",
    ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff",
}
_DISPLAY_KEYS = {
    "monday": "월요일", "tuesday": "화요일", "wednesday": "수요일", "thursday": "목요일",
    "friday": "금요일", "saturday": "토요일", "sunday": "일요일", "pattern": "풀이 구조",
    "topic_id": "주제", "exam_count": "관찰 시험지 수", "exam_denominator": "전체 시험지 수",
    "historical_frequency": "과거 관찰 비율", "sitting_count": "관찰 시행 수",
    "sitting_denominator": "전체 시행 수", "sitting_frequency": "시행별 관찰 비율",
    "question_count": "문항 수", "question_denominator": "전체 문항 수", "question_share": "문항 비율",
    "remaining_minutes": "남은 학습 시간(분)", "reason": "이유", "status": "상태",
    "question_id": "문항", "correct": "정답 여부", "observed_at": "풀이 기록일",
    "review_due": "복습 예정일", "note": "메모",
}


def _items(value):
    return value if isinstance(value, (list, tuple)) else []


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _text(value, fallback="미확인"):
    if value is None or value == "":
        return fallback
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(v) for v in value) or fallback
    if isinstance(value, bool):
        return "예" if value else "아니요"
    if isinstance(value, Mapping):
        return ", ".join(f"{_DISPLAY_KEYS.get(k, k)}: {_text(v)}" for k, v in value.items()) or fallback
    return str(value)


def _cell(value):
    return _text(value).replace("|", "\\|").replace("\n", "<br>")


def _key(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:20]


def _href(filename, anchor=""):
    return quote(filename.replace("\\", "/"), safe="/") + (f"#{anchor}" if anchor else "")


def _target(root, filename):
    path = root / filename
    if not path.resolve().is_relative_to(root):
        raise ValueError("Artifact path escapes output directory")
    return path


def _table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(_cell(v) for v in row) + " |" for row in rows), ""]


def _bullets(values):
    return [f"- {_text(value)}" for value in values] + [""]


class _Document:
    def __init__(self, title):
        self.lines = [f"# {title}", ""]
        self.source_ids = set()
        self.status = "complete"

    def add(self, *lines):
        self.lines.extend(lines)

    def section(self, title):
        self.add(f"## {title}", "")

    def missing(self, message):
        self.status = "partial"
        self.add(message, "")


class _Sources:
    """Package inert document copies and readable extracts, never execute inputs."""

    def __init__(self, root, sources):
        self.root = root
        self.records = {}
        self.extracts = {}
        self.originals = {}
        self.locations = {}
        self.metadata = []
        for index, raw in enumerate(sources):
            source = dict(_mapping(raw))
            source_id = str(source.get("id") or f"unidentified-{index + 1}")
            self.records[source_id] = source
            self._package(source_id, source)

    def _package(self, source_id, source):
        filename = f"sources/source-{_key(source_id)}.md"
        self.extracts[source_id] = filename
        doc = _Document(f"자료 사본: {self.name(source_id)}")
        doc.source_ids.add(source_id)
        doc.add(f"자료 식별자: {source_id}", "",
                f"분류: {_CATEGORIES.get(source.get('category'), '기타 자료')}", "",
                f"읽기 상태: {_STATUSES.get(source.get('status'), '미확인')}", "")
        if source.get("status") != "processed":
            doc.status = "partial"
        # A preserved ingestion copy takes precedence over the user-input path.
        stored = source.get("storage_path") or source.get("stored_path") or source.get("original_path")
        if stored and source.get("status") != "failed":
            path = Path(stored)
            # Ingestion stores immutable bytes under a hash without an extension.
            kind = str(source.get("file_type") or "").lower().lstrip(".")
            suffix = ("." + kind) if kind else Path(self.name(source_id)).suffix.lower()
            if suffix in _DOCUMENT_SUFFIXES and path.is_file():
                original_name = f"sources/source-{_key(source_id)}.original{suffix}"
                original = _target(self.root, original_name)
                original.parent.mkdir(parents=True, exist_ok=True)
                if path.resolve() == original.resolve():
                    raise ValueError("Output must not overwrite a supplied source")
                try:
                    shutil.copyfile(path, original)
                except OSError:
                    doc.missing("보존된 원본 사본을 읽거나 복사하지 못했습니다. 추출 내용의 한계를 확인하세요.")
                    original.unlink(missing_ok=True)
                    self._extract(source_id, source, filename, doc)
                    return
                expected = source.get("sha256")
                if expected and re.fullmatch(r"[a-fA-F0-9]{64}", str(expected)):
                    with original.open("rb") as stream:
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    if actual != expected.lower():
                        original.unlink()
                        doc.missing("보존 사본의 해시가 자료 기록과 달라 원본 링크를 만들지 않았습니다.")
                    else:
                        self.originals[source_id] = original_name
                else:
                    self.originals[source_id] = original_name
                if source_id in self.originals:
                    self.metadata.append({"filename": original_name, "source_ids": [source_id],
                                          "status": doc.status})
                    doc.add(f"[제공 자료의 원본 사본]({_href(original_name.rsplit('/', 1)[-1])})", "")
            else:
                doc.missing("원본 사본을 포함하지 못했습니다. 아래 추출 내용과 읽기 한계를 확인하세요.")
        self._extract(source_id, source, filename, doc)

    def _extract(self, source_id, source, filename, doc):
        self.locations[source_id] = set()
        for section in _items(source.get("sections")):
            section = _mapping(section)
            location = _text(section.get("location"), "위치 미확인")
            self.locations[source_id].add(location)
            doc.add(f'<a id="loc-{_key(location)}"></a>', "", f"## {location}", "")
            if section.get("text"):
                doc.add(str(section["text"]), "")
            else:
                doc.missing("이 구간의 본문을 읽지 못했습니다.")
        if not self.locations[source_id]:
            doc.missing("추출된 본문이 없습니다. 이 자료의 내용을 확인된 것으로 간주하지 않습니다.")
        if source.get("limitations"):
            doc.section("자료의 한계")
            doc.lines.extend(_bullets(_items(source["limitations"])))
        self.metadata.append(_write(self.root, filename, doc))

    def name(self, source_id):
        name = _text(self.records.get(source_id, {}).get("filename"), source_id)
        return re.split(r"[/\\]", name)[-1].replace("[", "(").replace("]", ")")

    def cite(self, doc, source_id, location=None):
        if source_id is None:
            doc.status = "partial"
            return "출처 미연결"
        source_id = str(source_id)
        doc.source_ids.add(source_id)
        if source_id not in self.records:
            doc.status = "partial"
            return f"출처 확인 필요 ({source_id})"
        label = self.name(source_id)
        anchor = ""
        if location:
            label += f" · {location}"
            if location in self.locations[source_id]:
                anchor = f"loc-{_key(location)}"
            else:
                doc.status = "partial"
                label += " (위치 확인 필요)"
        if self.records[source_id].get("status") != "processed":
            doc.status = "partial"
        result = f"[{label}]({_href(self.extracts[source_id], anchor)})"
        if source_id in self.originals:
            original = self.originals[source_id]
            page = re.fullmatch(r"page:(\d+)", str(location or ""))
            fragment = f"page={page[1]}" if page and original.endswith(".pdf") else ""
            result += f" ([원본 사본]({_href(original, fragment)}))"
        return result

    def references(self, doc, refs):
        links = [self.cite(doc, ref.get("source_id"), ref.get("location"))
                 for ref in _items(refs) if isinstance(ref, Mapping)]
        if not links:
            doc.status = "partial"
            return "출처 미연결 — 근거 확인 필요"
        return "; ".join(links)


def _write(root, filename, doc):
    path = _target(root, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(doc.lines).rstrip() + "\n", encoding="utf-8")
    return {"filename": filename, "source_ids": sorted(doc.source_ids), "status": doc.status}


def _topic_order(topics):
    """Order presentation by dependencies; report cycles instead of hiding content."""
    pending = list(topics)
    ordered = []
    while pending:
        pending_ids = {t.get("id") for t in pending}
        ready = [t for t in pending if not pending_ids.intersection(_items(t.get("prerequisites")))]
        if not ready:
            return ordered + pending, True
        ordered.extend(ready)
        pending = [t for t in pending if t not in ready]
    return ordered, False


def _semantic_list(doc, sources, heading, values):
    if not values:
        return
    doc.add(f"### {heading}", "")
    labels = {"term": "용어", "definition": "정의", "name": "이름", "formula": "식",
              "expression": "식", "conditions": "적용 조건", "steps": "순서", "text": "내용",
              "description": "설명", "explanation": "설명", "title": "항목", "meaning": "뜻"}
    for value in _items(values):
        if isinstance(value, Mapping):
            fields = [f"{labels.get(k, '내용')}: {_text(v)}" for k, v in value.items()
                      if k not in {"id", "references"} and v is not None]
            doc.add("- " + "; ".join(fields), "")
            if value.get("references"):
                doc.add("  근거: " + sources.references(doc, value["references"]), "")
        else:
            doc.add(f"- {value}", "")


def _question_link(question):
    return f"[{_text(question.get('number'), question.get('id', '문항'))}]({_href(FILENAMES['index'], 'q-' + _key(question.get('id')))})"


def _limit_lines(*objects):
    values = []
    for obj in objects:
        for value in _items(_mapping(obj).get("limitations")):
            text = _text(value)
            if text not in values:
                values.append(text)
    return values


def render_package(output_dir, profile, manifest, draft, analysis, plan, policy, mastery, errors, qa):
    """Return ``list[{filename, source_ids, status}]`` for rendered package files.

    Content comes from a caller-validated semantic draft. Missing optional fields
    produce honest partial sections, not invented explanations or study results.
    Original document bytes are copied from ingestion's storage_path when present;
    original_path is only a compatibility fallback. No source is executed.
    """
    profile, manifest, draft, analysis, plan, policy, mastery, errors, qa = (
        _mapping(obj) for obj in (profile, manifest, draft, analysis, plan, policy, mastery, errors, qa)
    )
    questions = _items(draft.get("questions"))
    policy_sources = [{**s, "category": s.get("category", "other"),
                       "status": s.get("status", "failed"), "sections": _items(s.get("sections"))}
                      for s in _items(manifest.get("sources"))]
    effective = GenerationPolicy.evaluate({"sources": policy_sources}, questions, policy.get("consent"))
    effective.assert_generation(_items(draft.get("generated_questions")))
    if "allowed" in policy and policy["allowed"] is not effective.allowed:
        raise PolicyViolation("Renderer permission disagrees with the central generation policy")
    policy = effective.to_dict()
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    sources = _Sources(root, _items(manifest.get("sources")))
    topics, cyclic = _topic_order([t for t in _items(draft.get("topics")) if t.get("in_scope", True)])
    topic_names = {t.get("id"): _text(t.get("title"), t.get("id", "주제"))
                   for t in _items(draft.get("topics"))}
    question_by_id = {q.get("id"): q for q in questions}
    solutions = _items(draft.get("solutions"))
    generated = _items(draft.get("generated_questions")) if policy.get("allowed") is True else []

    def usable_history(q):
        source = sources.records.get(str(q.get("source_id")), {})
        text_available = q.get("text") or any(
            s.get("text") and s.get("location") == q.get("location") for s in _items(source.get("sections"))
        )
        return q.get("kind") == "historical" and not q.get("is_context") and bool(text_available) and source.get("status") != "failed"

    historical = [q for q in questions if usable_history(q)]
    selected = {k for k in FILENAMES if k not in {"history", "solutions", "generated"}}
    if historical:
        selected.add("history")
    if questions:
        selected.add("solutions")
    if generated:
        selected.add("generated")
    # Retire only canonical renderer-owned optional files on a rerun.
    for key in FILENAMES.keys() - selected:
        _target(root, FILENAMES[key]).unlink(missing_ok=True)

    docs = {}
    limits = _limit_lines(manifest, draft, analysis, plan)
    observations = _items(mastery.get("observations"))
    days = _items(plan.get("days"))

    doc = docs["start"] = _Document("시험 대비 시작 안내")
    doc.lines.extend(_table(["항목", "확인 내용"], [
        ("과목", profile.get("subject")), ("시험 일시", profile.get("exam_at")),
        ("시간대", profile.get("timezone")), ("시험 범위", profile.get("scope")),
        ("학습 가능 시간(분)", profile.get("availability")), ("시험 방식", profile.get("format")),
        ("목표", profile.get("target")),
    ]))
    doc.section("권장 시작 순서")
    if topics:
        doc.add(f"먼저 **{topic_names.get(topics[0].get('id'))}**의 개념과 적용 조건을 확인하세요. "
                "자료검증 문서에서 빠진 범위를 확인한 뒤 학습계획의 첫 블록을 진행하세요.", "")
    else:
        doc.missing("확인된 개념 설명이 없어 학습 시작 순서를 확정하지 못했습니다. 자료검증 문서의 한계를 먼저 확인하세요.")
    doc.section("패키지 구성")
    doc.lines.extend(_bullets(f"[{FILENAMES[k]}]({_href(FILENAMES[k])})" for k in FILENAMES if k in selected))
    doc.section("학습 상태와 제한")
    if not observations:
        doc.add(f"준비도는 자기보고 정보입니다: {_text(profile.get('preparation'), '미평가')}. "
                "실제 풀이 결과가 없어 숙련도는 평가 전입니다. 이 패키지 작성은 학습 완료를 뜻하지 않습니다.", "")
    else:
        doc.add(f"실제 응답 기록 {len(observations)}건이 있습니다. 결과와 복습 예정일은 체크리스트에서 확인하세요.", "")
    if not profile.get("exam_at") or not profile.get("scope") or profile.get("availability") is None:
        doc.missing("시험 일시·범위·가능 시간 중 미확인 항목이 있습니다. 계획의 조건과 가정을 확인하세요.")
    if limits:
        doc.lines.extend(_bullets(limits))
    doc.source_ids.update(sources.records)

    doc = docs["inventory"] = _Document("시험 범위와 자료 검증")
    doc.add(f"확인된 시험 범위: {_text(profile.get('scope'))}", "")
    doc.section("자료 목록과 읽기 결과")
    rows = []
    for source_id, source in sources.records.items():
        rows.append((source_id, sources.cite(doc, source_id), _CATEGORIES.get(source.get("category"), "기타 자료"),
                     _STATUSES.get(source.get("status"), "미확인"), source.get("page_count"),
                     _text(source.get("limitations"), "기록된 한계 없음")))
    if rows:
        doc.lines.extend(_table(["ID", "자료", "분류", "읽기 상태", "쪽·슬라이드 수", "한계"], rows))
    else:
        doc.missing("등록된 자료가 없습니다. 자료 전체를 확인했다고 볼 수 없습니다.")
    doc.section("근거의 우선순위와 미확인 범위")
    doc.add("학생이 직접 지정한 시험 정보와 명시적인 시험 안내를 우선 확인합니다. "
            "강의계획서·교수자 공지·강의자료를 대조하고, 공식 해설과 학생 해설·정답표를 구분합니다. "
            "자료 사이의 충돌은 원문을 남겨 확인하며 임의로 한쪽을 정답으로 바꾸지 않습니다.", "")
    doc.add("부분 처리·읽기 실패 자료와 출처 미연결 내용은 확인된 범위에 포함하지 않습니다. "
            "기출 파일을 읽지 못한 것은 기출이 없다는 뜻이 아닙니다.", "")
    if limits:
        doc.lines.extend(_bullets(limits))

    doc = docs["concepts"] = _Document("시험 범위 개념 총정리")
    doc.add("선수 개념을 먼저 배치했습니다. 자료 근거와 AI 해석을 구분하며, 수식·조건·표기는 제공된 설명을 유지합니다.", "")
    if cyclic:
        doc.missing("선수 관계에 순환이 있어 일부 개념의 선후 순서를 확정하지 못했습니다.")
    if not topics:
        doc.missing("시험 범위에 해당하는 개념 설명이 제공되지 않았습니다. 학습 가이드가 완성된 것으로 보지 않습니다.")
    for topic in topics:
        doc.section(f"{_text(topic.get('title'), topic.get('id', '주제'))} ({_text(topic.get('id'))})")
        evidence = "자료에 근거한 설명" if topic.get("evidence_kind") == "source_backed" else "AI 해석 — 근거와 대조 필요"
        doc.add(f"근거 구분: {evidence}", "")
        prerequisites = _items(topic.get("prerequisites"))
        if prerequisites:
            doc.add("선수 개념: " + ", ".join(topic_names.get(p, str(p)) for p in prerequisites), "")
        doc.add("자료: " + sources.references(doc, topic.get("references")), "")
        if topic.get("explanation"):
            doc.add(str(topic["explanation"]), "")
        else:
            doc.missing("이 개념의 상세 설명이 아직 제공되지 않았습니다.")
        for field, heading in (("definitions", "정의와 용어"), ("formulas", "공식과 적용 조건"),
                               ("procedures", "풀이 절차"), ("common_mistakes", "자주 발생하는 오류")):
            _semantic_list(doc, sources, heading, topic.get(field))

    if historical:
        doc = docs["history"] = _Document("기출문제 출제 경향 분석")
        doc.add("아래 빈도는 제공된 과거 자료의 관찰값입니다. 다음 시험의 출제 확률이나 성적 보장을 뜻하지 않습니다. "
                "분류가 불확실하거나 일부 자료를 읽지 못했다면 그 한계를 함께 해석하세요.", "")
        doc.section("시험 목록과 표본")
        for exam in _items(draft.get("exams")):
            doc.add(f"- {_text(exam.get('label'), exam.get('id', '시험'))}: "
                    f"{sources.cite(doc, exam.get('source_id'))}; "
                    f"시행 식별자 {_text(exam.get('sitting_id'))}, 시험지 변형 {_text(exam.get('variant'))}")
        doc.add("", f"분석에 기록된 시험지 수: {_text(analysis.get('exam_count'))}; "
                f"시행 수: {_text(analysis.get('sitting_count'))}; 독립 문항 수: {_text(analysis.get('question_count'))}", "")
        rows = []
        for item in _items(analysis.get("topics")):
            rows.append((topic_names.get(item.get("topic_id"), item.get("topic_id")),
                         f"{_text(item.get('exam_count'))} / {_text(item.get('exam_denominator'))}",
                         item.get("question_count"), item.get("historical_frequency")))
        if rows:
            doc.lines.extend(_table(["주제", "관찰 시험지 / 분모", "관련 문항 수", "과거 관찰 비율"], rows))
        else:
            doc.missing("검증된 주제별 빈도 계산 결과가 없습니다. 출제 비율을 임의로 채우지 않았습니다.")
        doc.section("원문 문항과 반복 구조")
        for q in historical:
            doc.add(f"- 원문 {_question_link(q)} ({q.get('id')}): {sources.cite(doc, q.get('source_id'), q.get('location'))}; "
                    f"구조 {_text(q.get('pattern'))}; 풀이 방법 {_text(q.get('method'))}")
            if q.get("difficulty") is not None:
                doc.add(f"  난이도: {_text(q['difficulty'])} — 제공된 정성 평가이며 실제 체감 난이도와 다를 수 있습니다.")
            else:
                doc.add("  난이도: 미평가 — 관찰 빈도에서 난이도를 추정하지 않았습니다.")
            if q.get("needs_review"):
                doc.add("  분류 재검토 필요: 이 문항의 주제·구조 판정이 확정되지 않았습니다.")
                doc.status = "partial"
        doc.add("")
        for pattern in _items(analysis.get("patterns")):
            doc.add("- " + _text(pattern), "")
        doc.section("난이도와 학습 우선순위")
        doc.add("난이도는 출제 빈도만으로 확정할 수 없습니다. 풀이 단계·선수 개념·실제 응답 기록을 함께 확인하세요. "
                "주제별 우선순위와 시간 배분은 학습계획의 근거와 한계를 따릅니다.", "")
        if analysis.get("limitations"):
            doc.lines.extend(_bullets(_items(analysis["limitations"])))

    if questions:
        doc = docs["solutions"] = _Document("제공 문제 해설 가이드")
        doc.add("문제의 수치·조건·번호를 바꾸지 않습니다. 제공 해설을 먼저 보존하고, 누락된 추론만 AI 보충으로 구분합니다. "
                "해설 작성은 새 문항 작성이나 학생의 풀이 완료를 뜻하지 않습니다.", "")
        unresolved = []
        for q in questions:
            doc.section(f"문항 {_text(q.get('number'), q.get('id'))} ({_text(q.get('id'))})")
            doc.add(f"원문: {_question_link(q)} — {sources.cite(doc, q.get('source_id'), q.get('location'))}", "")
            if q.get("is_context"):
                doc.add("상위 문항의 공통 지문입니다. 하위 문항별 해설을 확인하세요.", "")
                continue
            matches = [s for s in solutions if s.get("question_id") == q.get("id")]
            supplied = [s for s in matches if s.get("origin") != "ai"]
            complete = any(s.get("coverage") == "complete" for s in supplied)
            additions = [s for s in matches if s.get("origin") == "ai"]
            for solution in supplied + ([] if complete else additions):
                doc.add(f"### {_ORIGINS.get(solution.get('origin'), '제공 해설')}", "",
                        f"범위: {_COVERAGE.get(solution.get('coverage'), '미확인')}; "
                        f"확인 상태: {_VERIFICATION.get(solution.get('verification'), '미검증')}", "")
                if solution.get("text"):
                    doc.add(str(solution["text"]), "")
                else:
                    doc.missing("연결된 해설의 본문이 없습니다.")
                doc.add("근거: " + sources.references(doc, solution.get("references")), "")
                if solution.get("note"):
                    doc.add("확인 메모: " + str(solution["note"]), "")
                if solution.get("verification") in {"conflict", "unresolved"}:
                    doc.missing("해설에 불일치 또는 미해결 사항이 있습니다. 제공된 원문을 유지했으며 정답으로 단정하지 않습니다.")
            if complete and additions:
                doc.missing("제공된 전체 해설을 우선 보존했습니다. 중복 AI 해설은 표시하지 않았습니다.")
            shown = supplied + ([] if complete else additions)
            if not any(s.get("coverage") == "complete" and s.get("text") for s in shown):
                unresolved.append(q)
                doc.missing("누락된 상세 풀이가 아직 제공되지 않았습니다. 해결 완료로 표시하지 않습니다.")
        if unresolved:
            doc.section("미해결·풀이 보충 대기")
            doc.lines.extend(_bullets(_question_link(q) for q in unresolved))

    doc = docs["schedule"] = _Document("시험일까지의 개인 학습계획")
    doc.add(f"기간: {_text(plan.get('start_date'))} ~ {_text(plan.get('end_date'))}", "")
    if plan.get("conditional"):
        doc.missing("조건부 계획입니다. 미확인 시험 정보나 학습 가능 시간을 임의로 채우지 않았습니다.")
    if plan.get("assumptions"):
        doc.section("계획의 전제")
        doc.lines.extend(_bullets(_items(plan["assumptions"])))
    if not days:
        doc.missing("확정된 날짜별 학습 블록이 없습니다. 가능한 시간을 확인하기 전에는 실행 가능한 일정으로 보지 않습니다.")
    for day in days:
        doc.section(_text(day.get("date"), "날짜 미확인"))
        blocks = _items(day.get("blocks"))
        total = sum(b.get("minutes", 0) for b in blocks if isinstance(b.get("minutes"), (int, float)))
        doc.add(f"학습 배정: {total}분; 가능 시간: {_text(day.get('available_minutes'))}분; "
                f"여유 시간: {_text(day.get('buffer_minutes'))}분", "")
        for block in blocks:
            doc.add(f"### {topic_names.get(block.get('topic_id'), _text(block.get('topic_id'), '종합 복습'))}", "",
                    f"할 일: {_text(block.get('task'))}", "",
                    f"시간: {_text(block.get('minutes'))}분; 우선순위: {_text(block.get('priority'))}", "")
            refs = [sources.cite(doc, sid) for sid in _items(block.get("source_ids"))]
            for qid in _items(block.get("question_ids")):
                q = question_by_id.get(qid)
                if q:
                    refs.append(_question_link(q) + " — " + sources.cite(doc, q.get("source_id"), q.get("location")))
                else:
                    refs.append(f"문항 연결 확인 필요 ({qid})")
                    doc.status = "partial"
            if refs:
                doc.add("사용 자료·원문 문항: " + "; ".join(refs), "")
            review = block.get("review")
            review_text = "복습 블록" if review is True else "기본 학습 블록" if review is False else _text(review, "별도 복습 계획 미기록")
            doc.add(f"완료 기준: {_text(block.get('completion'))}", "", f"복습 계획: {review_text}", "")
    if plan.get("alternatives"):
        doc.section("학습 강도별 대안")
        alternatives = plan["alternatives"]
        alternatives = alternatives.values() if isinstance(alternatives, Mapping) else _items(alternatives)
        for alternative in alternatives:
            doc.add(f"### {_text(alternative.get('label'), '대안 학습계획')}", "")
            rows = []
            for day in _items(alternative.get("days")):
                blocks = _items(day.get("blocks"))
                minutes = sum(b.get("minutes", 0) for b in blocks if isinstance(b.get("minutes"), (int, float)))
                rows.append((day.get("date"), minutes, day.get("available_minutes"), day.get("buffer_minutes"),
                             "; ".join(_text(b.get("task")) for b in blocks) or "배정된 학습 없음"))
                for block in blocks:
                    doc.source_ids.update(str(sid) for sid in _items(block.get("source_ids")))
                    for qid in _items(block.get("question_ids")):
                        if qid in question_by_id:
                            doc.source_ids.add(str(question_by_id[qid].get("source_id")))
            doc.lines.extend(_table(["날짜", "배정(분)", "가능(분)", "여유(분)", "할 일"], rows))
            if alternative.get("conditional"):
                doc.add("확인된 정보가 부족하여 조건부로 제시된 대안입니다.", "")
            doc.lines.extend(_bullets(_items(alternative.get("limitations"))))
    if plan.get("unscheduled"):
        doc.section("시간 부족 등으로 배정되지 않은 학습")
        doc.lines.extend(_bullets(_items(plan["unscheduled"])))
        doc.status = "partial"
    doc.section("시험 전 마지막 날 점검")
    doc.lines.extend(_bullets(_items(plan.get("final_checklist"))))
    doc.add("새 범위를 늘리기 전에 예정된 복습과 오답 확인을 마치세요. 공식의 적용 조건, 제공 원문 문항, "
            "교수자 안내·준비물·시험 시각을 대조하세요. 실제 완료 여부는 학생의 수행 후에 기록합니다.", "")
    if plan.get("limitations"):
        doc.lines.extend(_bullets(_items(plan["limitations"])))

    doc = docs["checklist"] = _Document("복습과 학습 진행 체크리스트")
    doc.add("체크 항목은 앞으로 수행할 학습입니다. 패키지 작성만으로 완료 처리하지 않습니다. "
            "정답 여부와 복습 시점은 실제 응답 기록에 근거합니다.", "")
    doc.section("핵심 개념·공식·절차")
    for topic in topics:
        doc.add(f"- [ ] {topic_names.get(topic.get('id'))}: 정의·적용 조건·풀이 절차를 원문과 대조", "",
                "  자료: " + sources.references(doc, topic.get("references")), "")
        for field, label in (("formulas", "공식"), ("procedures", "절차"), ("common_mistakes", "주의할 오류")):
            _semantic_list(doc, sources, f"{topic_names.get(topic.get('id'))} — {label}", topic.get(field))
    doc.section("제공 문항 복습 범위")
    for q in questions:
        if not q.get("is_context"):
            kind = "기출" if q.get("kind") == "historical" else "제공 연습문제"
            doc.add(f"- [ ] {kind} {_question_link(q)}: " + sources.cite(doc, q.get("source_id"), q.get("location")), "")
    doc.section("날짜별 실행 확인")
    for day in days:
        for block in _items(day.get("blocks")):
            doc.add(f"- [ ] {_text(day.get('date'))} — {_text(block.get('task'))} "
                    f"({_text(block.get('minutes'))}분); 완료 기준: {_text(block.get('completion'))}", "")
    doc.section("실제 응답과 복습 예정")
    if not observations:
        doc.add("실제 풀이 기록 없음 — 숙련도 평가 전. 맞힌 문항 수나 향상률을 추정하지 않았습니다.", "")
    for observation in observations:
        q = question_by_id.get(observation.get("question_id"))
        result = "정답 기록" if observation.get("correct") is True else "오답 기록" if observation.get("correct") is False else "결과 미확인"
        label = _question_link(q) if q else _text(observation.get("question_id"))
        doc.add(f"- {label}: {result}; 기록일 {_text(observation.get('observed_at'))}; "
                f"복습 예정 {_text(observation.get('review_due'))}; 메모 {_text(observation.get('note'), '없음')}", "")
    entries = _items(errors.get("entries"))
    if entries:
        doc.section("확인된 오류와 보충 과제")
        for entry in entries:
            doc.add(f"- 문항 {_text(entry.get('question_id'))}; "
                    f"원인·메모: {_text(entry.get('reason') or entry.get('note'))}; "
                    f"복습 예정: {_text(entry.get('review_due'))}", "")

    doc = docs["index"] = _Document("제공 문제 원문 인덱스")
    doc.add("기출과 일반 제공 연습문제를 구분합니다. 아래 본문은 입력된 원문을 유지하며, 읽히지 않은 문장을 복원해 만들지 않습니다.", "")
    for kind, heading in (("historical", "기출문제"), ("exercise", "제공 연습문제")):
        group = [q for q in questions if q.get("kind", "exercise") == kind]
        if not group:
            continue
        doc.section(heading)
        for q in group:
            doc.add(f'<a id="q-{_key(q.get("id"))}"></a>', "",
                    f"### {_text(q.get('number'), q.get('id'))} ({_text(q.get('id'))})", "",
                    "출처: " + sources.cite(doc, q.get("source_id"), q.get("location")), "")
            if q.get("parent_id"):
                doc.add(f"상위 문항: {q['parent_id']}", "")
            if q.get("is_context"):
                doc.add("공통 지문 — 독립 문항 수에 포함하지 않습니다.", "")
            if q.get("text"):
                doc.add(str(q["text"]), "")
            else:
                doc.missing("문항 본문을 판독하지 못했습니다. 연결된 자료를 확인하세요. 내용을 추정해 만들지 않았습니다.")
    if not questions:
        doc.add("연결된 제공 문항이 없습니다. 해설만 있는 자료에서 원래 문제를 역으로 만들지 않습니다.", "")

    doc = docs["usage"] = _Document("학습 진행 방법")
    doc.add("1. 자료검증에서 시험 범위와 누락 구간을 확인합니다.\n"
            "2. 개념총정리를 선수 개념부터 읽고 학습계획의 날짜별 블록을 진행합니다.\n"
            "3. 제공 문제 인덱스로 원문을 열고 수치·조건·선택지를 그대로 사용합니다.\n"
            "4. 먼저 직접 풀어 본 뒤 제공 해설과 AI 보충 추론을 구분하여 대조합니다.\n"
            "5. 실제 풀이 결과를 알려 주면 약점과 복습 일정을 갱신할 수 있습니다.", "")
    doc.section("이어 하기와 계획 변경")
    doc.add('다음 대화에서 같은 과목 자료와 함께 “오늘 할 학습을 이어서 진행해 줘”라고 요청하세요. '
            "확인 가능한 저장 상태가 없으면 이전 진행이 복원되었다고 가정하지 않습니다. "
            "계획보다 늦어지면 실제 완료한 블록과 남은 시간을 알려 주세요. 이미 끝낸 것으로 표시하지 않고 남은 일정을 조정합니다.", "")
    doc.add("해설이 다르면 문항 번호·자료 위치·의심되는 단계를 알려 주세요. 공식 해설을 유지하면서 불일치와 검증 결과를 따로 기록합니다.", "")
    doc.section("새 문제 생성 제한")
    doc.add("기출문제가 있으면 새 문제·수치 변경·유사 문제·새 진단 문항을 만들지 않습니다. "
            "기출이 없더라도 명시적 허용이 있어야 새 연습문제를 사용할 수 있습니다. 무응답과 읽기 실패는 허용이 아닙니다.", "")
    doc.add("현재 적용 상태: " + ("새 연습문제 생성 허용" if policy.get("allowed") is True else "새 연습문제 생성 금지"), "")
    if policy.get("reason"):
        doc.add("적용 사유: " + str(policy["reason"]), "")
    if generated:
        doc.add(f"허용된 초안의 AI 생성 문제는 [{FILENAMES['generated']}]({_href(FILENAMES['generated'])})에 따로 표시했습니다.", "")
    doc.section("자료와 검증 한계")
    doc.add("패키지의 sources 폴더를 문서와 함께 보관하세요. 자료 링크는 이 폴더의 사본을 가리킵니다. "
            "원래 업로드 파일은 변경하지 않습니다. 패키지에는 개인 수업 자료가 포함될 수 있으므로 본인의 학습 저장소에서 보관하세요.", "")
    qa_status = qa.get("status")
    passed = qa.get("passed") is True or qa_status in {"passed", "complete"}
    doc.add("검증 보고 상태: " + ("제공된 검증 결과 통과" if passed else "미실행 또는 확인·보완 필요"), "")
    if not passed:
        doc.status = "partial"
    for field in ("blockers", "errors", "warnings", "limitations"):
        if qa.get(field):
            doc.lines.extend(_bullets(_items(qa[field])))
    doc.source_ids.update(sources.records)

    if generated:
        doc = docs["generated"] = _Document("AI 생성 연습문제와 해설")
        doc.add("다음은 명시적으로 허용된 초안의 AI 생성 연습문제입니다. 실제 기출문제가 아닙니다. "
                "연도·교수자·배점은 추정해 부여하지 않았습니다.", "")
        for item in generated:
            doc.section(f"AI 생성 연습문제 ({_text(item.get('id'))})")
            for field, heading in (("text", "문제"), ("answer", "정답"), ("explanation", "해설")):
                doc.add(f"### {heading}", "")
                if item.get(field):
                    doc.add(str(item[field]), "")
                else:
                    doc.missing(f"{heading} 내용이 아직 제공되지 않았습니다.")
            doc.add("근거: " + sources.references(doc, item.get("references")), "")

    metadata = list(sources.metadata)
    for key in FILENAMES:
        if key in docs:
            metadata.append(_write(root, FILENAMES[key], docs[key]))
    archive_path = _target(root, "package.zip")
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for record in metadata:
            archive.write(_target(root, record["filename"]), record["filename"])
    metadata.append({"filename": "package.zip",
                     "source_ids": sorted({sid for record in metadata for sid in record["source_ids"]}),
                     "status": "partial" if any(r["status"] == "partial" for r in metadata) else "complete"})
    return metadata
