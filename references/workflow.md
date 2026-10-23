# Agent workflow

Read [../docs/CONTRACT.md](../docs/CONTRACT.md) first. It is the semantic/data authority; the additional deferred-intake, review, replan, and localization adapters below describe the current host workflow. All commands and JSON authoring are the **agent's** work. Student interaction is one request, at most one intake message with no more than eight questions, one reply, then automatic production.

## Primary sequence

1. Choose one private root outside every Git checkout, including the skill installation. Keep uploaded originals intact. Check Python, core dependencies, applicable extractors, file-writing/export support, and actual visual tools. Install missing declared dependencies through the host's authorized mechanism or report the unsupported format. Do not request student terminal work.
2. Read the initial request and any immediately available exam facts. Write `profile.json` with `schema_version: 1`, a stable course ID, known facts and evidence, explicit IANA timezone when known, `language: "ko"` by default, and `generation_consent: null` unless explicitly answered. Unknowns remain null. Do not infer student availability from class hours or a syllabus date from an unrelated historical exam.
3. Run `prepare --state DIR --profile profile.json --materials FILE... --defer-intake`, optionally with `--categories categories.json`. Categories map authorized paths or filenames to contract category strings. The result is stage `inventoried`, an extracted `source_manifest`, and **no emitted intake**. Repeating `prepare` on existing state resumes it; it does not import more sources or reset intake.
4. Read all preliminary sections relevant to exam instructions, scope, and course identity. Inspect raw uploaded mathematical pages/images where available, especially signs, exponents, subscripts, diagrams, tables, and choices. Resolve categories from actual content. Never treat an unreadable suspected historical file as evidence of no history.
5. When actual reading/manual classification needs to enter the inventory, author a review list and run `review --state DIR --reviews reviews.json`. This is permitted at `inventoried` and later at `awaiting_semantics`. A review records actual method `native_manual` or `multimodal`, a nonempty inspection note, source ID, sections, and optional category/status/limitations. Never claim a visual inspection you did not perform.
6. Write `facts.json` with only reliably extracted profile facts and evidence. Run `intake --state DIR --profile facts.json`. It merges those facts and emits only remaining questions, once. Present those questions in one message, translating the Korean intake text into an explicitly requested language. Do not add extra questions outside the batch. If no questions remain, omit the student-facing intake and consume an empty answer internally if needed.
7. Normalize the student's one reply into `answers.json`, run `answer`, and continue immediately. Consent requires explicit yes/no; omitted means null. Use integer minutes for capacity, ISO dates/datetimes, explicit timezone, and `monday` through `sunday` or date keys. Answer only emitted fields; language/timezone are also accepted. Unknown nonessential answers require conservative disclosed assumptions, not another routine question.
8. Read [semantic-authoring.md](semantic-authoring.md). Author a complete substantive draft from the actual sources. Use `review` again at `awaiting_semantics` for real late visual reading without another student message. Use preserved source IDs and locations. Read the policy before any potential new question; solve existing questions without seeking generation consent.
9. Run `finish --state DIR --draft draft.json`, preferably with an explicit aware `--start-date ISO` for a reproducible calendar. Inspect the package, policy, solution coverage, QA, unscheduled work, and manifest. Repair content or source-reference errors automatically and retry the supported operation. Do not turn unsupported semantics into fabricated solutions.
10. For non-Korean language, complete the localization pass below automatically. Return only verified output links, a starting action, and concrete limitations. A partial package remains partial even if some files are useful. Do not stop at the plan when the remaining work can be performed.

The non-deferred `prepare` shortcut opens intake immediately. Use it only if the agent has already reliably inspected all relevant facts/categories. The deferred path is the default because extraction may reveal facts that should not be asked again.

## Review records and integrity

`reviews.json` is a JSON **list**, not an object wrapper. Each item has this shape:

```text
{source_id, method, note, sections:[{location,text}], category?, status?, limitations?}
```

Use the registered source ID returned by ingestion. Copy actual readings; use stable locations such as `page:2` or `slide:4`. `sections` replaces the entire section list for that source, so preserve all existing still-valid sections and location labels that a draft cites. A category-only review can retain the existing sections. `limitations` also replaces that list when supplied: retain unresolved pages, symbols, and coverage warnings. Mark `processed` only when all relevant content was actually inspected/read; an empty non-container file cannot be processed. Use `partial` for incomplete coverage or `failed` for unusable content. Do not remove history flags merely to unlock generation.

If an unresolved historical source remains, keep it historical/suspected, disclose the limitation, and leave generated items empty regardless of consent. Actual visual review can repair readable pages; consent cannot repair unreadable pages. Source review is a recorded host action, not a bundled OCR engine.

Changing category alone never clears `suspected_history` or `unreadable_history`. If actual complete inspection proves a falsely suspected source is nonhistorical, a review may include a nonempty `history_resolution` explanation along with processed status, actual sections and the corrected category. Unreadable/partial/empty sources cannot resolve suspicion, and already confirmed historical questions cannot be reclassified to unlock generation. The original suspicion and review remain auditable.

## Localization without another student turn

Korean defaults are `ko`, `ko-KR`, and `한국어`. For another language:

1. Translate intake before presenting it; preserve fields, choices, and the eight-question ceiling.
2. Author semantic explanations in the requested language where practical. Call `finish` once without `localized_documents` to obtain the full applicable base Markdown set. Its base Korean output is intentionally **partial** until localization is ready; do not present it as the final requested-language package.
3. Read every applicable top-level numbered Markdown document in `output/`. Write `draft.localized_documents` as a JSON object whose keys are **exactly those top-level Markdown filenames** and whose values are the complete translated contents. Evidence copies under `sources/` stay in their original language. Translate headings, fixed labels, explanations, warnings, plans, and navigation labels. Retain filenames in Korean.
4. Preserve every original supplied question and non-AI solution text verbatim wherever it appears. Add translated explanations alongside originals as useful. Keep every Markdown link target byte-for-byte; do not rewrite citation/navigation destinations. Keep every AI-created item visibly attributed to AI. The generated-item machine label remains `AI 생성 연습문제`; translate its displayed label without losing authorship.
5. Run `finish` again automatically with the enriched draft and the same start timestamp. The validator rejects an incomplete applicable-file set, missing links or navigation anchor IDs, empty translations, and changed supplied statements. Review language quality and semantic fidelity yourself; structural checks do not establish a good translation.

Refresh translations after replanning, corrections, observations, consent changes, or any changed artifact set/content. A saved mapping can become stale even if filenames and links still validate. When necessary, build a new base pass with the mapping omitted, translate that base, and finish again. Do not hide a consent-revocation update behind an outdated mapping containing artifact 09.

## Checkpoints, errors, and delivery

`resume --state DIR` returns `stage`, `intake`, `profile`, `source_manifest`, `generation_policy`, `mastery_state`, `error_log`, `draft`, `run_manifest`, and `output_dir`. Use it after interruption. Resume semantic work from `awaiting_semantics` rather than issuing a second intake. Do not run a second `answer`; it is consumed once. An error result is not successful completion.

The private root contains authoritative `state.json`, preserved source copies under `materials/`, and final exports under `output/`. Agent-created profile/facts/answer/review/draft JSON belongs in this same private root. Treat exports as snapshots. Do not delete unrelated files or scan unrelated personal directories. Unsupported state versions need explicit migration preserving the original.

Check actual numbered Markdown, `manifest.json`, and `package.zip`; conditional documents must match applicability. Verify the ZIP opens, excludes private intermediates and repository contents, and contains the expected export files. Confirm source navigation works in the host's supported context; local absolute paths are not portable cloud download links. PDF requires an available renderer and successful visual inspection. If files/export are unavailable, provide complete accessible content and disclose the missing mechanics without inventing file links or durable state.

If the CLI says `complete` but the host finds missing teaching, uncertain math, or a mistranslation, repair it or report partial completion. A structural QA pass is not a semantic correctness certificate. Consult [tutoring.md](tutoring.md) for later observations, corrections, and replanning.

## Concrete synthetic source walkthrough

This is a transparent developer/agent exercise using real text files. It is not an automated solver, a backend fixture lookup, a native skill installation test, or evidence of Work compatibility. All source text below is synthetic. A new course requires fresh agent interpretation and solutions. Use a fresh private directory; do not overwrite existing student state.

From a PowerShell session at the skill root, set a task-specific private location:

```powershell
$env:STUDYMACHINE_STATE = Join-Path $env:LOCALAPPDATA 'UnivStudyMachine\synthetic-linear-algebra-20261023'
```

On a POSIX host, the analogous setting is `export STUDYMACHINE_STATE=/tmp/univ-studymachine-synthetic-linear-algebra-20261023`. Execute the following Python block with the installed environment. It refuses an existing root and creates actual source texts, not fabricated extraction records:

```python
import json
import os
from pathlib import Path

root = Path(os.environ["STUDYMACHINE_STATE"]).resolve()
assert not any((p / ".git").exists() for p in (root, *root.parents))
root.mkdir(parents=True, exist_ok=False)
inputs = root / "inputs"
inputs.mkdir()
texts = {
    "syllabus.txt": "선형대수학 시험 안내\n시험: 2026-10-30 14:00 Asia/Seoul.\n범위: 2×2 행렬의 행렬식과 역행렬.\n형식: 계산형이며 풀이 과정을 제출한다.\n",
    "lecture_notes.txt": "2×2 행렬 A=[[a,b],[c,d]]의 행렬식은 det(A)=ad-bc이다.\ndet(A) != 0일 때 역행렬은 A^(-1)=(1/det(A))*[[d,-b],[-c,a]]이다.\n행렬식이 0이면 역행렬이 없다.\n역행렬의 검산은 A*A^(-1)=I와 A^(-1)*A=I를 모두 확인한다.\n계산 시 비대각 성분의 부호와 전체 분모를 확인한다.\n",
    "historical_exam.txt": "2025년 선형대수학 중간고사 A형 (합성 검증 자료)\n1. A=[[1,2],[3,4]]에 대하여 다음을 구하시오.\n(가) det(A)를 구하시오.\n(나) A의 역행렬을 구하고 A*A^(-1)=I인지 확인하시오.\n",
    "official_key.txt": "공식 정답표 (합성 검증 자료)\n1(가): -2\n",
}
for name, text in texts.items():
    (inputs / name).write_text(text, encoding="utf-8")
def save(name, data):
    (root / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
save("profile.json", {"schema_version": 1, "course_id": "synthetic-linear-algebra",
    "timezone": "Asia/Seoul", "language": "ko", "generation_consent": None})
save("categories.json", {"syllabus.txt": "syllabus", "lecture_notes.txt": "lecture_notes",
    "historical_exam.txt": "historical_exam", "official_key.txt": "answer_key"})
```

Use the actual environment's Python for every adapter; on Windows the installed example is:

```powershell
.\.venv\Scripts\python.exe scripts/study.py prepare --state "$env:STUDYMACHINE_STATE" --profile "$env:STUDYMACHINE_STATE/profile.json" --materials "$env:STUDYMACHINE_STATE/inputs/syllabus.txt" "$env:STUDYMACHINE_STATE/inputs/lecture_notes.txt" "$env:STUDYMACHINE_STATE/inputs/historical_exam.txt" "$env:STUDYMACHINE_STATE/inputs/official_key.txt" --categories "$env:STUDYMACHINE_STATE/categories.json" --defer-intake
```

Read the returned actual sections. They establish the subject, exam timestamp, scope, and format before the student sees questions. After personally reading them, run this Python block to record an actual native/manual review and source-backed facts:

```python
import json
import os
from pathlib import Path
root = Path(os.environ["STUDYMACHINE_STATE"])
state = json.loads((root / "state.json").read_text(encoding="utf-8"))
sources = {s["filename"]: s for s in state["source_manifest"]["sources"]}
reviews = [{"source_id": s["id"], "method": "native_manual",
    "note": "합성 원본 텍스트와 추출된 각 줄을 직접 대조했습니다.",
    "sections": s["sections"], "category": s["category"], "status": "processed",
    "limitations": []} for s in sources.values()]
evidence = {"source_id": sources["syllabus.txt"]["id"],
    "location": sources["syllabus.txt"]["sections"][0]["location"]}
facts = {"subject": "선형대수학", "exam_at": "2026-10-30T14:00:00+09:00",
    "scope": "2×2 행렬의 행렬식과 역행렬", "format": "계산형, 풀이 과정 제출",
    "instructor_guidance": "풀이 과정을 제출한다.",
    "evidence": {k: [evidence] for k in ("subject", "exam_at", "scope", "format", "instructor_guidance")}}
for name, data in (("reviews.json", reviews), ("facts.json", facts)):
    (root / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

```powershell
.\.venv\Scripts\python.exe scripts/study.py review --state "$env:STUDYMACHINE_STATE" --reviews "$env:STUDYMACHINE_STATE/reviews.json"
.\.venv\Scripts\python.exe scripts/study.py intake --state "$env:STUDYMACHINE_STATE" --profile "$env:STUDYMACHINE_STATE/facts.json"
```

Expected intake fields are `availability`, `preparation`, and `target`; confirmed exam facts should not be requested again. Historical material means no generation-consent question. In an actual student run wait for the one reply. For this synthetic exercise the reply is: `평일 60분, 주말 120분 가능해요. 개념을 한 번 봤지만 역행렬 계산이 약해요. 목표는 B+예요.` Normalize that stated reply:

```python
import json
import os
from pathlib import Path
root = Path(os.environ["STUDYMACHINE_STATE"])
answers = {"availability": {"monday": 60, "tuesday": 60, "wednesday": 60,
    "thursday": 60, "friday": 60, "saturday": 120, "sunday": 120},
    "preparation": "개념을 한 번 봤고 역행렬 계산이 약함", "target": "B+"}
(root / "answers.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
```

```powershell
.\.venv\Scripts\python.exe scripts/study.py answer --state "$env:STUDYMACHINE_STATE" --answers "$env:STUDYMACHINE_STATE/answers.json"
```

Now author `draft.json` using the complete worked construction in [semantic-authoring.md](semantic-authoring.md). It binds citations to the actual ingested source IDs, retains the answer key, supplies missing reasoning, and verifies the inverse. Then:

```powershell
.\.venv\Scripts\python.exe scripts/study.py finish --state "$env:STUDYMACHINE_STATE" --draft "$env:STUDYMACHINE_STATE/draft.json" --start-date "2026-10-23T09:00:00+09:00"
.\.venv\Scripts\python.exe scripts/study.py resume --state "$env:STUDYMACHINE_STATE"
```

Inspect the actual exported concept guide and solution guide: there should be one exam variant, one sitting, two historical leaf questions, retained context, a preserved answer-key entry, two AI explanations for missing reasoning, and zero generated questions/artifact 09. Verify the determinant is −2, both inverse products are the identity, source links target real sections, all dated work fits capacity including buffers, and the ZIP/manifest agree. Do not report this expected outcome as tested until it has actually been executed and inspected.
