# Semantic authoring

Use [../docs/CONTRACT.md](../docs/CONTRACT.md) as the authoritative shared contract, together with current declared adapter extensions. Read this reference at `awaiting_semantics`; it is the hosting agent's task, not a Python solver interface. A deterministic validator cannot infer course meaning, solve an arbitrary exam, or establish educational correctness. Do not deliver an empty topic shell, a canned fixture answer, or a statement such as “apply the relevant formula” as a detailed solution.

## Read, map, explain, verify

1. Read the finalized profile, original uploads, registered sections, source reviews, and policy. Identify confirmed scope, exclusions, unresolved scope, instructor guidance, and source hierarchy. Explicit exam instructions and reliable course materials outweigh generic subject expectations; preserve conflicting evidence instead of inventing certainty.
2. Inspect the raw uploaded page/image when mathematics, diagrams, tables, or answer choices depend on layout. Cross-check negative signs, exponents, subscripts, bounds, units, labels, and conditions. If tools are unavailable or a symbol remains ambiguous, name the source/location, mark the question for review, and keep the affected solution unresolved. Do not guess from OCR. Import an actual reading through `review` at `awaiting_semantics`; preserve the full replacement section list and remaining limitations.
3. Build stable course-specific topic IDs and prerequisite dependencies. Cover the whole confirmed scope with definitions, formulas, conditions of use, reasoning, procedures, and common mistakes. Explain why steps are valid and where a method does not apply. Cite the actual notes/slide/page supporting the concept; label agent interpretation. Do not expand scope silently to include excluded prerequisites or outside research.
4. Preserve exact supplied question text or a faithful registered source reference. Create separate leaf IDs for subquestions and retain shared statements as `is_context: true` parents. Do not change numbers, choices, variables, or diagrams. Match original exam variants and sittings; do not count copies as independent history. Ordinary assignments use `kind: "exercise"` and do not contribute to historical counts.
5. Match every leaf to all relevant supplied solution evidence. Prefer official/instructor work. Preserve student work and answer keys with their actual origin. Complete supplied reasoning receives navigation and consistency checking rather than a redundant AI replacement. Partial reasoning and answer-only entries receive only the missing AI additions. Never reconstruct an absent question from a solution file.
6. Solve missing coverage on the exact supplied problem. Show significant intermediate steps, assumptions and conditions, units, edge cases, and the final conclusion. Cite the original question plus the applicable course method. Label AI additions `AI 작성 해설` by default or the requested-language equivalent. Independently check arithmetic, substitutions, dimensions, or proof logic where feasible. Keep original conflicting answers and explain the disagreement separately.
7. Recheck generation policy before writing any new question, including diagnostics, flashcards, changed-input examples, remedial drills, or mocks. Any history or unreadable suspected history forbids it, regardless of consent. With no history/suspicion and explicit yes, generate source-grounded practice plus answers/explanations, with honest AI attribution. No answer means no generation. Concept summaries, existing-question explanations, and review checklists do not require new-question consent.
8. Check references, complete coverage, Korean/requested-language teaching quality, and unresolved content before `finish`. The draft's `limitations` must state actual gaps. `verified` means a check was actually performed; use `unchecked`, `conflict`, or `unresolved` honestly. A programmatic pass is not permission to hide a semantic gap.

## Draft shape and field decisions

The top-level object has `schema_version: 1`, `topics`, `exams`, `questions`, `solutions`, `generated_questions`, and `limitations`. Arrays may be empty only when genuinely inapplicable; an applicable concept guide cannot be an empty shell. Optional `localized_documents` maps exact applicable Markdown filenames to complete translations as described in [workflow.md](workflow.md).

| Record | Fields and decisions |
| --- | --- |
| Topic | `id`, `title`, `prerequisites` (existing IDs), `in_scope`, `importance`, `weakness`, `estimated_minutes`, substantive `explanation`, `definitions`, `formulas`, `procedures`, `common_mistakes`, nonempty `references`, `evidence_kind` (`source_backed` or `ai_interpretation`). Importance/effort are disclosed estimates; default weakness 0.5 means unassessed planning need, not measured mastery. |
| Exam | `id`, `label`, historical `source_id`, explicit `sitting_id`, `variant`. Shared sitting IDs group genuine variants; do not combine unrelated unknown sittings. A synthetic example must be labeled synthetic rather than presented as a real exam record. |
| Question | `id`, original `number`, `kind` (`historical` or `exercise`), `source_id`, registered `location`, unchanged `text`, `topic_ids`, `exam_id` (historical required; exercise usually null), `parent_id`, `pattern`, `method`, `confidence`, `needs_review`. Context parents add `is_context: true`. Preserve identity across later runs. |
| Solution | `id`, `question_id`, `origin` (`official`, `student`, `answer_key`, `ai`), `coverage` (`complete`, `partial`, `answer_only`, `unresolved`), `text`, nonempty `references`, `verification` (`verified`, `unchecked`, `conflict`, `unresolved`), `note`. Supplied text remains exact; use separate AI records for missing reasoning. |
| Generated question | `id`, machine `label: "AI 생성 연습문제"`, `text`, `answer`, substantive `explanation`, nonempty source `references`. Keep these outside supplied-question and historical registries. All generation paths must be allowed. |
| Citation | `{source_id, location}` from actual registered sections. Never fabricate `page:1` when only a line-range section exists. A filename or raw path is not a source ID. |

Use unique stable IDs and reject dangling references, prerequisite cycles, or duplicate imports. A single historical question assigned to several topics contributes once to each topic; their shares need not sum to 100%. Report variant/sitting/question denominators and insufficient-sample/extraction limitations. Never turn frequency or classification confidence into a future appearance probability.

## Solution coverage examples

| Supplied evidence | Agent action |
| --- | --- |
| Complete official solution for 1(가), nothing for 1(나) | Preserve/link 1(가), author only 1(나). |
| Official partial working for 1(가) | Preserve its exact text, explain only the missing steps in a separate AI record; check the combined explanation covers the leaf. |
| Answer key gives only “−2” | Preserve the answer-only record; derive the missing reasoning in an AI record and check agreement. |
| Student working disagrees with official solution | Preserve both origins, verify what can be checked, mark the conflict, explain the evidence; do not silently replace either source. |
| Unreadable question or unresolved proof | Retain actual readable context and citations; mark review/unresolved and report partial coverage. Do not invent missing conditions. |
| Solutions with no original questions | Inventory the solutions; no fictional question reconstruction or historical-question count. |

Before claiming `complete`, inspect the substance as well as the schema. A `coverage: "complete"` AI record must genuinely explain the missing work; the flag is not a substitute for that work. If a checker leaves an unchecked solution as a limitation, the host must still decide whether educational uncertainty requires a partial result.

## Complete worked draft for the synthetic texts

Continue the real text walkthrough in [workflow.md](workflow.md). This explicit example demonstrates semantic authoring and citation binding for that source set only. Read those texts first. It is not a reusable arbitrary-matrix solver or a production fixture selector. Execute the following Python block in the agent's installed environment after `answer`; it writes only the private course's `draft.json`.

```python
import json
import os
from fractions import Fraction as F
from pathlib import Path

root = Path(os.environ["STUDYMACHINE_STATE"])
state = json.loads((root / "state.json").read_text(encoding="utf-8"))
sources = {s["filename"]: s for s in state["source_manifest"]["sources"]}
def ref(name):
    source = sources[name]
    assert source["status"] == "processed" and len(source["sections"]) == 1
    return {"source_id": source["id"], "location": source["sections"][0]["location"]}
notes, exam, key = ref("lecture_notes.txt"), ref("historical_exam.txt"), ref("official_key.txt")
exam_lines = sources["historical_exam.txt"]["sections"][0]["text"].splitlines()
key_lines = sources["official_key.txt"]["sections"][0]["text"].splitlines()

# Independent exact-arithmetic check of the explanation below, not inferred mastery.
A = [[F(1), F(2)], [F(3), F(4)]]
B = [[F(-2), F(1)], [F(3, 2), F(-1, 2)]]
def product(left, right):
    return [[sum(left[i][k] * right[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
assert A[0][0] * A[1][1] - A[0][1] * A[1][0] == -2
assert product(A, B) == product(B, A) == [[1, 0], [0, 1]]

topics = [
    {"id": "t-det", "title": "2×2 행렬의 행렬식", "prerequisites": [],
     "in_scope": True, "importance": 1, "weakness": 0.5, "estimated_minutes": 25,
     "explanation": "A=[[a,b],[c,d]]에서 행렬식은 ad-bc이다. 주대각 성분의 곱 ad에서 다른 대각 성분의 곱 bc를 빼므로 순서와 부호를 구별해야 한다. 행렬식은 행렬과 달리 하나의 수이며 음수도 가능하다. 이 강의자료의 역행렬 공식은 행렬식이 0이 아닐 때만 적용되므로, 역행렬 계산보다 먼저 행렬식을 확인한다. 제공 기출 1(가)의 계산은 별도 해설에서 원래 행렬로 수행한다.",
     "definitions": ["2×2 행렬 A의 행렬식은 det(A)=ad-bc로 계산하는 수이다."],
     "formulas": ["det([[a,b],[c,d]])=ad-bc"],
     "procedures": ["a,b,c,d의 위치를 원문과 대조한다.", "ad와 bc를 따로 계산한 뒤 ad-bc를 구한다.", "역행렬이 필요한 경우 결과가 0인지 먼저 확인한다."],
     "common_mistakes": ["ad-bc를 ad+bc 또는 bc-ad로 계산함", "행렬식이 음수라는 이유로 역행렬이 없다고 판단함"],
     "references": [notes], "evidence_kind": "source_backed"},
    {"id": "t-inverse", "title": "2×2 역행렬의 계산과 검산", "prerequisites": ["t-det"],
     "in_scope": True, "importance": 1, "weakness": 0.5, "estimated_minutes": 35,
     "explanation": "먼저 det(A)를 계산한다. 0이면 자료의 역행렬 공식을 적용할 수 없고 역행렬이 없다. 0이 아니면 주대각의 a,d를 맞바꾸고 비대각 b,c의 부호를 바꾼 행렬 전체에 1/det(A)를 곱한다. 일부 성분에만 분모를 적용하면 다른 행렬이 된다. 구한 후보 B는 원래 A와 곱해 각 성분을 계산하고 AB=I 및 BA=I인지 확인한다. 계산 결과만 쓰지 말고 존재 조건, 공식 대입, 성분 계산, 곱셈 검산을 함께 기록한다.",
     "definitions": ["역행렬 B는 AB=BA=I를 만족하는 행렬이다."],
     "formulas": ["A^(-1)=(1/(ad-bc))*[[d,-b],[-c,a]], ad-bc != 0"],
     "procedures": ["행렬식을 계산하여 0이 아닌지 확인한다.", "대각 교환과 비대각 부호 변경 후 전체를 행렬식으로 나눈다.", "두 곱 AB, BA가 단위행렬인지 성분별로 검산한다."],
     "common_mistakes": ["대각 성분도 부호만 바꿈", "행렬식의 음수 부호를 누락함", "곱셈 검산에서 행과 열을 혼동함"],
     "references": [notes], "evidence_kind": "source_backed"},
]
def question(qid, number, text, topic_ids, parent=None, context=False):
    return {"id": qid, "number": number, "kind": "historical", **exam,
        "text": text, "topic_ids": topic_ids, "exam_id": "e-2025-a", "parent_id": parent,
        "pattern": None if context else "2×2 행렬 계산",
        "method": None if context else "행렬식 및 역행렬 공식",
        "confidence": 1.0, "needs_review": False, "is_context": context}
questions = [question("q1", "1", exam_lines[1], [], context=True),
    question("q1a", "1(가)", exam_lines[2], ["t-det"], "q1"),
    question("q1b", "1(나)", exam_lines[3], ["t-det", "t-inverse"], "q1")]
solutions = [
    {"id": "s-key-1a", "question_id": "q1a", "origin": "answer_key", "coverage": "answer_only",
     "text": key_lines[1], "references": [key], "verification": "verified",
     "note": "공식 정답표를 그대로 보존했다. 계산 과정은 제공되지 않았다. 독립 계산과 일치한다."},
    {"id": "s-ai-1a", "question_id": "q1a", "origin": "ai", "coverage": "complete",
     "text": "AI 작성 해설: 원문 A=[[1,2],[3,4]]에서 a=1,b=2,c=3,d=4이다. 강의 공식 det(A)=ad-bc에 대입하면 1×4-2×3=4-6=-2이다. 공식 정답표 1(가): -2와 일치한다. 음수라는 사실은 역행렬이 없다는 뜻이 아니다. 다음 소문항에서는 0이 아닌지를 조건으로 사용한다.",
     "references": [exam, notes, key], "verification": "verified",
     "note": "원래 정답을 바꾸지 않고 빠진 계산 과정만 추가했다. 정확한 유리수 연산으로 검산했다."},
    {"id": "s-ai-1b", "question_id": "q1b", "origin": "ai", "coverage": "complete",
     "text": "AI 작성 해설: det(A)=-2 != 0이므로 역행렬이 존재한다. 공식에 따라 A^(-1)=(-1/2)*[[4,-2],[-3,1]]=[[-2,1],[3/2,-1/2]]이다. 원문이 요구한 AA^(-1)의 네 성분은 차례로 -2+3=1, 1-1=0, -6+6=0, 3-2=1이므로 I이다. 추가 검산으로 A^(-1)A의 성분은 -2+3=1, -4+4=0, 3/2-3/2=0, 3-2=1이며 역시 I이다. 따라서 위 행렬이 원래 A의 역행렬이다. 공식 정답표에는 이 소문항의 풀이가 없어 전체 과정을 AI가 작성했다.",
     "references": [exam, notes], "verification": "verified",
     "note": "원문의 행렬과 요구 조건을 보존했다. 두 행렬곱을 정확한 유리수 연산으로 독립 검산했다."},
]
draft = {"schema_version": 1, "topics": topics,
    "exams": [{"id": "e-2025-a", "label": exam_lines[0], "source_id": exam["source_id"],
        "sitting_id": "sitting-2025-midterm", "variant": "A"}],
    "questions": questions, "solutions": solutions, "generated_questions": [],
    "limitations": ["합성 기출 한 회분만 사용했다. 과거 빈도는 미래 출제 확률이 아니다.",
        "주제별 중요도 1, 취약도 0.5와 학습 시간 25·35분은 계획용 추정이며 진단된 숙련도가 아니다."]}
(root / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
```

This example keeps generated items empty despite providing new **explanations**: explanations solve original questions and do not constitute new questions. The parent plus two leaves must count as two questions, not three. The synthetic answer key covers one answer only, so both leaves require AI reasoning. For complete official reasoning, omit the redundant AI record for that leaf; for genuinely partial official working, preserve it and author only the absent steps. Do not reuse this fixed solution for unrelated uploaded problems.
