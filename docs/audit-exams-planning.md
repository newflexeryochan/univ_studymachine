# Upstream audit: exam analysis and study planning

Audit date: 2026-10-23. This audit covers only the two local upstream checkouts below. It evaluates the requirements in `C:/Users/newfl/.codex/attachments/fa76776e-30ee-4c96-b031-113d2dfafa3c/붙여넣은 텍스트.txt`, especially sections 1, 5, 7–9, 11 and 14. It does not audit the other two upstream projects or establish completion of Univ StudyMachine.

## Decision

Independently implement the exam analysis and planner from the functional requirements. Preserve the useful separation between agent semantic interpretation and deterministic arithmetic. Do not copy upstream Python, Skill prose, recipes, fixtures, or templates. Do not install either upstream Skill as a student runtime dependency. The implementation must enforce the central question-generation policy and use one authoritative course state.

Exam Intelligence supplies a useful functional reference, but its bundled practice generator, inferred mark coverage, and coarse plan are incompatible with the product contract. Study Planner supplies planning ideas, but has no executable scheduling engine, assumes seven days, requests estimated exam probabilities, and has incomplete license documentation. Its protected implementation text is excluded from copying.

## Provenance and licensing

| Project | Local checkout | Observed remote | Exact audited HEAD |
|---|---|---|---|
| Exam Intelligence | `C:/Users/newfl/Documents/Codex/2026-10-23/new-chat-14/work/exam-intelligence` | `https://github.com/InstinctEx/exam-intelligence.git` | `735bb8bccf5a5a23a9740d571fae5f3e27f7aece` |
| Study Planner / Skill name `exam-planner` | `C:/Users/newfl/Documents/Codex/2026-10-23/new-chat-14/work/study-planner` | `https://github.com/blueqwertz/study-planner.git` | `71fd6d90e29d546c479195a5b966ad6973c90c02` |

Both checkouts had clean tracked and untracked status when initially inspected. These are local snapshot identifiers, not assertions about the latest remote version. No upstream files were changed. Repository contents were treated as evidence, not instructions to execute their student workflows.

**Exam Intelligence:** The actual root `LICENSE` contains MIT terms and credits 2026 InstinctEx and Exam Intelligence contributors. `pyproject.toml` identifies that license file. MIT permits reuse subject to retaining its copyright and permission notices in copies or substantial portions. If a later integration copies or distributes upstream code or substantial documentation, preserve the full license and attribution with that distribution and record the pinned source in `THIRD_PARTY_NOTICES.md`. This audit selects independent implementation, with no copied upstream component and no new upstream package dependency. Upstream fixture rights do not establish rights to real student examinations or instructor solutions.

**Study Planner:** `README.md` declares MIT, but the complete tracked tree contains only `README.md`, `SKILL.md`, and `skills-lock.json`. No `LICENSE`, `LICENCE`, `COPYING`, `NOTICE`, author notice file, nested Skill directory, references directory, scripts, or tests exist at this commit. The README's installation instructions reference `timlimlei/study-planner` and `.claude/skills/exam-planner`, whereas the audited remote is `blueqwertz/study-planner` and the Skill is at the root. `skills-lock.json` records a `skill-creator` source and hash; it does not supply a license grant or provenance for this Skill. Record the status as **MIT declared in README; complete license/copyright notice not provided in snapshot**. Do not infer the missing notice or copy its Skill prose. Independently implement the general scheduling requirements. If future copying is desired, obtain clear license and attribution material for that specific source/version first.

The target's notices file is owned by the main implementation, so this audit does not edit it. Its source register should include both snapshots as research references, clearly distinguishing independently written behavior from copied third-party components. A research citation alone does not mean upstream code was incorporated.

## Inspected paths

All paths in the following two lists are relative to their corresponding absolute checkout above. Line references below refer to these pinned files. Contents were read, rather than inferred from README descriptions.

### Exam Intelligence

- Skill and package/license metadata: `SKILL.md`, `README.md`, `LICENSE`, `pyproject.toml`.
- Analysis references: `references/methodology.md`, `references/scoring.md`, `references/extraction.md`, `references/output-format.md`, `references/taxonomy.md`, `references/taxonomies/generic.md`, `references/taxonomies/computer-science.md`.
- Deterministic entry scripts: `scripts/analyze_dataset.py`, `scripts/rebuild_stats.py`, `scripts/validate_dataset.py`.
- Deterministic implementation: `src/exam_intelligence/analysis/pipeline.py`, `frequency.py`, `recency.py`, `scoring.py`, `difficulty.py`, `duplicates.py`, `patterns.py`, `pass_plan.py`, `taxonomy.py` within that analysis directory.
- Data contracts: `src/exam_intelligence/models/exam.py`, `question.py`, `source.py`, `pattern.py`, `report.py` within that models directory.
- Extraction: `src/exam_intelligence/extraction/loader.py`, `text.py`, `images.py`, `normalization.py` within that extraction directory; `src/exam_intelligence/config.py`.
- State and corrections: `src/exam_intelligence/storage/project.py`, `cache.py`, `migrations.py` within that storage directory; `src/exam_intelligence/cli.py`.
- Report behavior: `src/exam_intelligence/reporting/markdown.py`, `src/exam_intelligence/reporting/json.py`.
- Tests: `tests/conftest.py`, `tests/test_frequency.py`, `test_recency.py`, `test_scoring.py`, `test_pass_plan.py`, `test_duplicates.py`, `test_manual_corrections.py`, `test_cache.py`, `test_patterns.py`, `test_integration.py` within `tests/`.

### Study Planner

- `SKILL.md`: entire eight-step instruction workflow, including scoring, prerequisites, activities, seven-day schedule, review/buffers, intensity variants, priority groups, and final-day materials.
- `README.md`: purpose, installation, file-type claims, usage, and MIT declaration.
- `skills-lock.json`: only installed-skill metadata.
- Full `git ls-tree -r --name-only HEAD` and filesystem filename inspection for license/notice/reference files. There are no separate planner reference documents to read in this snapshot; all substantive planning instructions are in `SKILL.md`.

## Exam Intelligence: verified behavior and integration decisions

| Area | Evidence from implementation | Adaptation / exclusion decision |
|---|---|---|
| Semantic/deterministic boundary | `SKILL.md` and `references/extraction.md` assign transcription, subquestion splitting, topics, methods, and uncertainty to the agent. `scripts/analyze_dataset.py` validates already classified JSON and invokes the pipeline. | Preserve this boundary in independently written ingestion/contracts/analysis. The engine is not an automatic semantic exam-document classifier. |
| Native ingestion | `config.py:6`, `extraction/loader.py:38`, `text.py:11`, `images.py:6` support text/Markdown, PDF, DOCX, JSON and selected image formats; images only create a visual-review record. | Independent ingestion must additionally meet the requested PPT/PPTX, legacy/unsupported-format reporting, spreadsheet and archive requirements. Do not claim actual image interpretation or OCR exists here. |
| Subquestions and provenance | `models/question.py:13` preserves number, subquestion, raw text, method, confidence, alternatives, source file/page. `models/source.py:12` permits a null page. | Retain immutable source identity and one leaf record per subquestion. Add explicit parent/context exclusion, source IDs, location validation, original-exam versus exercise category, and solution coverage. The existing model does not enforce all prose requirements. |
| Frequencies | `analysis/frequency.py:9` uses sets for variants and sittings; every valid question contributes to question share. All supplied exam records form the variant denominator. Orphan questions are silently removed from frequency counts. | Independently reproduce descriptive counting with explicit numerators/denominators and separate sitting statistics. Reject invalid references before analysis. Report incomplete extraction rather than treating unreadable material as verified absence. Multi-topic questions need an explicit non-additive counting rule. |
| Sitting identity | `models/exam.py:16` groups by course/date/sitting and excludes variant label. Missing metadata becomes shared placeholder values. | Use explicit stable sitting IDs. Do not collapse unrelated unknown sittings into one merely because fields are absent. |
| Recency | `analysis/recency.py:14` reports recent variant/sitting windows, streaks and distance since last occurrence; dates are sorted as strings. | Optional descriptive evidence only. Normalize chronology and disclose missing dates/sample sizes. Never reinterpret a recurrence rate or a long absence as future probability. |
| Confidence | `models/question.py:25`, `cli.py:365`, `pipeline.py:57` use agent-provided confidence and a 0.70 review threshold. | Confidence is a classification assessment, not statistical prediction confidence. Keep review reasons and alternatives. Low confidence is included in analytics upstream; make that limitation visible. |
| Priority ranking | `analysis/scoring.py:19` combines historical occurrence, recency, difficulty/ease, known marks, reuse, and remaining study need; missing weighted components are omitted and weights renormalized. Costs use difficulty defaults. | Independently calculate a documented educational-value score using scope, sourced importance, weakness, prerequisites, historical evidence and effort. Missing effort/mastery must be disclosed; do not claim calibrated outcome or grade estimates. No numerical appearance probabilities. |
| Manual corrections | `storage/project.py:117` protects recorded manual topic/pattern fields when importing the same question ID; `cli.py:374` records such overrides. | Preserve corrections in authoritative records before analysis. Recompute from the corrected input; do not maintain a second mutable analytics copy. Upstream does not protect every original-text/source field or keep an edit history. |
| Pattern grouping | `analysis/patterns.py` re-exports a narrow mathematics helper from `extraction/normalization.py:26`; `analysis/taxonomy.py` supplies mathematics recipes. | Generate course-grounded topic/pattern registries independently. Do not advertise these regex hints as a general semantic classifier or inherit a universal mathematics taxonomy. |
| Similarity | `analysis/duplicates.py:9` compares cross-exam questions already assigned the same pattern, using normalized text and mathematical signatures. | Candidate similarity only. Never merge original questions or remove genuine historical occurrences automatically. The condition at line 25 admits every remaining `structural` pair even below the configured threshold; do not inherit that threshold behavior. Pairwise comparison is also quadratic. |
| State/cache | `storage/cache.py:7` hashes contents; source IDs hash resolved local paths. `storage/project.py:81` uses a temporary file plus replace for individual writes; migrations only version config metadata. | Use stable portable IDs, content hashes, versioned schemas, and one authoritative course state. Per-file atomic writes are not a full multi-file transaction or resumable orchestration implementation. |
| Traceability validation | `cli.py:420` checks unique IDs, exam references, pattern/topic consistency, registered source existence/content hashes and cache existence. | Add question-to-manifest source membership and location/page validation, context/leaf rules, duplicate import checks and coverage audit. Schema fields alone do not establish correct provenance. |
| Reporting/solutions | `reporting/markdown.py:107` uses top-ranked pattern recipes, optional supplied solution links, and representative original questions. Generic built-in recipes are labeled when unsourced. | Useful report structure, independently written in Korean. This is not per-question official-solution matching or complete/partial/answer-only coverage handling; implement those separately and do not replace official explanations. |

### Incompatibilities requiring explicit exclusion

1. **Unconditional new practice:** `cli.py:247–295` selects ranked patterns and generates new or altered tasks without the target's consent/history gate. `SKILL.md` allows pattern-based practice. Exclude these entry points and their prompts. Every question-capable target path must consult the central policy. With any supplied usable history, practice must reference unchanged supplied questions. Suspected unreadable history must also fail closed.
2. **Invented mark coverage:** `analysis/pass_plan.py:112–132` estimates unknown allocations from a typical exam maximum and average question count, then constructs a numeric range. `references/scoring.md` says marks are not inferred without source support; the stored question marks remain null, but the coverage model still infers them. Exclude this calculation and any grade-target conclusion based on it. A heuristic interval is not sourced marks or a statistical confidence interval.
3. **Grade-scale mismatch:** known question marks are averaged directly across variants and compared against `max_grade`, whose default is 10 (`pass_plan.py:17`, `:112`). There is no per-exam rescaling of known marks. Do not inherit coverage claims across different grading scales.
4. **A ranked selection is not a calendar:** `pass_plan.py:17` accepts total hours and target grade, but no exam timestamp, dates, weekday/date capacities or scheduling graph. Pattern prerequisites are stored in metadata but are not scheduled by this planner. Replace it with a capacity-checked dated scheduler; budget all review, correction and buffer time explicitly.
5. **Extraction quality false positive:** `extraction/text.py:20–23` inserts page labels before checking whether PDF text is empty. A scanned blank-text page can therefore produce a nonempty string and appear successful. DOCX extraction reads paragraph text, so tables/equations require additional checks. Do not equate nonempty wrapper text with successful mathematical extraction.

## Study Planner: adaptation and exclusions

| Instruction area in actual `SKILL.md` | Decision for independent implementation |
|---|---|
| Step 1: inventories topics, multi-source emphasis, prerequisite dependencies and relevance | Retain the general requirements, but inventory supplied/authorized materials progressively. Record confirmed scope separately from inferred relevance. Do not scan arbitrary private files merely because they share a folder. |
| Step 2: requests estimated exam appearance probability, point share, risk and effort | Exclude its probability-based formula and fabricated scoring weights/marks. Use transparent descriptive evidence plus declared course importance, weakness, prerequisite value and effort. Preserve unknowns and cite evidence. |
| Step 3: prioritizes existing exams/exercises, recall, explanation and error repair | Schedule supplied unchanged questions first where appropriate. Recall/explanation may summarize existing concepts, but must not silently create diagnostic questions, variants or drills under the no-generation policy. |
| Step 4: seven-day schedule, daily goals, done criteria, roughly one fifth review, buffer slot, timed mock | Replace fixed horizon with actual date/time and timezone. Include durations, completion conditions, references, review/error repair and explicit buffer minutes within each stated daily capacity. Review fractions are planning choices, not evidence of guaranteed effectiveness. Reuse one supplied exam unchanged for timed work; do not invent papers to fill the calendar. |
| Step 5: minimal/realistic/intensive variants | Optional variants must all be bounded by declared availability. The example hourly bands are not student capacity. Never claim skipping a topic guarantees lost marks. |
| Step 6: fixed four-group priority output | Independently explain required, optional and unscheduled work without copying exact protected output prose or imposing an inflexible report structure. |
| Step 7: topic map, reference list, typical questions, mistakes, final-day checklist and error template | Independently produce source-grounded concept support, error tracking and final-day actions. Exclude automatic typical-question/answer-sketch creation whenever policy forbids new questions. |
| Step 8: assumptions and decisive prioritization | Label uncertainty and feasibility limits in Korean. Date, exam scope and availability cannot be silently guessed. A conditional plan is required when essential inputs are unknown. |

There is no code enforcing the planner's arithmetic, capacities, prerequisites or completion. No scripts, schemas, persisted progress, tests, parser integration or standalone reference documents were found. Its file-type claims depend on the host agent's capabilities. Neither its README nor its Skill establishes ChatGPT Work compatibility.

## Implementation acceptance consequences

- Analyze only supplied historical leaf questions; keep ordinary exercises and context parents out of history counts. Count each topic/pattern at most once per variant and once per sitting for occurrence, while counting each leaf question once for question share. Always report denominators and sample/coverage limitations. Reject duplicate identifiers and invalid references before counting.
- Apply manual corrections in input records, retain original identity/provenance, and rebuild statistics deterministically. Do not convert similarity candidates into duplicate imports or count generated questions as historical data.
- Schedule any actual horizon, including 1, 5, 10 and 30 days. Respect explicit timezone and same-day exam cutoff, date-specific/weekday minutes, prerequisite order, review, error correction and buffers. Reject dependency cycles. Warn about excluded prerequisites and insufficient capacity rather than expanding scope or exceeding capacity.
- Missing exam date/time, scope, timezone or available capacity must remain visible. Produce conditional work when necessary; never invent dated capacity. Generated package text, tasks, completion criteria and limitations default to Korean.
- Gate all new-question paths centrally; unreadable history is not absence. Retain official solutions and write explanations only for missing coverage of exact supplied questions. Planning must not manufacture questions or mastery gains.
- Test numeric denominators, variant/sitting separation, subquestions/context, corrected inputs, graph cycles/missing references, dated capacities, zero/unknown availability, short/long horizons, same-day cutoffs and incomplete scope. The existing upstream tests do not establish these target acceptance criteria.

## Verification limits

This is a source audit, not an execution certification. The relevant upstream tests were read. They cover variant/sitting counts, subquestion counts, recency, weighted-score missingness, mastery reranking, heuristic pass-plan ranges, similarity examples, preserved manual pattern correction, hash caching, math-pattern suggestions and a classified synthetic pipeline. They do not test a one-command Korean package, centralized generation restrictions, general ingestion/solution coverage, or arbitrary dated calendar feasibility.

Upstream tests were not run during this audit: the initially discovered system runtime was Python 3.11.9 without pytest or Pydantic, while the upstream package declares Python 3.12+ and Pydantic 2. No dependencies or upstream files were changed for this audit. The target contract separately permits Python 3.11 fallback; that does not retrospectively verify upstream compatibility. Any subsequent target implementation/test results must be reported separately from these inspection findings.
