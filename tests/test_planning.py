"""Behavioral checks for independent descriptive analysis and safe scheduling."""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from studymachine import planning
from studymachine.planning import analyze_exams, build_plan, order_topics


START = date(2026, 1, 1)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def topic(identifier, **changes):
    return {"id": identifier, "title": f"주제 {identifier}", "prerequisites": [],
            "in_scope": True, "importance": 1, "weakness": 0.5,
            "estimated_minutes": 30, "references": [{"source_id": "notes", "location": "page:1"}],
            **changes}


def question(identifier, exam="a", **changes):
    return {"id": identifier, "number": identifier, "kind": "historical", "exam_id": exam,
            "source_id": "exam-" + str(exam), "location": "page:1", "text": "원본 문항 " + identifier,
            "topic_ids": ["t1"], "parent_id": None, "pattern": "방법1",
            "confidence": 1, "needs_review": False, **changes}


def draft():
    return {"schema_version": 1, "topics": [topic("t1"), topic("t2")],
            "exams": [{"id": "a", "sitting_id": "s1", "variant": "A", "source_id": "exam-a"},
                      {"id": "b", "sitting_id": "s1", "variant": "B", "source_id": "exam-b"},
                      {"id": "c", "sitting_id": "s2", "variant": "A", "source_id": "exam-c"},
                      {"id": "d", "sitting_id": "s3", "variant": "A", "source_id": "exam-d"}],
            "questions": [question("parent", is_context=True),
                          question("q1", parent_id="parent", topic_ids=["t1", "t1"]),
                          question("q2", topic_ids=["t1", "t2"]),
                          question("q3", "b"), question("q4", "c", topic_ids=["t2"], pattern="방법2"),
                          question("exercise", None, kind="exercise")]}


def profile(days=5, minutes=120, **changes):
    return {"scope": "주제 t1과 t2", "timezone": "UTC",
            "exam_at": (START + timedelta(days=days)).isoformat() + "T09:00:00+00:00",
            "availability": {key: minutes for key in WEEKDAYS}, **changes}


def blocks(plan):
    return [(day["date"], block) for day in plan["days"] for block in day["blocks"]]


def assert_capacity(plan):
    for day in plan["days"]:
        assert isinstance(day["available_minutes"], int)
        assert day["buffer_minutes"] >= 0
        assert sum(block["minutes"] for block in day["blocks"]) + day["buffer_minutes"] <= day["available_minutes"]
        assert all(isinstance(block["minutes"], int) and block["minutes"] > 0 for block in day["blocks"])


def test_frequency_has_explicit_variants_sittings_and_leaf_denominators():
    result = analyze_exams(draft())
    assert (result["exam_count"], result["sitting_count"], result["question_count"]) == (4, 3, 4)
    t1 = next(item for item in result["topics"] if item["topic_id"] == "t1")
    assert (t1["exam_count"], t1["exam_denominator"], t1["historical_frequency"]) == (2, 4, 0.5)
    assert (t1["sitting_count"], t1["sitting_denominator"], t1["sitting_frequency"]) == (1, 3, 1 / 3)
    assert (t1["question_count"], t1["question_denominator"], t1["question_share"]) == (3, 4, 0.75)
    pattern = next(item for item in result["patterns"] if item["pattern"] == "방법1")
    assert pattern["question_count"] == 3
    assert result["frequency_unit"] == "fraction"
    assert any("미래" in text for text in result["limitations"])
    assert not any("probability" in key for item in result["topics"] for key in item)


def test_corrected_records_recompute_without_mutating_input():
    data = draft()
    original = deepcopy(data)
    first = analyze_exams(data)
    assert data == original
    data["questions"][1]["topic_ids"] = ["t2"]
    data["questions"][1]["pattern"] = "수정한 방법"
    second = analyze_exams(data)
    assert first["topics"][0]["question_count"] == 3
    assert second["topics"][0]["question_count"] == 2
    assert any(row["pattern"] == "수정한 방법" for row in second["patterns"])


@pytest.mark.parametrize("error", ["question_id", "exam_id", "topic_ref", "exam_ref", "sitting", "source_duplicate", "variant_duplicate", "parent"])
def test_bad_historical_records_are_rejected(error):
    data = draft()
    if error == "question_id":
        data["questions"].append(deepcopy(data["questions"][1]))
    elif error == "exam_id":
        data["exams"].append(deepcopy(data["exams"][0]))
    elif error == "topic_ref":
        data["questions"][1]["topic_ids"] = ["missing"]
    elif error == "exam_ref":
        data["questions"][1]["exam_id"] = "missing"
    elif error == "sitting":
        data["exams"][0]["sitting_id"] = None
    elif error == "source_duplicate":
        data["questions"].append({**data["questions"][1], "id": "other-id"})
    elif error == "variant_duplicate":
        data["exams"].append({**data["exams"][0], "id": "other-id"})
    else:
        data["questions"][1]["parent_id"] = "q4"
    with pytest.raises(ValueError):
        analyze_exams(data)


def test_no_exams_and_review_uncertainty_are_explicit():
    empty = analyze_exams({"topics": [topic("t1")], "questions": [], "exams": []})
    assert empty["topics"][0]["exam_denominator"] == 0
    assert empty["topics"][0]["historical_frequency"] == 0
    data = draft()
    data["questions"][1]["needs_review"] = True
    assert any("검토" in text for text in analyze_exams(data)["limitations"])


def test_order_respects_prerequisites_before_high_priority_dependents_and_is_stable():
    topics = [topic("dependent", importance=100, prerequisites=["base"]), topic("base"), topic("a")]
    result = [row["id"] for row in order_topics(topics)]
    assert result.index("base") < result.index("dependent")
    assert result == [row["id"] for row in order_topics(list(reversed(topics)))]


@pytest.mark.parametrize("topics", [
    [topic("a", prerequisites=["b"]), topic("b", prerequisites=["a"])],
    [topic("a", prerequisites=["a"])], [topic("a", prerequisites=["missing"])],
    [topic("a"), topic("a")],
])
def test_graph_cycles_and_invalid_references_rejected(topics):
    with pytest.raises(ValueError):
        order_topics(topics)
    with pytest.raises(ValueError):
        build_plan(profile(), topics, [], {}, START)


@pytest.mark.parametrize(("days", "mode"), [(1, "very_short"), (5, "short"), (10, "medium"), (30, "long")])
def test_arbitrary_horizons_have_real_dates_and_feasible_capacity(days, mode):
    result = build_plan(profile(days), [topic("t1"), topic("t2", prerequisites=["t1"])], [], {}, START)
    assert result["mode"] == mode
    assert len(result["days"]) == days
    assert result["start_date"] == START.isoformat()
    assert result["end_date"] == (START + timedelta(days=days)).isoformat()
    assert result["days"][-1]["date"] == (START + timedelta(days=days - 1)).isoformat()
    assert not result["unscheduled"]
    assert_capacity(result)
    assert any("오류" in block["task"] for _, block in blocks(result))
    assert "최종 점검" in result["days"][-1]["blocks"][-1]["task"]
    assert all(any("가" <= char <= "힣" for char in block[field])
               for _, block in blocks(result) for field in ("task", "completion"))


def test_long_horizon_places_actual_spaced_reviews_without_starving_dependent_core():
    topics = [topic("t1", estimated_minutes=60), topic("t2", estimated_minutes=60, prerequisites=["t1"])]
    result = build_plan(profile(30, 180), topics, [], {}, START)
    cores = [(day, block["topic_id"]) for day, block in blocks(result) if "핵심 개념" in block["task"]]
    assert cores == [(START.isoformat(), "t1"), (START.isoformat(), "t2")]
    for identifier in ("t1", "t2"):
        reviews = [date.fromisoformat(day) for day, block in blocks(result)
                   if block["topic_id"] == identifier and block["review"]]
        assert reviews == [START + timedelta(days=n) for n in (1, 3, 7)]
    assert_capacity(result)


def test_review_uses_nearest_available_later_date():
    availability = {key: 0 for key in WEEKDAYS}
    availability.update({START.isoformat(): 100, (START + timedelta(days=2)).isoformat(): 100})
    result = build_plan(profile(5, availability=availability), [topic("t1", estimated_minutes=60)], [], {}, START)
    reviews = [day for day, block in blocks(result) if block["topic_id"] == "t1" and block["review"]]
    assert reviews and set(reviews) == {(START + timedelta(days=2)).isoformat()}
    assert_capacity(result)


def test_date_overrides_weekday_and_zero_is_real_capacity():
    p = profile(5, 100)
    p["availability"][START.isoformat()] = 0
    p["availability"][(START + timedelta(days=1)).isoformat()] = 40
    result = build_plan(p, [topic("t1", estimated_minutes=100)], [], {}, START)
    assert [day["available_minutes"] for day in result["days"][:3]] == [0, 40, 100]
    assert result["days"][0]["blocks"] == []
    assert_capacity(result)


def test_unknown_daily_capacity_is_omitted_not_invented():
    result = build_plan(profile(5, availability={START.isoformat(): 60}), [topic("t1")], [], {}, START)
    assert result["conditional"]
    assert len(result["days"]) == 1
    assert result["days"][0]["available_minutes"] == 60
    assert any("가용 시간" in text for text in result["limitations"])
    assert_capacity(result)


@pytest.mark.parametrize("changes", [
    {"availability": None}, {"availability": {}}, {"exam_at": None},
    {"timezone": None}, {"timezone": "No/Such_Zone"},
])
def test_missing_essential_calendar_fields_produce_conditional_plan(changes):
    result = build_plan(profile(**changes), [topic("t1")], [], {}, START)
    assert result["conditional"]
    assert result["days"] == []
    assert result["unscheduled"][0]["remaining_minutes"] == 39
    assert result["limitations"]


def test_unknown_scope_or_exam_time_is_conditional_with_known_earlier_capacity():
    result = build_plan(profile(scope=None, exam_at="2026-01-04"), [topic("t1")], [], {}, START)
    assert result["conditional"]
    assert len(result["days"]) == 3
    assert_capacity(result)


def test_out_of_scope_prerequisite_warns_without_scope_expansion():
    topics = [topic("base", in_scope=False), topic("t1", prerequisites=["base"])]
    result = build_plan(profile(), topics, [], {}, START)
    assert not any(block["topic_id"] in {"base", "t1"} for _, block in blocks(result))
    assert "범위 밖" in result["unscheduled"][0]["reason"]


def test_overload_keeps_buffers_recap_and_reports_unachievable_scope():
    result = build_plan(profile(1, 20), [topic("t1", estimated_minutes=200)], [], {}, START)
    assert result["unscheduled"][0]["remaining_minutes"] > 0
    assert any("전체 범위" in text for text in result["limitations"])
    assert result["days"][0]["buffer_minutes"] == 2
    assert_capacity(result)


def test_calendar_only_same_day_is_conditional_and_does_not_assume_midnight_start():
    result = build_plan(profile(0), [topic("t1")], [], {}, START)
    assert result["conditional"]
    assert result["days"] == []
    assert any("시작 시각" in text for text in result["limitations"])


def test_exact_same_day_and_offset_conversion_never_schedule_after_exam():
    # 14:30+09 is 05:30 UTC; the actual remaining window is 30 minutes.
    result = build_plan(profile(0, 300, exam_at="2026-01-01T15:00:00+09:00"),
                        [topic("t1")], [], {}, "2026-01-01T14:30:00+09:00")
    assert result["days"][0]["available_minutes"] == 30
    assert result["mode"] == "very_short"
    assert_capacity(result)


@pytest.mark.parametrize("start", ["2026-01-01T09:00:00+00:00", "2026-01-01T10:00:00+00:00"])
def test_exam_at_or_before_start_has_no_scheduled_work(start):
    result = build_plan(profile(0), [topic("t1")], [], {}, start)
    assert result["mode"] == "expired"
    assert result["days"] == []
    assert result["unscheduled"]


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        assert tz is timezone.utc
        return cls(2026, 1, 1, 23, 30, tzinfo=timezone.utc)


def test_default_start_is_aware_utc_clock_and_optional_keyword(monkeypatch):
    monkeypatch.setattr(planning, "datetime", FixedClock)
    result = build_plan(profile(), [topic("t1")], [], {})
    assert result["start_date"] == "2026-01-01"
    assert result["days"][0]["available_minutes"] == 30
    assert_capacity(result)


def test_default_without_valid_timezone_warns_conditional_utc(monkeypatch):
    monkeypatch.setattr(planning, "datetime", FixedClock)
    result = build_plan(profile(timezone=None), [topic("t1")], [], {}, start_date=None)
    assert result["start_date"] == "2026-01-01"
    assert result["conditional"] and result["days"] == []
    assert any("UTC" in text for text in result["limitations"])


def test_default_start_uses_student_timezone_not_host_calendar(monkeypatch):
    try:
        ZoneInfo("Asia/Seoul")
    except ZoneInfoNotFoundError:
        pytest.skip("IANA timezone database unavailable; Windows runtime needs tzdata")
    monkeypatch.setattr(planning, "datetime", FixedClock)
    result = build_plan(profile(timezone="Asia/Seoul"), [topic("t1")], [], {})
    assert result["start_date"] == "2026-01-02"


@pytest.mark.parametrize("value", ["2026-03-08T02:30:00", "2026-11-01T01:30:00"])
def test_dst_gap_and_ambiguous_naive_exam_time_require_explicit_offset(value):
    try:
        ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        pytest.skip("IANA timezone database unavailable; Windows runtime needs tzdata")
    with pytest.raises(ValueError, match="explicit UTC offset"):
        build_plan(profile(timezone="America/New_York", exam_at=value), [topic("t1")], [], {}, START)


def test_alternatives_are_distinct_feasible_and_do_not_add_hours():
    result = build_plan(profile(10, 120), [topic("t1"), topic("t2", prerequisites=["t1"])], [], {}, START)
    totals = {}
    for name, variant in result["alternatives"].items():
        assert_capacity(variant)
        assert [day["available_minutes"] for day in variant["days"]] == [day["available_minutes"] for day in result["days"]]
        totals[name] = sum(block["minutes"] for _, block in blocks(variant))
    assert totals["minimal"] < totals["realistic"] < totals["intensive"]
    minimal_topics = {block["topic_id"] for _, block in blocks(result["alternatives"]["minimal"])}
    assert "t2" not in minimal_topics
    assert "t1" in minimal_topics


def test_tasks_reference_unchanged_supplied_questions_and_sources_without_mutating():
    topics = [topic("t1")]
    questions = [question("q1")]
    p = profile()
    before = deepcopy((p, topics, questions))
    result = build_plan(p, topics, questions, {}, START)
    linked = [block for _, block in blocks(result) if block["topic_id"] == "t1"]
    assert all(block["question_ids"] == ["q1"] for block in linked)
    assert all(block["source_ids"] == ["exam-a", "notes"] for block in linked)
    assert (p, topics, questions) == before


@pytest.mark.parametrize("capacity", [-1, 1.5, True, float("nan")])
def test_invalid_capacities_are_rejected(capacity):
    with pytest.raises(ValueError):
        build_plan(profile(availability={"thursday": capacity}), [topic("t1")], [], {}, START)


def test_history_raises_priority_descriptively_without_overriding_prerequisites():
    topics = [topic("a"), topic("b")]
    analysis = {"topics": [{"topic_id": "a", "historical_frequency": 0},
                           {"topic_id": "b", "historical_frequency": 1}]}
    result = build_plan(profile(), topics, [], analysis, START)
    assert next(block["topic_id"] for _, block in blocks(result)) == "b"
    topics[1]["prerequisites"] = ["a"]
    result = build_plan(profile(), topics, [], analysis, START)
    assert next(block["topic_id"] for _, block in blocks(result)) == "a"


def test_incomplete_prerequisite_prevents_dependent_core_and_reports_both():
    result = build_plan(profile(1, 40), [topic("a", estimated_minutes=100),
                                        topic("b", prerequisites=["a"])], [], {}, START)
    assert not any(block["topic_id"] == "b" for _, block in blocks(result))
    assert {item["topic_id"] for item in result["unscheduled"]} == {"a", "b"}
    assert_capacity(result)


def test_recap_remains_last_when_final_calendar_day_has_no_capacity():
    availability = {key: 100 for key in WEEKDAYS}
    availability[(START + timedelta(days=4)).isoformat()] = 0
    result = build_plan(profile(5, availability=availability), [topic("t1")], [], {}, START)
    for variant in [result, *result["alternatives"].values()]:
        last_working = [day for day in variant["days"] if day["blocks"]][-1]
        assert "최종 점검" in last_working["blocks"][-1]["task"]
        assert_capacity(variant)


def test_missing_capacity_alternatives_preserve_conditional_warning():
    result = build_plan(profile(availability=None), [topic("t1")], [], {}, START)
    for alternative in result["alternatives"].values():
        assert alternative["conditional"] and alternative["days"] == []
        assert any("가용 시간" in text for text in alternative["limitations"])


def test_analysis_is_deterministic_under_reordered_inputs():
    data = draft()
    original = analyze_exams(data)
    data["topics"].reverse()
    data["exams"].reverse()
    data["questions"].reverse()
    assert analyze_exams(data) == original


@pytest.mark.parametrize("days,mode", [(2, "short"), (7, "short"), (8, "medium"), (21, "medium"), (22, "long")])
def test_exact_horizon_mode_boundaries(days, mode):
    exam = (START + timedelta(days=days)).isoformat() + "T00:00:00+00:00"
    assert build_plan(profile(exam_at=exam), [topic("t1")], [], {}, START)["mode"] == mode
