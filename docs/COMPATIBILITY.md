# Compatibility and runtime limitations

This is a capability and verification boundary, not a certification matrix. The shared contract permits Python 3.11 as a fallback and prefers 3.12+. The documentation pass has not verified native skill installation/loading or ChatGPT Work execution. A developer CLI result must be reported with its actual interpreter, OS, dependencies, and source scenario; it is not a substitute for those host tests.

## Hosts

| Environment | Required capabilities | Current claim and limitation |
| --- | --- | --- |
| Codex with local execution | Skill discovery, accessible uploads, Python, file writes, hosting-agent semantic authoring | Intended local path. Copy/install instructions are provided; native loading and a full student workflow are not certified by documentation. |
| ChatGPT Work | A real supported skill import/load path, uploaded-file access, suitable execution/storage/export tools, semantic and visual capabilities as needed | **Not verified.** No assumption of access to the developer's Windows files, virtual environment, credentials, or installed libraries. |
| Host with files but no Python execution | Agent can read authorized sources and write accessible content | Can provide source-grounded content with an explicit fallback notice; cannot claim CLI validation, durable CLI state, or ZIP generation ran. |
| Host without durable storage or downloadable files | Accessible conversation content | Provide complete accessible content where feasible; disclose missing persistence/export. Do not invent paths or download links. |
| Alternative-language request | Host translates intake and every applicable document through `localized_documents` | Implemented host-mediated path with structural validation. Original supplied text and links stay intact; filenames remain Korean. Semantic translation quality requires host review. |

No upstream skill installation is required at student runtime. Connected storage is optional, not part of the default workflow. An optional connector must actually be available and authorized before it can be used; do not require students to install one to finish the normal local workflow. Default processing does not upload documents to third-party conversion or AI services.

## Formats and dependencies

Install declared extras in the actual execution environment using `python -m pip install -e ".[documents]"` from the repository root. A missing dependency must name the package and installation step. If installation is unavailable, explicitly retain the file as failed/partial and continue verified material where possible. Do not silently report conversion success.

| Input | Extraction requirement | Fidelity/support boundary |
| --- | --- | --- |
| TXT / Markdown | Python text handling | Encoding, section boundaries, and unusual notation still require inspection. |
| CSV | Python CSV handling | Cell values do not automatically convey visual table structure or course semantics. |
| PDF with text | `pypdf` from `documents` extra | Embedded images, scans, equation order, and complex layout can be absent or misleading. |
| DOCX | `python-docx` | Paragraph/table text is not a guarantee that drawings, equations, or embedded objects were interpreted. |
| PPTX | `python-pptx` | Extractable slide text does not establish diagram or equation fidelity. |
| XLSX | `openpyxl` | Reading cells is not spreadsheet recalculation or chart understanding; cached values may be stale. |
| Images / scanned pages | A capable host visual tool; OCR only if explicitly available | No bundled general OCR or vision backend is promised. The host must inspect raw mathematical visuals where available; uncertain content stays flagged. |
| Legacy DOC / PPT / XLS | No native extractor promised | Explicitly unsupported without an available, verified conversion path. Preserve originals and document omissions. |
| ZIP | Safe archive handling, bounded extraction, supported member extractors | Container ingestion does not make every member readable. Preserve archive-qualified identities and reject unsafe members. |

Do not equate a filename extension or nonempty text result with successful semantic reading. An unreadable suspected historical exam remains a historical warning and blocks generation even when the student consented. Actual host reading can be recorded using `review --reviews` at `inventoried` or `awaiting_semantics`, with source ID, method, inspection note, and actual sections/category/status. Retain remaining limitations; empty non-container files cannot be processed. This is a host inspection path, not bundled OCR.

## Tools and optional output

- Semantic interpretation and solving belong to the hosting agent. There is no automatic general-course solver in Python. Arithmetic checks are useful but do not establish the correctness of every proof, interpretation, or official solution.
- Raw visual inspection depends on the host. Prefer the original uploaded page/image when equations, signs, diagrams, tables, or answer choices matter. If unavailable or ambiguous, mark the exact content unresolved and produce a partial package where necessary.
- Markdown and JSON are the canonical editable/export formats. ZIP requires actual file creation and verification. PDF requires a separate available renderer and a successful visual check; no default PDF pipeline is claimed.
- A local directory does not automatically become a downloadable attachment. Verify the host's actual link/export mechanism before presenting a file as available.

## Persistence and updates

Use a private root outside every Git checkout. The implementation repository and skill installation directory contain code/documentation, not student files. A host unable to provide such storage cannot claim normal durable-state operation. Local persistence has no documented automatic retention expiry, encryption, remote backup, synchronization, or migration across local/Work environments. No automatic deletion claim is made.

The primary flow is `prepare --defer-intake`, actual source inspection/`review`, `intake --profile`, `answer`, agent semantic authoring, and `finish`. `resume` reads saved context. `record` stores actual outcomes and rebuilds outputs. `correct` preserves supported question-field corrections and cannot edit source identity or profile. `replan --profile --start-date` updates permitted exam/date/capacity/preferences and refreshes outputs; revoked consent removes generated items/artifact 09 after successful refresh.

Replanning does not track a complete ledger of completed study-block minutes, automatically detect missed days, or semantically remap topics when only scope text changes. Observations and corrections persist, but already studied work may be assigned again. Inspect the actual plan and unscheduled work; distinguish advice from a persisted refresh. Existing downloaded exports are not recalled.

For non-Korean profiles, `finish` without `localized_documents` deliberately returns a partial base Korean package. The host must read all applicable Markdown files, supply complete translated contents keyed by exact filenames, and finish again automatically. Validation checks the applicable file set, retained original statements, and links; host review is still required for meaning and freshness after a rebuild. This adds no student messages or commands.

## Evidence needed before stronger claims

Record native discovery/loading separately from Python import/CLI execution. Verify one student request, one intake batch of at most eight, one reply, substantive agent authoring, policy/coverage validation, actual generated files, private-state resumption, and limitations in each advertised host. Use real synthetic source texts rather than an injected fixture answer. Test unreadable-history blocking, complete/partial/answer-key solution cases, consent absence, and different exam horizons. Do not infer Work support, semantic correctness, or automatic replanning from local deterministic test passes.
