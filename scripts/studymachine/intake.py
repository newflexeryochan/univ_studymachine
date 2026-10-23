"""One adaptive batch, with absent answers never becoming consent."""

QUESTIONS = [
    ("subject", "과목명이 무엇인가요?"),
    ("exam_at", "시험 날짜와 시간을 알려 주세요. 모르면 미정이라고 적어 주세요."),
    ("scope", "정확한 시험 범위와 제외 범위를 알려 주세요."),
    ("availability", "날짜별 또는 평일·주말별 공부 가능한 시간을 알려 주세요."),
    ("format", "시험 형식은 무엇인가요? 객관식·서술·계산·증명·오픈북 등을 적어 주세요."),
    ("preparation", "현재 준비 수준과 특히 어려운 부분을 알려 주세요."),
    ("target", "목표 성적이나 원하는 학습 수준이 있나요?"),
    ("instructor_guidance", "교수님이 강조하거나 제외한 내용이 있나요?"),
]


def intake_batch(profile, manifest):
    questions = [{"field": k, "text": t} for k, t in QUESTIONS if profile.get(k) in (None, "", {})]
    history = any(s["category"] == "historical_exam" or s.get("suspected_history") or s.get("unreadable_history")
                  for s in manifest["sources"])
    if not history and profile.get("generation_consent") not in ("yes", "no"):
        questions = questions[:7]
        questions.append({
            "field": "generation_consent",
            "text": "기출문제가 확인되지 않았습니다. 강의자료를 바탕으로 새로운 연습문제를 생성할까요?",
            "choices": ["예", "아니요"],
        })
    return questions[:8]


def apply_answers(profile, answers, allowed_fields=None):
    result = dict(profile)
    permitted = {key for key, _ in QUESTIONS} | {"generation_consent", "language", "timezone"}
    if allowed_fields is not None:
        permitted &= set(allowed_fields) | {"language", "timezone"}
    for key, value in answers.items():
        if key not in permitted:
            raise ValueError(f"Unexpected intake field: {key}")
        if key == "generation_consent":
            value = {"예": "yes", "아니요": "no", "Yes": "yes", "No": "no"}.get(value, value)
            if value not in ("yes", "no", None):
                raise ValueError("Generation consent must be explicit yes/no or null")
        result[key] = value
    result.setdefault("language", "ko")
    return result
