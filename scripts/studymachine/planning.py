"""Independent, deterministic exam descriptions and capacity-bounded planning.

Frequencies are fractions in [0, 1], with explicit variant, sitting and question
denominators. Planning uses a declared heuristic, never a forecast or grade model.
Calendar-only starts conservatively exclude exam-day work. An aware datetime
start additionally permits work before the exam's local timestamp.
"""

from __future__ import annotations

import heapq
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _indexed(records, label):
    result = {}
    for record in records:
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"{label} requires a nonempty id")
        if identifier in result:
            raise ValueError(f"Duplicate {label} id: {identifier}")
        result[identifier] = record
    return result


def _number(value, label, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"Invalid {label}: {value}")
    return value


def _validate_questions(questions, topics, exams=None):
    indexed = _indexed(questions, "question")
    identities = set()
    for question in indexed.values():
        if question.get("kind") not in {"historical", "exercise"}:
            raise ValueError(f"Invalid question kind: {question['id']}")
        for topic_id in question.get("topic_ids", []):
            if topic_id not in topics:
                raise ValueError(f"Unknown question topic: {topic_id}")
        parent = question.get("parent_id")
        if parent and (parent not in indexed or not indexed[parent].get("is_context")):
            raise ValueError(f"Invalid context parent: {parent}")
        exam_id = question.get("exam_id")
        if exams is not None:
            if exam_id and exam_id not in exams:
                raise ValueError(f"Unknown exam reference: {exam_id}")
            if question["kind"] == "historical" and not exam_id:
                raise ValueError(f"Historical question has no exam: {question['id']}")
        # Exact source identity detects duplicate semantic imports without
        # conflating different numbered questions that use identical wording.
        if not question.get("is_context") and all(
            question.get(key) is not None for key in ("source_id", "location", "number", "text")
        ):
            identity = tuple(question.get(key) for key in
                             ("kind", "exam_id", "source_id", "location", "number", "text"))
            if identity in identities:
                raise ValueError(f"Duplicate source question: {question['id']}")
            identities.add(identity)
    return indexed


def analyze_exams(draft):
    """Describe supplied historical leaf questions; reject ambiguous identities.

    Every registered variant is in the denominator, including one with no
    extracted questions. Multi-topic questions count once per topic, so topic
    question shares need not sum to one. Inputs, including corrections, are the
    sole source of truth; no cached or generated records are consulted.
    """
    topics = _indexed(draft.get("topics", []), "topic")
    exams = _indexed(draft.get("exams", []), "exam")
    identities = set()
    for exam in exams.values():
        if not isinstance(exam.get("sitting_id"), str) or not exam["sitting_id"].strip():
            raise ValueError(f"Explicit sitting_id required: {exam['id']}")
        if exam.get("variant") is not None:
            identity = (exam["sitting_id"], exam["variant"])
            if identity in identities:
                raise ValueError(f"Duplicate sitting/variant: {identity}")
            identities.add(identity)
    questions = _validate_questions(draft.get("questions", []), topics, exams)
    leaves = [q for q in questions.values()
              if q["kind"] == "historical" and not q.get("is_context")]
    sittings = {exam["sitting_id"] for exam in exams.values()}
    limits = ["역사적 빈도는 제공된 기출 표본의 기술 통계이며 미래 출제를 예측하지 않습니다."]
    if not leaves:
        limits.append("판독된 기출 문항이 없어 역사적 출제 경향을 판단할 수 없습니다.")
    if any(q.get("needs_review") or q.get("confidence", 1) < 0.7 for q in leaves):
        limits.append("검토가 필요한 문항도 집계에 포함되어 있습니다. 분류를 확인해 주세요.")
    represented = {q["exam_id"] for q in leaves}
    if len(represented) < len(exams):
        limits.append("문항이 추출되지 않은 시험도 분모에 포함됩니다. 미출제와 판독 누락을 구별해야 합니다.")
    if any(len(set(q.get("topic_ids", []))) > 1 for q in leaves):
        limits.append("여러 주제에 속하는 문항은 주제마다 한 번씩 집계하여 주제별 비율의 합이 1을 넘을 수 있습니다.")
    if draft.get("limitations"):
        limits.append("자료·분석의 한계가 기록되어 있습니다. 각 한계의 실제 내용을 함께 확인해 주세요.")

    def records(keys, field, extract):
        counts = Counter()
        variants = defaultdict(set)
        sessions = defaultdict(set)
        for question in leaves:
            for key in set(extract(question)):
                counts[key] += 1
                variants[key].add(question["exam_id"])
                sessions[key].add(exams[question["exam_id"]]["sitting_id"])
        return [{field: key,
                 "exam_count": len(variants[key]), "exam_denominator": len(exams),
                 "historical_frequency": len(variants[key]) / len(exams) if exams else 0.0,
                 "sitting_count": len(sessions[key]), "sitting_denominator": len(sittings),
                 "sitting_frequency": len(sessions[key]) / len(sittings) if sittings else 0.0,
                 "question_count": counts[key], "question_denominator": len(leaves),
                 "question_share": counts[key] / len(leaves) if leaves else 0.0}
                for key in sorted(keys)]

    patterns = {q["pattern"] for q in leaves if q.get("pattern")}
    return {"schema_version": 1, "exam_count": len(exams), "sitting_count": len(sittings),
            "question_count": len(leaves), "frequency_unit": "fraction",
            "topics": records(topics, "topic_id", lambda q: q.get("topic_ids", [])),
            "patterns": records(patterns, "pattern", lambda q: [q["pattern"]] if q.get("pattern") else []),
            "limitations": limits}


def _effort(topic):
    minutes = _number(topic.get("estimated_minutes", 60), "estimated_minutes", minimum=1)
    return math.ceil(minutes)


def _rank(topic, evidence):
    importance = _number(topic.get("importance", 1), "importance")
    weakness = _number(topic.get("weakness", 0.5), "weakness")
    if weakness > 1:
        raise ValueError("weakness must be between 0 and 1")
    frequency = _number(evidence.get(topic["id"], 0), "historical_frequency")
    if frequency > 1:
        raise ValueError("historical_frequency must be a fraction between 0 and 1")
    return importance * (1 + weakness) * (1 + frequency) / _effort(topic)


def _ordered(topics, evidence):
    indexed = _indexed(topics, "topic")
    pending = {}
    children = defaultdict(set)
    for identifier, topic in indexed.items():
        prerequisites = set(topic.get("prerequisites", []))
        for prerequisite in prerequisites:
            if prerequisite not in indexed:
                raise ValueError(f"Unknown prerequisite: {prerequisite}")
            children[prerequisite].add(identifier)
        pending[identifier] = len(prerequisites)
    scores = {key: _rank(topic, evidence) for key, topic in indexed.items()}
    ready = [(-scores[key], key) for key, count in pending.items() if count == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        _, key = heapq.heappop(ready)
        result.append(indexed[key])
        for child in sorted(children[key]):
            pending[child] -= 1
            if pending[child] == 0:
                heapq.heappush(ready, (-scores[child], child))
    if len(result) != len(indexed):
        raise ValueError("Prerequisite cycle: " + ", ".join(sorted(k for k, n in pending.items() if n)))
    return result


def order_topics(topics):
    """Return original topic records in deterministic prerequisite-first order."""
    return _ordered(topics, {})


def _localize(value, zone):
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(zone)
    candidates = [value.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    valid = [candidate for candidate in candidates if
             candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == value]
    if not valid or (len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset()):
        raise ValueError("Ambiguous/nonexistent local time; supply an explicit UTC offset")
    return valid[0]


def _parse_start(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("start_date must be a date or ISO date/datetime")
    return date.fromisoformat(value) if len(value) == 10 else datetime.fromisoformat(value)


def _capacities(availability):
    if availability is None:
        return None
    if not isinstance(availability, dict):
        raise ValueError("availability must map dates or weekdays to integer minutes")
    for key, minutes in availability.items():
        if key not in _WEEKDAYS:
            date.fromisoformat(key)
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0:
            raise ValueError(f"Invalid minute capacity for {key}")
    return availability


def build_plan(profile, topics, questions, analysis, start_date=None):
    """Build a Korean plan without exceeding explicit date/weekday capacities.

    Date overrides weekday. Missing days are omitted and marked conditional,
    never assumed free or available. Reserve ceil(10%) of usable capacity as buffer. Each topic
    requires its estimated core minutes plus ceil(10%) error correction and
    ceil(20%) review. These allocations are disclosed choices, not outcome claims.
    An exact datetime start bounds same-day minutes; date-only starts reserve the
    exam day because the student's actual study start is unknown.
    """
    indexed = _indexed(topics, "topic")
    _validate_questions(questions, indexed)
    evidence = {}
    for item in analysis.get("topics", []):
        if item["topic_id"] not in indexed:
            raise ValueError(f"Unknown analysis topic: {item['topic_id']}")
        if item["topic_id"] in evidence:
            raise ValueError(f"Duplicate analysis topic: {item['topic_id']}")
        evidence[item["topic_id"]] = item.get("historical_frequency", 0)
    ordered = _ordered(topics, evidence)
    selected = [topic for topic in ordered if topic.get("in_scope", True)]
    availability = _capacities(profile.get("availability"))
    # An aware UTC clock never derives the student's calendar from host timezone.
    start = _parse_start(start_date) if start_date is not None else datetime.now(timezone.utc)
    start_day = start.date() if isinstance(start, datetime) else start
    plan = {"schema_version": 1, "mode": "conditional", "start_date": start_day.isoformat(),
            "end_date": None, "conditional": False, "assumptions": [], "limitations": [],
            "days": [], "unscheduled": []}
    limits, assumptions = plan["limitations"], plan["assumptions"]
    assumptions.append("준비 우선도는 중요도 × (1 + 취약도) × (1 + 역사적 빈도) ÷ 예상 학습 분으로 계산하며 선수 주제를 먼저 배치합니다.")
    assumptions.append("확인되지 않은 역사적 빈도는 우선도 가산에 쓰지 않습니다. 학습 시간 외에 오류 점검 10%, 복습 20%, 날짜별 여유 시간 10%를 올림하여 확보합니다.")
    assumptions.append("분 단위 가용 시간은 계획 시작 이후와 시험 이전에 확보할 수 있는 시간으로 해석합니다. 실제 시각별 일정과 충돌하는지 확인해 주세요.")
    if any(key not in topic for topic in selected for key in ("estimated_minutes", "importance", "weakness")):
        assumptions.append("누락된 주제 추정값은 학습 60분·중요도 1·취약도 0.5를 임시 사용했습니다. 평가된 숙련도가 아닙니다.")
    if not profile.get("scope"):
        plan["conditional"] = True
        limits.append("시험 범위가 확인되지 않아 현재 범위로 표시된 주제만 임시 배치합니다.")
    zone = None
    if profile.get("timezone"):
        try:
            zone = timezone.utc if profile["timezone"] in {"UTC", "Etc/UTC"} else ZoneInfo(profile["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            limits.append("시간대를 확인할 수 없습니다. IANA 시간대 이름과 실행 환경의 시간대 자료를 확인해 주세요.")
    else:
        limits.append("명시된 시간대가 없어 시험 전 학습 시각을 확정할 수 없습니다.")
    if start_date is None:
        if zone is not None:
            start = start.astimezone(zone)
        else:
            plan["conditional"] = True
            limits.append("현재 시각은 UTC 기준으로만 표시했습니다. 학생 시간대가 확인될 때까지 날짜별 배치를 보류합니다.")
        plan["start_date"] = start.date().isoformat()
    exam_value = profile.get("exam_at")
    exam = None
    has_exam_time = False
    if exam_value:
        if isinstance(exam_value, datetime):
            has_exam_time = True
            exam = exam_value
        elif isinstance(exam_value, date):
            exam = datetime.combine(exam_value, time.min)
        elif isinstance(exam_value, str):
            has_exam_time = len(exam_value) != 10
            exam = datetime.fromisoformat(exam_value) if has_exam_time else datetime.combine(date.fromisoformat(exam_value), time.min)
        else:
            raise ValueError("exam_at must be an ISO date/datetime or null")
        if zone is not None:
            exam = _localize(exam, zone)
        plan["end_date"] = exam.date().isoformat()
        if not has_exam_time:
            plan["conditional"] = True
            limits.append("시험 시각이 없어 시험 당일은 학습 시간에서 제외했습니다.")
    else:
        limits.append("시험 날짜가 없어 날짜별 계획을 확정할 수 없습니다.")
    if availability is None or not availability:
        limits.append("가용 시간이 제공되지 않아 날짜별 학습 시간을 만들지 않았습니다.")
    if exam is None or zone is None or not availability:
        plan["conditional"] = True
    else:
        exact_start = isinstance(start, datetime)
        beginning = _localize(start if exact_start else datetime.combine(start, time.min), zone)
        start_day = beginning.date()
        plan["start_date"] = start_day.isoformat()
        duration = (exam.astimezone(timezone.utc) - beginning.astimezone(timezone.utc)).total_seconds()
        plan["mode"] = ("expired" if duration <= 0 else "very_short" if duration < 48 * 3600
                        else "short" if duration <= 7 * 86400 else "medium" if duration <= 21 * 86400 else "long")
        if duration <= 0:
            limits.append("시험 시각이 계획 시작 이전이거나 같습니다. 시험 이후 학습은 배치하지 않았습니다.")
        else:
            include_exam_day = exact_start and has_exam_time
            if has_exam_time and not exact_start:
                limits.append("학습 시작 시각이 없어 시험 당일을 보수적으로 제외했습니다. 시작 시각을 지정하면 시험 전 남은 시간만 배치할 수 있습니다.")
                if start_day == exam.date():
                    plan["conditional"] = True
            final_day = exam.date() if include_exam_day else exam.date() - timedelta(days=1)
            current = start_day
            while current <= final_day:
                key = current.isoformat()
                capacity = availability.get(key, availability.get(_WEEKDAYS[current.weekday()]))
                if capacity is None:
                    plan["conditional"] = True
                    limits.append(f"{key}의 가용 시간이 없어 해당 날짜에는 학습을 배치하지 않았습니다.")
                    current += timedelta(days=1)
                    continue
                else:
                    lower = max(beginning.astimezone(timezone.utc), _localize(datetime.combine(current, time.min), zone).astimezone(timezone.utc))
                    upper = min(exam.astimezone(timezone.utc), _localize(datetime.combine(current + timedelta(days=1), time.min), zone).astimezone(timezone.utc))
                    span = max(0, math.floor((upper - lower).total_seconds() / 60))
                    if capacity > span:
                        limits.append(f"{key}의 가용 시간을 계획 시작·시험 시각 사이의 실제 {span}분으로 제한했습니다.")
                    capacity = min(capacity, span)
                plan["days"].append({"date": key, "available_minutes": capacity,
                                     "buffer_minutes": math.ceil(capacity / 10) if capacity else 0,
                                     "blocks": []})
                current += timedelta(days=1)

    days = plan["days"]
    completed = {}
    pending = {}
    priorities = {topic["id"]: i for i, topic in enumerate(selected, 1)}
    final_index = next((i for i in range(len(days) - 1, -1, -1)
                        if days[i]["available_minutes"] > days[i]["buffer_minutes"]), None)
    recap_minutes = min(10, days[final_index]["available_minutes"] - days[final_index]["buffer_minutes"]) if final_index is not None else 0

    def free(index):
        day = days[index]
        reserve = recap_minutes if index == final_index else 0
        return day["available_minutes"] - day["buffer_minutes"] - reserve - sum(b["minutes"] for b in day["blocks"])

    def sources(topic):
        return sorted({ref["source_id"] for ref in topic.get("references", []) if ref.get("source_id")} |
                      {q["source_id"] for q in questions if q.get("source_id") and
                       topic["id"] in q.get("topic_ids", []) and not q.get("is_context")})

    def append(index, topic, task, minutes, review, completion):
        # A whole original question may require several topics. Link it for
        # solving only once every required topic is ready on this calendar day.
        related = sorted(q["id"] for q in questions
                         if topic["id"] in q.get("topic_ids", []) and not q.get("is_context")
                         and all(indexed[tid].get("in_scope", True) and (
                             (tid == topic["id"] and not review) or completed.get(tid, len(days)) <= index)
                             for tid in q.get("topic_ids", [])))
        days[index]["blocks"].append({"topic_id": topic["id"], "task": task, "minutes": minutes,
                                     "priority": priorities[topic["id"]], "source_ids": sources(topic),
                                     "question_ids": related, "completion": completion, "review": review})

    def defer(topic, minutes, reason):
        key = topic["id"]
        if key in pending:
            pending[key]["remaining_minutes"] += minutes
        else:
            pending[key] = {"topic_id": key, "remaining_minutes": minutes, "reason": reason}

    # Core and correction use a forward pass. Reviews cannot consume capacity
    # needed by dependent core work until this pass has completed.
    cursor = 0
    for priority, topic in enumerate(selected, 1):
        identifier = topic["id"]
        minutes = _effort(topic)
        total = minutes + math.ceil(minutes / 10) + math.ceil(minutes / 5)
        blocked = [prerequisite for prerequisite in topic.get("prerequisites", [])
                   if prerequisite not in completed]
        if blocked:
            outside = [key for key in blocked if not indexed[key].get("in_scope", True)]
            reason = ("범위 밖 선수 주제를 추가하지 않았습니다: " if outside else "선수 주제 학습이 완료되지 않았습니다: ") + ", ".join(blocked)
            limits.append(f"{topic.get('title', identifier)}: {reason}")
            defer(topic, total, reason)
            continue
        related = sorted(q["id"] for q in questions if identifier in q.get("topic_ids", []) and not q.get("is_context"))
        title = topic.get("title", identifier)
        activity = f"{title}: 개념·절차 학습 후 선수 주제가 준비된 연결 문항만 원문 풀이" if related else f"{title}: 자료를 바탕으로 핵심 개념과 절차 정리"
        stages = [(activity, minutes, "핵심 개념과 풀이 근거를 자료 위치와 함께 설명하고, 제공 문항은 원문 그대로 풀이 내용을 기록합니다."),
                  (f"{title}: 오류 점검과 수정", math.ceil(minutes / 10), "틀린 단계와 수정 근거를 기록하고, 오류가 없으면 확인한 항목을 기록합니다.")]
        remaining_total = minutes + math.ceil(minutes / 10)
        for task, effort, completion in stages:
            remaining = effort
            while remaining and cursor < len(plan["days"]):
                available = free(cursor)
                if available <= 0:
                    cursor += 1
                    continue
                allocated = min(available, remaining)
                append(cursor, topic, task, allocated, False, completion)
                remaining -= allocated
                remaining_total -= allocated
            if remaining:
                break
        if remaining_total:
            defer(topic, remaining_total + math.ceil(minutes / 5), "확인된 시험 전 가용 시간이 부족하거나 필수 일정 정보가 없습니다.")
        else:
            completed[identifier] = cursor

    for topic in selected:
        identifier = topic["id"]
        if identifier not in completed:
            continue
        done_index = completed[identifier]
        done_day = date.fromisoformat(days[done_index]["date"])
        last_day = date.fromisoformat(days[-1]["date"])
        targets = [done_day + timedelta(days=offset) for offset in (1, 3, 7)
                   if done_day + timedelta(days=offset) <= last_day]
        targets = targets or [done_day]
        budget = math.ceil(_effort(topic) / 5)
        targets = targets[:budget]
        for sequence, target in enumerate(targets):
            remaining = budget // len(targets) + (sequence < budget % len(targets))
            # Prefer a later calendar day, then the available date nearest the
            # intended interval. Same-day retrieval is an explicit fallback.
            candidates = sorted(range(done_index + 1, len(days)), key=lambda i: (
                abs((date.fromisoformat(days[i]["date"]) - target).days),
                date.fromisoformat(days[i]["date"]) < target, days[i]["date"]))
            candidates.append(done_index)
            for index in candidates:
                allocated = min(free(index), remaining)
                if allocated <= 0:
                    continue
                append(index, topic, f"{topic.get('title', identifier)}: 간격 복습 (목표 {target.isoformat()})", allocated, True,
                       "자료를 가리고 배운 개념·절차를 설명한 뒤 원문과 대조하고 남은 오류를 보완합니다.")
                remaining -= allocated
                if index == done_index:
                    limits.append(f"{topic.get('title', identifier)}: 이후 날짜의 여유가 부족해 일부 복습을 학습 당일에 배치했습니다.")
                if not remaining:
                    break
            if remaining:
                defer(topic, remaining, "시험 전 복습에 필요한 가용 시간이 부족합니다.")

    plan["final_checklist"] = ["시험 날짜·시각·장소와 준비물을 확인합니다.",
                               "확인된 시험 범위의 핵심 개념·공식과 남은 오류를 점검합니다.",
                               "제공된 기출·해설의 미해결 항목과 자료의 판독 제한을 확인합니다."]
    if final_index is not None and recap_minutes:
        days[final_index]["blocks"].append({"topic_id": None,
            "task": "시험 전 최종 점검: 핵심 내용·미해결 오류·시간·준비물 확인", "minutes": recap_minutes,
            "priority": len(selected) + 1, "source_ids": [], "question_ids": [],
            "completion": "시험 일정과 준비물, 핵심 내용, 남은 오류를 체크리스트에 표시합니다.", "review": True})
    plan["unscheduled"] = sorted(pending.values(), key=lambda item: priorities[item["topic_id"]])
    if plan["unscheduled"]:
        limits.append("전체 범위를 완료할 시간을 확보하지 못했습니다. 미배치 주제와 남은 분을 확인하고 범위·우선순위·가용 시간을 조정해 주세요.")
    plan["alternatives"] = _alternatives(plan, selected, completed)
    return plan


def _alternatives(plan, topics, completed):
    """Offer less/more work without increasing any declared daily capacity."""
    eligible = [topic["id"] for topic in topics if topic["id"] in completed]
    minimal_ids = set(eligible[:max(1, math.ceil(len(eligible) / 2))])
    # The prefix is topological, so every prerequisite of a selected completed
    # topic is retained. Context-free recap remains in every alternative.
    minimum = deepcopy(plan["days"])
    for day in minimum:
        day["blocks"] = [block for block in day["blocks"] if block["topic_id"] is None or block["topic_id"] in minimal_ids]
    intensive = deepcopy(plan["days"])
    for index, day in enumerate(intensive):
        free = day["available_minutes"] - day["buffer_minutes"] - sum(b["minutes"] for b in day["blocks"])
        ready = [topic for topic in topics if topic["id"] in completed and completed[topic["id"]] <= index]
        if not ready or free <= 0:
            continue
        topic = ready[index % len(ready)]
        base = next((block for block in day["blocks"] if block["topic_id"] == topic["id"]), None)
        recap_position = next((i for i, block in enumerate(day["blocks"])
                               if block["topic_id"] is None), len(day["blocks"]))
        day["blocks"].insert(recap_position, {
            "topic_id": topic["id"], "task": f"{topic.get('title', topic['id'])}: 선택 추가 복습과 오류 재점검",
            "minutes": min(20, free), "priority": len(topics) + 1,
            "source_ids": list(base["source_ids"]) if base else sorted({ref["source_id"] for ref in topic.get("references", []) if ref.get("source_id")}),
            "question_ids": list(base["question_ids"]) if base else [],
            "completion": "이미 학습한 내용을 다시 설명하고 기존 오류 기록과 대조합니다.", "review": True})
    return {"minimal": {"label": "최소 학습안", "days": minimum, "conditional": plan["conditional"],
                        "limitations": list(plan["limitations"]) + ["우선순위가 높은 완료 가능 주제와 선수 주제에 집중하며 나머지 범위는 생략됩니다."],
                        "skipped_topic_ids": [topic["id"] for topic in topics if topic["id"] not in minimal_ids]},
            "realistic": {"label": "기본 학습안", "days": deepcopy(plan["days"]), "conditional": plan["conditional"],
                          "limitations": list(plan["limitations"])},
            "intensive": {"label": "집중 학습안", "days": intensive, "conditional": plan["conditional"],
                          "limitations": list(plan["limitations"]) + ["기본 계획에서 남은 가용 시간에만 날짜별 최대 20분의 선택 복습을 추가합니다. 가용 시간이 부족하면 기본안과 같습니다."]}}
