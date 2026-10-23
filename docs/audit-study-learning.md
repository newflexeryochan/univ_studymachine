# Study and learning upstream audit

Audit date: 2026-10-23 (Asia/Seoul). Status: completed static source inspection of the two requested local checkouts. This document records findings and integration decisions; it does not establish implementation or runtime acceptance.

## Scope and provenance

The requirements source is `C:/Users/newfl/.codex/attachments/fa76776e-30ee-4c96-b031-113d2dfafa3c/붙여넣은 텍스트.txt`, read in full, including the shared contracts, learning engine, policy, student artifacts, and acceptance scenarios. The direct instruction to audit only controlled the initial work despite the attachment's broader implementation mandate. A later direct instruction separately authorized only the artifact renderer, its tests, and third-party notices after this audit.

| Source | Exact inspected checkout | Git remote recorded locally | Exact HEAD | Declared release |
| --- | --- | --- | --- | --- |
| Study Skills | `C:/Users/newfl/Documents/Codex/2026-10-23/new-chat-14/work/study-skills` | `https://github.com/jacquardlabs/study-skills.git` | `a576399e21e64651a4e7b0bffa5998d26f10301b` | 2.0.0; commit timestamp 2026-10-12T16:36:06Z |
| Pass All Exams | `C:/Users/newfl/Documents/Codex/2026-10-23/new-chat-14/work/pass_all_exams` | `https://github.com/SolarAscent/pass_all_exams.git` | `2f4772259047672c834f6c7f2f23401efb782113` | 3.0.0; commit timestamp 2026-08-14T14:09:47+08:00 |

Both upstream worktrees were clean (`git status --porcelain=v1` empty; tracked differences against HEAD absent). The SHAs identify these local snapshots; no fetch or assertion about the latest remote revision was made. Git inventories included hidden tracked files. No upstream installer, ingestion program, study session, release workflow, or packaging program was executed. No upstream files were changed. No chats were messaged.

The target checkout was initially an unborn repository with no tracked implementation. Other work subsequently appeared there; this audit does not claim authorship or validation of that work. Exam Intelligence and Exam Planner are outside this audit's two-source scope. Their functionality and licensing are not inferred from these repositories.

## Decision vocabulary and reuse boundary

- **Reused** means retaining a general functional principle without changing its purpose. It does not mean copying implementation or expressive text.
- **Adapted** means independently implementing a related behavior with the target's intake, evidence, Korean language, and question restrictions.
- **Replaced** means the upstream mechanism cannot satisfy the target and needs a new implementation.
- **Excluded** means the upstream behavior, asset, platform assumption, or integration is outside the target workflow.

No upstream code, prompts, templates, examples, tests, illustrations, or substantial prose are planned for copying or vendoring. All future implementation is independent. Path names, field names, factual descriptions, and license facts below identify inspected evidence rather than republish upstream content.

## Inspected file ledger

Paths in each list are exact repository-relative paths under the absolute checkout named above. All listed files were read, rather than inferred from a README. Line references elsewhere are one-based at the recorded SHA.

### Study Skills

- `LICENSE`
- `README.md`
- `CHANGELOG.md`
- `pyproject.toml`
- `.gitignore`
- `.claude-plugin/plugin.json`
- `.github/workflows/release.yml`
- `skills/topic-map/SKILL.md`
- `skills/understanding-check/SKILL.md`
- `skills/paper-reader/SKILL.md`
- `skills/paper-critique/SKILL.md`
- `skills/literature-map/SKILL.md`
- `evals/topic-map-new-field/prompt.md`
- `evals/topic-map-new-field/graders/skill-fired.md`
- `evals/understanding-check-quiz/prompt.md`
- `evals/understanding-check-quiz/graders/skill-fired.md`
- `evals/understanding-check-procedural/prompt.md`
- `evals/understanding-check-procedural/graders/skill-fired.md`
- `evals/paper-reader-help-read/prompt.md`
- `evals/paper-reader-help-read/graders/skill-fired.md`
- `evals/paper-reader-help-read/graders/not-paper-critique.md`
- `evals/paper-critique-trust/prompt.md`
- `evals/paper-critique-trust/graders/skill-fired.md`
- `evals/paper-critique-trust/graders/not-paper-reader.md`
- `evals/literature-map-compare/prompt.md`
- `evals/literature-map-compare/graders/skill-fired.md`
- `evals/literature-map-compare/graders/not-paper-reader.md`
- `evals/no-skill-trivia/prompt.md`
- `evals/no-skill-trivia/graders/no-skill.md`

There is no application ingestion script, persistent student state implementation, shared data schema, or separate learning reference directory in this tracked tree. `pyproject.toml` configures semantic release, not a study-processing Python package. The workflow is release automation, not a learning-content validation pipeline. The changelog records consolidation into five current skills; removed earlier skills must not be assumed available.

### Pass All Exams

- `LICENSE`
- `SKILL.md`
- `README.md`
- `CHANGELOG.md`
- `PROJECT_CHECK.md`
- `.gitignore`
- `requirements-markitdown.txt`
- `agents/openai.yaml`
- `configs/example.yaml`
- `references/pipeline.md`
- `references/prompt-patterns.md`
- `references/platforms.md`
- `references/comparison.md`
- `scripts/ingest_materials.py`
- `scripts/examctl.py`
- `scripts/validate_skill.py`
- `scripts/package_skill.py`
- `scripts/install.sh`
- `scripts/quick-install.sh`

`README.zh-CN.md` and `docs/hero.svg` were inventoried but not read as evidence for functional decisions; translated marketing and visual assets are excluded. No actual private course state files were read. The runtime contracts below were reconstructed from the scripts and reference documents.

## Study Skills: findings and decisions

| Capability and exact evidence | Finding | Decision for Univ StudyMachine |
| --- | --- | --- |
| Topic boundaries and prerequisites: `skills/topic-map/SKILL.md:41-87,115-128` | Starts from the learner's goal/background, prefers supplied materials, arranges concepts by dependency, groups concepts into milestones, and describes observable capabilities and rough effort. The 5–15 concepts and 3–6 milestones are prompt guidance, not a validated graph algorithm. | **Reused**: dependency order, explicit scope, evidence-first reading, observable completion criteria. **Adapted**: distinguish major/minor topics using confirmed scope, instructor evidence, prerequisite importance, and study effort; maintain stable topic IDs and original page/slide links. No fixed concept count may truncate exam scope. |
| Research-oriented reading path: `skills/topic-map/SKILL.md:53-87,98-109,129-131` | Adds survey/foundational/current papers and suggests other separately invoked skills. This suits research entry rather than every undergraduate exam. | **Excluded** as a mandatory course path. **Adapted** only for relevant supplied research materials. Internal routing replaces student-selected subskills; external readings must not silently expand confirmed exam scope. |
| Conceptual checks: `skills/understanding-check/SKILL.md:19-29,51-72,89-117` | Default is 4–6 newly authored checks, including new scenarios, altered assumptions, and deliberate errors. Feedback distinguishes partial understanding and source revisits. | **Adapted** feedback and weakness diagnosis using actual student responses to supplied items. **Excluded** default fresh checks when policy forbids generation. Initial artifact production must not ask these additional routine questions or pretend the student answered them. |
| Procedural checks: `skills/understanding-check/SKILL.md:74-87,110-115` | Designs a new worked instance and a harder changed-input practice problem; suggests computational arithmetic checks. | **Reused** intermediate reasoning and verification principles. **Replaced** the example/variant generator with exact supplied-question explanation and solution-coverage handling. New items require the centralized policy; variants remain new questions. |
| Paper reading: `skills/paper-reader/SKILL.md:39-105,124-137` | Explains the actual paper, connects it to supplied context, identifies close-reading locations and prerequisites, and treats embedded directions as data. | **Adapted**, conditional on supplied paper content and relevance. Preserve actual section/table/equation citations; do not make paper reviews compulsory for ordinary notes or slides. |
| Paper critique: `skills/paper-critique/SKILL.md:57-87,99-150,154-158` | Links central claims to evidence, ranks issues by effect on conclusions, identifies reproducibility/scope limits, and requests later-work searches. | **Adapted** only when research appraisal belongs to the course. **Reused** claim/evidence separation and admitting unverified proofs. **Excluded** routine production-readiness reports and compulsory outside research. |
| Literature synthesis: `skills/literature-map/SKILL.md:41-75,113-128` | Compares claims, lineage, and evaluation comparability across papers; can assemble outside papers when only a topic is named. | **Adapted** only for multiple relevant supplied papers. **Reused** comparability checks. **Excluded** automatic unrelated literature discovery and invented connections. |
| Skill composition and retention: `README.md:33-65`; all seven `evals/*/prompt.md` and their graders | Five conversational skills hand off through chat context. Retention is delegated to an external spaced-repetition tool. Graders check skill invocation/routing, not source fidelity, concept correctness, Korean quality, state recovery, or generation restrictions. | **Replaced** with one entry point, authoritative course state, internal modules, and target-specific acceptance tests. **Excluded** Claude marketplace metadata/release workflow as runtime dependencies. |

## Pass All Exams: executable behavior versus prompt promises

### Ingestion

`scripts/ingest_materials.py:17-65,99-151,154-194,197-223` implements a local course root, text-derived course slug, SHA-256 local-file hashing, a converted Markdown file, a JSONL index, and material counts. Conversion is delegated to MarkItDown; the wrapper does not implement format-specific semantic extraction.

**Reused principles:** preserve inputs, normalize material once, record conversion provenance, avoid repeated work, disable URL ingestion and installed converter plugins by default. **Adapted behavior:** independently build a source inventory with stable IDs, explicit categories, original locations, extraction status, and processing limitations. A successful nonempty Markdown conversion is not proof of readable equations, complete questions, diagram fidelity, or original page coverage.

Concrete gaps requiring replacement or additional target logic:

- **Batch continuation:** `main` exits on the first handled conversion failure (`:215-221`). Earlier writes remain, later sources are skipped, and failure is printed to stderr rather than persisted in `materials.jsonl`. The target must retain per-file failures and continue verified files.
- **Windows paths:** `urlparse` is used before resolving local paths (`:99-118`). A Windows drive-prefixed path is interpreted as an unsupported scheme. `file:` is allowed by the scheme check but is then passed directly to `Path(source)` without URI decoding. These are static portability findings, not runtime reproductions.
- **Korean identity:** both scripts' slug filters retain Latin letters, digits, and CJK ideographs but remove Hangul (`ingest_materials.py:20-29`; `examctl.py:16-25`). Pure Hangul course names collapse to the same fallback slug; mixed names can also collide. Replace display-name slugs as authoritative identity with stable independent course IDs.
- **Cache provenance:** local hashes identify bytes; URL hashes identify the URL string (`:106-119`), not response content. Cache lookup is hash-based while the existence check uses the newly calculated output name (`:128-130`), so the same bytes under another name may be reconverted. Cached status is returned without a new persistent event. A URL whose content changes can reuse stale conversion. Replace with content/version-aware processing records and deterministic identity rules.
- **Source contract:** the persisted record (`:137-147`) has date, conversion time, course, source path/URL, hash, output path, title, Markdown byte count, and status. It lacks source category, stable source ID, page/slide count, per-section extraction quality, topic/question IDs, and math-review flags. Absolute machine paths are not portable student-package citations.
- **Input safety:** no wrapper-level archive traversal checks, expanded-size/file-count limits, per-file time/size budgets, embedded-content policy, or isolation are visible. ZIP/image/Office support is claimed through a dependency; its internal security and fidelity were not inspected here. Do not equate delegation with verified target compliance.
- **Dependencies:** `requirements-markitdown.txt:1` specifies `markitdown[all]>=0.1.6`, without an upper bound or lock. Missing dependency handling exists (`:68-83`), but no per-format feature matrix, OCR review, or multimodal fallback is implemented in this wrapper. Independently assess any future dependency and its transitive notices.

### State contracts actually implemented

The runtime root is `~/.pass-all-exams/courses/<slug>/`, with optional `--root`. Both scripts contain their own initialization and serialization helpers. Files are schema-free JSON/JSONL/YAML, with no contract version, formal migration, stable entity keys, foreign-key checks, or multi-writer transaction protocol.

| Runtime file | Actual contract and mutations | Decision |
| --- | --- | --- |
| `state.json` | `examctl.py:57-114` and `ingest_materials.py:154-194`: course, slug, created/updated dates, compact/standard/deep mode, initial stage `intake`, aggregate counts, and a `points` dictionary keyed by point text. Point entries contain level, status, source label, and update date. JSON replacement uses a temporary file, but coordinated multi-file transactions/locking are absent. | **Replaced** with one versioned authoritative course state and stable topic IDs. Keep display names separate; track planning, teaching exposure, and demonstrated mastery separately. |
| `course.yaml` | Initialized only when absent; example adds date, exam types, materials, preferences and review intervals. Neither Python helper reads YAML back or schedules from it. `init --force` can reset JSON while retaining existing logs/config. | **Adapted** conceptual profile; **replaced** duplicated mutable configuration and lifecycle. A filename/example is not an enforced planning contract. |
| `materials.jsonl` and `materials/*.md` | Append-only successful conversion metadata and converted Markdown with an HTML provenance header; no persistent failed/partial record. | **Adapted** indexing idea; **replaced** record shape with source-manifest requirements and portable package references. |
| `errors.jsonl` | `examctl.py:118-137`: date, point text, free-form reason, question type, must-know flag, open/stubborn status. The reference lists six diagnosis categories, while `--reason` does not enforce them. No resolution/update command. | **Adapted** six-way diagnostic taxonomy; **replaced** storage with error IDs, supplied question/subquestion references, response evidence, repair events, and resolution history. |
| `cards.jsonl` | `examctl.py:140-174,228-235`: date, point, front, back, due string, priority. Due values are not validated as dates; status returns the first ten lexically due entries in append order. No completed/reviewed transition, interval calculation, priority ordering, or rescheduling command. | **Adapted** explicit due-review idea. **Replaced** scheduling/storage; supplied-item references or checklists must not become an uncontrolled fresh-question channel. |
| `sessions.jsonl` | Touched by `init` (`examctl.py:83-84`), with no append/resume/checkpoint command in the complete parser (`:200-250`). `stage` is initialized/read but not advanced by those commands. | **Replaced** with resumable orchestration checkpoints and truthful artifact/validation status. Do not claim the existence of an operational resumption engine from this empty-log convention. |

`examctl.py:113` counts statuses `taught`, `corrected`, and `mastered` together as `points_done`. This is not evidence-based mastery. No target mastery gains may be assigned for writing a package or merely explaining a topic. A self-reported level must remain distinguished from demonstrated performance.

The target's required `exam_question_registry`, `solution_registry`, `exam_analysis`, `generation_policy`, `study_plan`, and `run_manifest` have no implemented equivalents here. Source categories, original question numbering, official-solution coverage, answer-key-only reasoning, subquestion matching, and conflicting-solution preservation need independent contracts and behavior.

### Learning, diagnosis, review, and intake

| Evidence | Finding | Decision |
| --- | --- | --- |
| `SKILL.md:24-65`; `references/pipeline.md:27-59` | Offers explicit start/resume/drill/retry/summary commands and a compact, one-point interactive loop. Intake requests missing information but has no enforced eight-question cap, single-message budget, generation consent field, or full first-run package orchestrator. | **Reused** collect-only-missing-information principle. **Replaced** control flow with automatic complete-package orchestration after one intake batch. Commands remain optional subsequent intents, never prerequisites. |
| `references/pipeline.md:71-115` | Small exam-sized points, prerequisites, preserved instructor wording, concrete explanations and a learner response. These are agent instructions, not semantic processing code. | **Adapted** teaching structure and must/key/support distinctions with explicit evidence and stable IDs. Comprehensive first-run materials cannot be truncated to compact-session limits. |
| `references/pipeline.md:116-159`; `references/prompt-patterns.md:25-82` | Drills and repairs routinely create new situations, near-transfer problems, blanks, and changed-angle retests. | **Excluded** as unconditional defaults. **Adapted** correction and alternate explanations around unchanged supplied questions. Initial package generation cannot simulate interactive answers. |
| `references/pipeline.md:143-170` | Lists confusion, missing term, logic reversal, transfer failure, calculation, and expression errors; suggests same-day/next-day/three-day/final-day reviews. | **Adapted** diagnosis and review recommendations. **Replaced** scheduling mechanism with exam-date-aware, availability-bounded blocks and persisted review results. References alone do not implement these intervals. |
| `SKILL.md:67-92`; `references/prompt-patterns.md:5-23` | Separates material evidence, inference, and unconfirmed claims; prompts generally cite converted filename/heading. Conflict handling asks a further question. | **Reused** epistemic distinctions. **Adapted** Korean labels and original page/slide citations; preserve competing source claims and disclose uncertainty without a second routine intake round. No historical count becomes a future probability. |
| `scripts/validate_skill.py:20-70`; `PROJECT_CHECK.md:5-36` | Validator checks frontmatter basics and required file existence. Historical project notes report package/syntax checks and a Markdown conversion smoke test. They do not demonstrate target E2E behavior. | **Replaced** acceptance checks with policy, content/provenance, coverage, planning arithmetic, privacy, and persistence tests. Upstream reported passes are not fresh test results from this audit. |
| `scripts/package_skill.py:12-34`; install scripts; `references/platforms.md` | Package builder recursively includes files except a small denylist. Installers use destructive replacement/synchronization and the quick installer clones an unpinned revision and optionally installs dependencies. Platform claims cover Codex/Claude/OpenClaw/OpenCode, not verified ChatGPT Work. | **Excluded** code/installer reuse. **Adapted** packaging goal with an explicit authorized file list, private runtime separation, portable source copies, and environment-specific verification. Never include arbitrary repository/runtime contents in a student ZIP. |

## Central policy incompatibility and target decisions

Question generation must be owned by one target policy rather than inherited prompts. Every output and future learning path must respect it, including flashcards, diagnostics, examples, remediation, and resumed sessions.

| Situation in the requirements | Required independently implemented behavior |
| --- | --- |
| Any usable historical questions | Reuse their exact wording/conditions or source references. No new variants, parallel questions, diagnostic items, or mock questions. Timed practice may reuse originals unchanged. |
| Complete supplied worked solutions | Preserve those solutions and numbering; produce navigation and consistency flags. Do not replace them with an AI rewrite. |
| No/partial worked solutions or answer-key-only material | Author only the missing reasoning/subparts, retain supplied answers/solutions, identify AI authorship and unresolved verification. No new question is needed. |
| No historical questions; explicit Yes | Only material-grounded AI-created practice is eligible, with honest provenance and matching solutions. |
| No historical questions; No or unanswered | No new questions. Concepts, supplied exercises, plans and review checklists remain available. |
| Historical file present but unreadable | Record extraction failure; absence of extracted text is not generation consent. Do not silently treat it as no historical material. |
| Solution-only source | Preserve the solution source; do not reverse-engineer fictional original questions. |

The renderer's later authorized role is presentation of supplied semantic content and effective policy, not independent question synthesis or policy/schema ownership. Conditional artifacts must be controlled by verified usable history, supplied-question presence, and both generation permission and nonempty generated content. Individual Markdown, per-file dependency metadata, and a package ZIP are target requirements; the final manifest belongs to the main workflow. Missing semantic content must be disclosed rather than padded with a fabricated study guide or progress.

## License inspection and attribution decision

Both exact checkouts contain a root `LICENSE` with MIT terms, not merely a README badge:

- Study Skills `LICENSE`: copyright year 2026, with no holder name on the copyright line. `.claude-plugin/plugin.json:5-10` separately identifies Jacquard Labs and declares MIT. Do not silently insert a holder into the original notice if it is ever redistributed.
- Pass All Exams `LICENSE`: copyright 2026 Tianyang Song. `SKILL.md` and README also identify MIT.

The inspected license files condition redistribution of copies/substantial portions on retaining the copyright and permission notices and contain a warranty disclaimer. No protected upstream code or substantial expressive content is copied in this work. The current decision is independent implementation from functional requirements, with provenance recorded in project notices. If that decision changes, preserve the actual required upstream notice verbatim with the reused portion; do not substitute this audit for the license. A future converter/dependency choice needs its own attribution review. No license conclusion about Exam Planner, Exam Intelligence, MarkItDown internals, or their transitive dependencies is established by this two-source inspection.

## Validation limits and remaining acceptance work

This is a static source audit, not an executed platform or educational-quality certification. The exact implementations and instruction files were read; tree/status/commit evidence was obtained locally. Upstream test suites, dependency installation, live conversions, mathematical solving, and ChatGPT Work loading were not run. Static consequences above are labeled accordingly.

Future target acceptance must independently verify: one-batch intake of at most eight questions; all historical/solution/consent edge cases; original-question and official-solution integrity; partial extraction continuation; Korean course-ID isolation; portable page/slide provenance; correct arbitrary-horizon schedules; no fake mastery; review/resume consistency; private data exclusion; dependency failures; archive safety; and substantial source-grounded Korean artifacts. Other upstream audits and any eventual implementation/test report must be maintained separately.
