# Integration contract v1

Implementation text is English; student content is Korean by default. All modules live in `scripts/studymachine/`, importable as `studymachine`. Python 3.11 is a supported fallback; 3.12+ is preferred. JSON objects use `schema_version: 1`. No external AI service: the hosting Skill agent performs semantic work and writes a validated semantic draft. Deterministic code never pretends to solve arbitrary questions.

## Shared data

`course_profile`: `course_id`, `subject`, `exam_at` (ISO datetime/date or null), `timezone` (IANA, explicit), `scope` (text or null), `availability` (mapping ISO dates or weekday names `monday` etc to minutes, or null), `preparation`, `target`, `format`, `instructor_guidance`, `language` (default `ko`), `generation_consent` (`yes`/`no`/null). Reliable field evidence can be recorded in `evidence`.

`source_manifest`: `sources` list. Each source: `id`, `filename`, `original_path`, `sha256`, `file_type`, `category`, `status` (`processed`/`partial`/`failed`), `sections` list of `{location, text}`, `page_count`, `limitations` list, `topic_ids`, `question_ids`. Locations are stable labels, e.g. `page:1`, `slide:2`, `lines:1-8`. Categories: `syllabus`, `lecture_slides`, `textbook`, `lecture_notes`, `assignment`, `historical_exam`, `official_solution`, `student_solution`, `answer_key`, `formula_sheet`, `other`. ZIP containers can be `other`; members retain archive-qualified names. Suspected history must fail closed even when unreadable.

`semantic draft`: `{schema_version:1, topics:[], exams:[], questions:[], solutions:[], generated_questions:[], limitations:[]}`. Topic: `{id,title,prerequisites:[],in_scope:true,importance:1,weakness:0.5,estimated_minutes:60,explanation,definitions:[],formulas:[],procedures:[],common_mistakes:[],references:[{source_id,location}],evidence_kind:'source_backed'|'ai_interpretation'}`. Exam: `{id,label,source_id,sitting_id,variant}`. Question: `{id,number,kind:'historical'|'exercise',source_id,location,text,topic_ids:[],exam_id:null,parent_id:null,pattern:null,method:null,confidence:1,needs_review:false}`. Split subquestions as individual IDs; parents retained only as context (`is_context:true`) and not counted. Solution: `{id,question_id,origin:'official'|'student'|'answer_key'|'ai',coverage:'complete'|'partial'|'answer_only'|'unresolved',text,references:[],verification:'verified'|'unchecked'|'conflict'|'unresolved',note:''}`. Missing subquestion reasoning must have AI additions; originals must remain.

Generated question: `{id,label:'AI 생성 연습문제',text,answer,explanation,references:[{source_id,location}]}`. Every generation entry point consults policy. No generated items if any historical questions or suspected unreadable history exist, regardless of consent. No reverse engineering questions from solutions.

`generation_policy`: `{schema_version:1,allowed,consent,historical_present,unreadable_history,reason}`.

`exam_analysis`: `{schema_version:1,exam_count,sitting_count,question_count,topics:[{topic_id,exam_count,exam_denominator,question_count,historical_frequency}],patterns:[],limitations:[]}`. Count exam variants independently, sittings separately; semantic duplicate imports rejected, context not counted. Historical frequency is descriptive only.

`study_plan`: `{schema_version:1,mode,start_date,end_date,conditional,assumptions:[],limitations:[],days:[{date,available_minutes,buffer_minutes,blocks:[{topic_id,task,minutes,priority,source_ids:[],question_ids:[],completion,review}]}],unscheduled:[]}`. No availability => conditional plan with no invented dated capacity. Respect prerequisite study before dependent topics, review and correction, explicit buffers. Horizon never hardcoded to seven days. Mode thresholds <48h, 2–7d, 8–21d, >21d.

`mastery_state`: `{schema_version:1,observations:[],topics:{}}`. No synthetic mastery. `error_log`: `{schema_version:1,entries:[]}`. Observation records actual student results and schedules review.

## Module interfaces

Ingestion `ingest(paths, storage_dir, category_overrides=None) -> source_manifest`; storage_dir is private and outside the source checkout. Never overwrite originals. Optional libraries for PDF/docx/pptx/xlsx; explicit unsupported status for legacy formats and image review requirements. Safe ZIP extraction with resource and traversal limits.

Planning `analyze_exams(draft) -> exam_analysis`; `order_topics(topics) -> list`; `build_plan(profile, topics, questions, analysis, start_date) -> study_plan` (date or ISO date allowed). Reject cycles and invalid references. Scope-excluded prerequisites create warnings rather than silent scope expansion.

Artifact rendering `render_package(output_dir, profile, manifest, draft, analysis, plan, policy, mastery, errors, qa) -> list of artifact metadata`. Each metadata `{filename,source_ids,status}`. Render only relevant artifacts; Korean filenames from user prompt, plus manifest.json and package.zip. The main workflow owns final run manifest, QA, atomic state.

Workflow checkpoint states: `inventoried -> awaiting_intake -> awaiting_semantics -> complete|partial`; an interrupted stage is resumable. Intake occurs once, max eight questions. Student never sees CLI mechanics. CLI developer adapters prepare, answer, finish, resume, record, correct. Agent must create substantive explanations before finish; unresolved content yields partial, never a false success.

## Implemented adapter extensions

The normal `prepare --defer-intake` call stops at `inventoried`. The agent inspects extracted and original content, records actual manual/visual source reviews with `review`, and merges source-established profile facts with `intake --profile`. This opens the one student batch only after preliminary inspection. `review` also works during `awaiting_semantics`; it replaces only explicitly reviewed source sections, preserves original bytes, and records method/note. It must never stand for a visual inspection the host did not perform.

`replan --profile --start-date` updates permitted profile fields and rebuilds the calendar while retaining actual observations and classification corrections. Revoked consent removes generated questions and artifact 09 on successful rebuild. `record` also rebuilds using observed weakness. These are agent adapters, not extra student commands. Completed study-block minutes are not a tracked ledger; scope-text edits require the agent to inspect and update topic membership rather than pretending a semantic remap occurred.

For another requested language, the agent translates intake before display, authors semantic content in that language, then supplies `localized_documents` mapping exactly the applicable **top-level** numbered Markdown filenames to complete translated content. Evidence copies under `sources/` stay in their original language. Structural checks preserve Markdown link targets and verbatim supplied question/solution text. A missing translation mapping produces partial output; it is not a complete requested-language package. Filenames remain stable Korean. Semantic fidelity remains the hosting agent's responsibility.

Semantic drafts are checkpointed before rendering. Rebuilds invalidate the previous completion stage before saving changed observations/profile/corrections. Exceptions leave `awaiting_semantics` for a retry. Unsupported schema versions are rejected without changing the original; there is no implicit v0 or future-version migration.

Subsequent drafts cannot delete previously registered original questions or supplied solution records. Supplied solution identity, coverage, original text and evidence links remain immutable; discrepancy/verification notes may be updated. This prevents omission from bypassing official-solution precedence. Localization must preserve explicit navigation anchor IDs as well as link targets and original statements.

## Ownership

Main agent owns policy.py, contracts.py, workflow.py, cli.py, intake.py, learning.py, state.py, QA, packaging and end-to-end tests. Workers own ingestion.py (+ tests), planning.py (+ tests), artifacts.py (+ tests), docs/references as assigned. No overlapping files.
