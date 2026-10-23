"""Single fail-closed authority for all new question generation."""

from dataclasses import asdict, dataclass


class PolicyViolation(ValueError):
    pass


@dataclass(frozen=True)
class GenerationPolicy:
    allowed: bool
    consent: str | None
    historical_present: bool
    unreadable_history: bool
    reason: str
    schema_version: int = 1

    @classmethod
    def evaluate(cls, manifest, questions=(), consent=None):
        history = [s for s in manifest["sources"] if s["category"] == "historical_exam"
                   or s.get("suspected_history") or s.get("unreadable_history")]
        historical = bool(history) or any(q.get("kind") == "historical" for q in questions)
        unreadable = any(s.get("unreadable_history") or s["status"] != "processed" or not s["sections"] for s in history)
        allowed = not historical and not unreadable and consent == "yes"
        reason = (
            "기출 자료 또는 아직 해소되지 않은 기출 의심 기록이 있어 새 문제 생성이 금지됩니다." if historical else
            "새 연습문제 생성에 명시적으로 동의했습니다." if allowed else
            "새 문제 생성 동의가 없거나 거절되어 생성하지 않습니다."
        )
        return cls(allowed, consent, historical, unreadable, reason)

    def assert_generation(self, items):
        if items and not self.allowed:
            raise PolicyViolation(self.reason)

    def to_dict(self):
        return asdict(self)
