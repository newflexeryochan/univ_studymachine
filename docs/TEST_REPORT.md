# Validation report — 2026-10-23

## Recorded local results

Environment: Windows, Python 3.11.9 (documented fallback), isolated project virtual environment with the `documents` and `dev` extras and IANA timezone data. Python 3.12+ remains preferred. No real student documents were used.

The final local regression command was `python -m pytest -ra --junitxml=../validation-results.xml`: **280 passed, 3 skipped, zero failures**, in 43.37 seconds. The skipped tests require filesystem symlink creation privileges unavailable on this Windows host. They are not counted as passes. Archive symlink/reparse-point rejection and other archive protections were exercised. The JUnit file is an external development artifact, not private runtime state in the repository.

| Suite | Passed | Purpose |
| --- | ---: | --- |
| Core | 17 | Central policy, intake, atomic state/version rejection, source review, localization integrity, UTF-8 JSON transport, multi-topic question readiness |
| Ingestion | 134 | Native and optional extractors, missing dependencies, corruption, bounds, archive safety, source identity/classification |
| Planning | 57 | 1/5/10/30-day horizons, capacities, prerequisites, descriptive denominators, timezones, spaced review, alternatives |
| End-to-end | 39 | Complete pipeline, exact originals, official/missing/partial/answer-key solutions, permission cases, resumption, corrections, packaging |
| Artifact renderer | 20 | Conditional documents, actual citations/anchors, original copies/hashes, central policy at direct API, substantive content |
| Independent review regressions | 13 | Unreadable-history flags survive category changes, explicit resolution requires actual readable content, supplied originals survive later drafts, translated anchors and previous published output are preserved |

`ruff check scripts tests` passed. `scripts/check_skill.py` passed the canonical entrypoint, reference and published-schema consistency checks. The system skill-creator `quick_validate.py` passed when executed with UTF-8 mode; this checks structural Skill validity, not native installation. A Python wheel built successfully. The implementation-only Skill ZIP is produced and integrity-checked by `scripts/package_skill.py`.

## Mandatory scenario evidence

| Requirement | Observed automated coverage |
| --- | --- |
| Complete official solutions | Original text reused, no AI replacement, no new questions, history and plan exported |
| History without solutions | Exact existing questions receive supplied AI reasoning records; zero new questions |
| Partial solutions and answer keys | Missing leaf explanations only; original answers retained; duplicate complete AI replacement rejected |
| No history, explicit yes | Source-grounded generated-item contract and conditional artifact 09 |
| No history, no or unanswered | Zero new questions; no placeholder artifact 09 |
| Unreadable historical material | Failed extraction retained, no implied consent, partial output |
| Arbitrary horizons | 1/5/10/30-day capacity checks; same-day/exam-time boundaries and conditional unknowns |
| Adaptive intake | One batch, maximum eight, established fields omitted, conditional permission substitution |
| Source integrity | Immutable question identity, valid portable links/anchors, original-copy hashes, correction overlays |
| State and packaging | Actual observations only, fresh-process resume, no private runtime in Git, ZIP/manifest consistency, stale 09 removal |

The end-to-end automated suite explicitly injects hand-authored synthetic semantic records. It tests deterministic integration and **does not establish an automatic general-course solver**. The following separate behavioral exercise uses fresh raw source texts and agent authoring.

## Actual hosting-agent exercise

An independent Codex agent loaded the canonical `SKILL.md` and progressive references, then processed four newly created raw synthetic linear-algebra texts: exam instructions, lecture notes, two historical questions, and one supplied worked solution. It did not read test fixtures or their expected answers. The instruction was “이 자료들로 시험 대비해 줘.” A single provided student reply supplied weekday/weekend availability, preparation level, and target.

The observed adapter sequence inventoried and inspected the sources, opened **one batch of three questions** (availability, preparation, target), consumed the single reply, authored a substantive cited semantic draft, verified arithmetic with exact rational computations, and ran the actual finish pipeline. The resulting state was `complete`, QA passed with disclosed caveats, two original questions were retained, the supplied first solution was reused, only the missing second solution was AI-authored, and **zero new questions** were produced. Nine applicable numbered Korean Markdown documents, linked source evidence/original copies, `manifest.json`, and a valid ZIP were created outside the source checkout.

The arithmetic exercise checked the determinant, both products of the matrix and its supplied inverse, the linear-system solution using inverse and elimination methods, and substitution into both original equations. These observations apply to this synthetic example, not arbitrary mathematical correctness. Initial mastery and observation records remained unassessed/empty. No student learning completion was simulated.

This is a real source-reading/agent-authoring/local-execution exercise. It is **not** a test of native Skill installation/discovery, a real student upload through the ChatGPT Work UI, or Work cloud persistence/export.

Independent code review found and reproduced three bugs before delivery: category-only review could erase effective historical gating, later drafts could omit supplied solutions to bypass their precedence, and localization could remove destination anchors while retaining links. These were repaired and covered by 13 executable regressions. Render-time rejection keeps the old published package intact and checkpoints pending work at `awaiting_semantics`; it does not advertise fresh completion.

The actual source-to-package exercise also exposed multi-topic questions linked before all their required topics were ready and a generic caveat incorrectly described as extraction/classification failure. Both were repaired. The saved agent-authored draft was run again through the final code: complete state, zero new questions, **286 links/anchors checked with zero broken targets**, no early multi-topic-question links, no spurious reading-failure warning, and valid original-copy/manifest/ZIP hashes. Weekday and statistical display labels were rendered in Korean. This refresh did not simulate new student answers or mastery.

## Remaining verification boundaries

- Native Skill installation/discovery and ChatGPT Work execution have not been exercised. A compatible host must supply accessible uploads, permitted execution/storage/export and semantic capabilities; no shared local/cloud filesystem is assumed.
- Linux and Python 3.12/3.13 are configured in CI. Local Windows/Python 3.11 results do not count as those runtime results; inspect the actual workflow run before asserting passes.
- No bundled general OCR, vision service, legacy DOC/PPT conversion, PDF export, or external connector is claimed. The actual host may supply supported inspection/conversion; unreadable content remains explicit.
- The structured generation paths fail closed and reject unauthorized generated-item records. Semantic source completeness, arbitrary mathematical reasoning, newly invented questions hidden in free prose, and translation quality still require the hosting agent's review. Structural checks cannot prove those properties.
- Replanning retains observations and recalculates time/priority, but does not maintain a ledger of completed study-block minutes or automatically reinterpret changed scope text.
- Localization structure is tested; comprehensive language quality and real non-Korean student workflows are not verified.

Upstream source provenance, exact commits and licensing decisions are in the two audit documents and `THIRD_PARTY_NOTICES.md`. No upstream code or substantial protected prose was copied. All repository fixtures are synthetic.
