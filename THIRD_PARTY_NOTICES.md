# Third-party research and dependency notices

Recorded 2026-10-23. The following upstream projects were inspected as functional research for Univ StudyMachine. Their presence in this register does **not** mean their code, Skill prompts, templates, fixtures, artwork, or substantial documentation were incorporated. The implementation is independently written from functional requirements; none of these four Skills is a required installed runtime dependency.

## Audited research sources

| Project | Repository and exact inspected commit | License evidence | Incorporation decision |
| --- | --- | --- | --- |
| Study Skills | [jacquardlabs/study-skills](https://github.com/jacquardlabs/study-skills), `a576399e21e64651a4e7b0bffa5998d26f10301b` | Root `LICENSE` contains MIT terms. Copyright line records 2026 without naming a holder. Plugin metadata separately identifies Jacquard Labs. | Research reference for concept prerequisites, source-based reading, and feedback. Independent implementation; no copied component. |
| Pass All Exams | [SolarAscent/pass_all_exams](https://github.com/SolarAscent/pass_all_exams), `2f4772259047672c834f6c7f2f23401efb782113` | Root `LICENSE` contains MIT terms; copyright 2026 Tianyang Song. | Research reference for ingestion, evidence labels, learning/error repair, and durable review. Independent implementation; upstream question-generation defaults and code are excluded. |
| Exam Intelligence | [InstinctEx/exam-intelligence](https://github.com/InstinctEx/exam-intelligence), `735bb8bccf5a5a23a9740d571fae5f3e27f7aece` | The separate exam/planning audit records an inspected root MIT `LICENSE`, crediting 2026 InstinctEx and Exam Intelligence contributors. | Research reference for semantic classification separated from deterministic historical analysis. Independent implementation; no copied engine, practice generator, recipes, or fixtures. |
| Study Planner / `exam-planner` | [blueqwertz/study-planner](https://github.com/blueqwertz/study-planner), `71fd6d90e29d546c479195a5b966ad6973c90c02` | The separate exam/planning audit found an MIT declaration in `README.md` but no complete license/copyright notice in the three-file snapshot. The README also references a different installation repository. | Protected Skill prose/templates are excluded from copying. General scheduling behavior is implemented independently. No missing copyright attribution is invented. |

The exact local paths, inspected file ledgers, functional decisions, and limits of inspection are documented in [the study/learning audit](docs/audit-study-learning.md) and [the exam/planning audit](docs/audit-exams-planning.md). The latter is the evidence source for the last two entries; they were not independently re-audited by the artifact-rendering work. These SHAs identify local snapshots, without asserting they are the latest remote versions.

## Redistribution boundary

The inspected MIT licenses require retention of the original copyright and permission notices in copies or substantial portions of the covered software and include warranty disclaimers. No upstream code or substantial expressive material is being redistributed under this research-only decision. This source register does not replace a required license notice if the incorporation decision later changes. Preserve the exact applicable upstream license and attribution alongside any future copied component, and record the component and pinned version here.

For Study Planner, the incomplete licensing/attribution evidence is not treated as permission to copy its Skill text. Obtain the applicable complete licensing material before any future copying. No upstream software license establishes permission to publish student uploads, examination papers, instructor solutions, or private generated study packages. Those remain private runtime material.

## Runtime dependencies

The artifact renderer and its ZIP/source-copy handling use Python's standard library. Its tests use the development dependency pytest. The project declares other external runtime/document libraries in `pyproject.toml`; they are installed dependencies, not code copied from the four research projects. This research-source register is not a complete dependency license inventory or a claim that optional libraries or their transitive dependencies were audited. A distribution that vendors any dependencies must include the applicable notices for the actual bundled versions.

Microsoft MarkItDown was observed as a dependency used by Pass All Exams. No MarkItDown code or upstream ingestion wrapper is copied into this renderer, and that observation does not establish a new renderer dependency.
