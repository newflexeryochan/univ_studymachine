# Univ StudyMachine

Univ StudyMachine is one Agent Skill for turning supplied university course materials into a Korean exam preparation package. Students upload their materials, make one request, and answer one batch of at most eight missing-information questions. The hosting agent executes the remaining workflow, including the semantic authoring step.

The canonical entry point is [SKILL.md](SKILL.md), named `univ-studymachine`. [docs/CONTRACT.md](docs/CONTRACT.md) defines the shared contract. This documentation describes that interface; it does not certify native skill installation, arbitrary-course educational correctness, or ChatGPT Work execution. Work runtime support remains unverified. Local CLI tests, when reported separately, must not be described as native skill or Work tests.

## Responsibility boundary

Python performs extraction where supported, policy checks, schema validation, historical counting, scheduling, persistence, and rendering. **The hosting agent reads and interprets the sources and writes a detailed cited semantic draft.** There is no general-purpose semantic solver hidden in the CLI, no external AI service, and no fixture-backed substitute for solving uploaded questions. Running only `prepare` and `answer` cannot produce a substantive finished package.

The package requires no separately installed Study Skills, Pass All Exams, Exam Intelligence, or Exam Planner skills. Consult the repository's upstream audit and notice documents for provenance; conceptual influence does not imply copied code or installed upstream packages.

## Developer installation

Use Python 3.12+ where available; the declared fallback is Python 3.11. From the repository root, create an isolated environment and install the selected extras. These are developer setup instructions, not student tasks.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[documents,dev]"
```

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[documents,dev]'
```

The core dependency is `jsonschema`. The `documents` extra supplies `pypdf`, `python-docx`, `python-pptx`, and `openpyxl`; `dev` supplies testing, linting, and build tools. Installing an extractor does not supply OCR, visual understanding, a PDF renderer, or a mathematical solver. If the host cannot install dependencies, report the missing package and use a supported source format rather than claiming a successful conversion.

For a Codex-local installation candidate, place a copy of the **complete skill directory**, with its root `SKILL.md`, references, scripts, and package metadata, under the host's configured skills directory, conventionally `$CODEX_HOME/skills/univ-studymachine` or `~/.codex/skills/univ-studymachine`. Use a fresh destination and preserve an existing installation. Do not copy `.git`, `.venv`, caches, or private state. Install Python dependencies in the actual execution environment. A Python package installation alone does not register an Agent Skill, and copying a directory is not evidence that native discovery/loading worked. Verify discovery and a real run in the intended host before advertising installation success.

For ChatGPT Work, use only an installation/import mechanism actually exposed by that environment. No verified Work installer or cross-runtime filesystem bridge is documented. A local Windows path or local Python environment is not automatically accessible there. See [compatibility](docs/COMPATIBILITY.md).

## Student entry point

After the host has loaded the skill, a student can attach course materials and write:

> $univ-studymachine 이 자료들로 시험 대비해 줘.

The agent inventories/extracts without opening intake, reads preliminary content, records actual visual/manual reviews, and merges known exam information before asking only what is missing. The student's one reply is sufficient for normal initial production. No terminal, JSON, subskill selection, or export command is required. See [the Korean student guide](docs/STUDENT_GUIDE.ko.md).

## Agent/developer CLI

Run the adapters from the repository root using the environment's Python. `JSON` arguments below denote UTF-8 JSON files; the host writes those files. `DIR` is the single private course root, outside every Git checkout; `FILE...` are authorized local uploads. These interface names do not remove the host's semantic responsibilities.

```text
python scripts/study.py prepare --state DIR --profile JSON --materials FILE... [--categories JSON] --defer-intake
python scripts/study.py review --state DIR --reviews JSON
python scripts/study.py intake --state DIR --profile JSON
python scripts/study.py answer --state DIR --answers JSON
python scripts/study.py finish --state DIR --draft JSON [--start-date ISO]
python scripts/study.py resume --state DIR
python scripts/study.py record --state DIR --question ID --correct yes/no --note TEXT
python scripts/study.py correct --state DIR --corrections JSON
python scripts/study.py replan --state DIR --profile JSON --start-date ISO
```

1. Put immediately known values in the initial profile. `prepare --defer-intake` persists stage `inventoried` and emits extracted inventory without an intake batch.
2. Inspect sections and raw visuals. `review` imports a list of actual readings/manual category corrections. `intake --profile` merges reliably extracted facts and emits the single batch of remaining questions. Unknown values remain null. The non-deferred `prepare` shortcut opens intake immediately and is suitable only when source facts/categories have already been reliably inspected.
3. After the one reply, `answer` records normalized answers. The agent writes the substantive draft described in [semantic authoring](references/semantic-authoring.md). Additional actual visual reading may be imported through `review` at `awaiting_semantics`, without another student question.
4. `finish` validates that draft and builds the applicable study artifacts. Inspect the files, limitations, policy, QA, and manifest before presenting them as ready.
5. `resume` returns saved context. `record` stores an actual result and rebuilds outputs. `correct` preserves supported question-field corrections. `replan` updates permitted profile fields and rebuilds the remaining calendar from an explicit start. Neither question correction nor replanning performs arbitrary semantic edits.

See [the complete workflow and synthetic source walkthrough](references/workflow.md) for concrete JSON and agent actions, and [tutoring](references/tutoring.md) for later sessions.

## Output and privacy

Markdown is canonical. The applicable package includes the numbered Korean guide, source inventory, concept guide, historical analysis when supported, supplied-question explanations/index, study plan, review checklist, execution guide, `manifest.json`, and `package.zip`. Generated-question file `09_AI생성_연습문제_및_해설.md` exists only with affirmative consent, no historical material or suspicion, and actual generated items. Do not create empty conditional artifacts. PDF export is optional and requires an available renderer plus visual verification; it is not a default CLI promise.

Choose one private state root per course, outside the implementation checkout and all other Git checkouts. Keep source copies, profile, answer files, semantic drafts, state, and study exports there. Local state persists until deliberately removed; there is no documented automatic expiry, account-wide backup, encryption layer, or automatic local-to-Work migration. Do not commit or upload private study data. Default operation introduces no telemetry or third-party document-upload service. The hosting product's own data handling still applies.

## Limits and validation

- Image/scanned mathematics requires raw visual inspection by a capable host. Extracted text alone may lose symbols, tables, and diagrams. Unreadable historical material blocks new-question generation even after consent.
- Complete official explanations take priority. Partial solutions and answer keys are retained, with AI-authored missing reasoning clearly separated. The host must flag unresolved or conflicting solutions honestly.
- Planning uses the supplied date, timezone, scope, and availability. Missing capacity produces a conditional plan. Historical occurrence is not a predicted exam probability, and no schedule guarantees a grade.
- `replan` supports permitted profile/date/capacity updates and refreshes outputs; consent revocation removes generated items and artifact 09 after successful refresh. `record` also rebuilds outputs using observed weakness. `resume` only reads state. The planner does not track completed study-block minutes, automatically monitor missed days, or semantically remap topics when scope text changes; inspect rebuilt work and avoid claiming exact progress-aware calendar repair.
- Preferred-language output is authored by the host: translate intake, render the applicable base files, then provide complete `localized_documents` and finish again automatically. Missing translations leave the base package partial; validation protects applicable filenames, original question/solution statements, and links. Korean filenames stay stable. Translation quality still requires host review. Unsupported formats and missing dependencies require explicit limitations.

Developers can run the repository's checks in their environment:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check scripts tests
```

Passing deterministic tests cannot establish semantic correctness on arbitrary courses or native host compatibility. See [the validation report](docs/TEST_REPORT.md) for executed tests and a separate actual Codex agent-authored source-to-package exercise. Native installation/discovery and ChatGPT Work remain unverified and are separate from that local exercise.
