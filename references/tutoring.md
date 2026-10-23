# Tutoring, progress, corrections, and replanning

Use this after initial production or an interrupted run. The student can speak naturally; the host maps the request to saved course state and executes every mechanical step. No additional commands are required to obtain the original package. Do not repeat intake after the one reply.

## Resume and explain

Run `resume --state DIR`. Read the actual stage, profile, inventory, policy, draft, observations, errors, and manifest. At `inventoried`, complete the existing inspection/facts/intake sequence. At `awaiting_intake`, use the already emitted batch rather than opening a second one. At `awaiting_semantics`, continue source review/authoring and `finish`. At `complete` or `partial`, explain the saved outcome and its actual limitations.

For today's work, locate the current date in the course timezone and show its saved tasks, durations, source/question references, and completion criteria. Do not pretend a past plan is current or automatically move missed blocks. Use `replan` for an explicitly changed calendar. If no feasible dated work exists, show the conditional priorities and missing information without inventing availability.

For concept or solution help, use the cited course material and exact original question. Retain official explanations as primary evidence and add only the missing explanation. Discuss the student's actual working and identify the wrong step where available. Never generate a fresh diagnostic, numerical variant, remedial question, or flashcard question when history or unreadable suspected history exists. Recheck the policy even in a resumed session. A single original exam may be reused unchanged for timed study.

## Record an observed result

Use an existing supplied leaf question ID. Do not record a context parent, a fictional result, or mastery from merely reading an explanation. The developer/agent interface is:

```text
python scripts/study.py record --state DIR --question ID --correct yes/no --note TEXT [--observed-at YYYY-MM-DD]
```

For the synthetic walkthrough, after an actual stated outcome `1(나)를 틀렸어. 행렬식의 음수 부호를 빠뜨렸어.`, the host can execute:

```powershell
.\.venv\Scripts\python.exe scripts/study.py record --state "$env:STUDYMACHINE_STATE" --question q1b --correct no --note "행렬식의 음수 부호를 빠뜨렸다고 학생이 보고함" --observed-at 2026-10-24
```

The learning implementation stores a dated observation, topic status and a review due date; incorrect results also enter the error log. Its current fixed review rule is next day after incorrect and three days after correct. That due date is not proof the review occurred or that a compatible calendar slot exists. The command rebuilds outputs/plan using observed weakness. Inspect the regenerated package and any unscheduled work. A write can persist an observation even if a later render fails; resume and inspect rather than retrying blindly and duplicating the result.

## Correct classification without rewriting sources

`correct --state DIR --corrections corrections.json` accepts a mapping from known question ID to supported fields. Only `topic_ids`, `pattern`, `method`, `confidence`, and `needs_review` are permitted. Example for the synthetic question:

```json
{
  "q1b": {
    "topic_ids": ["t-det", "t-inverse"],
    "pattern": "2×2 역행렬과 행렬곱 검산",
    "method": "행렬식으로 존재 조건 확인 후 역행렬 공식 및 행렬곱 검산",
    "confidence": 1.0,
    "needs_review": false
  }
}
```

The overlay is preserved on later `finish` processing. Check that topic IDs exist and the classification is justified. This adapter cannot change original text, number, source, location, exam identity, solution content, or profile. To repair an AI solution, update the semantic draft and `finish`, preserving original supplied content and IDs; do not send it through `correct`. Actual source-reading repairs use `review` only in its permitted stages, not arbitrary edits to state.

## Replan and refresh

`replan --state DIR --profile updates.json --start-date ISO` accepts a **partial profile object**, not a complete state wrapper. Supported keys are `exam_at`, `scope`, `availability`, `preparation`, `target`, `instructor_guidance`, `timezone`, `language`, and `generation_consent`. Omitted keys keep their prior values. Availability replaces that mapping, so include all still-applicable weekdays/date overrides; provide explicit zero for a known unavailable day.

For an explicitly reported change to 45 weekday minutes, 90 weekend minutes, and a new exam timestamp:

```json
{
  "exam_at": "2026-11-02T14:00:00+09:00",
  "timezone": "Asia/Seoul",
  "availability": {
    "monday": 45, "tuesday": 45, "wednesday": 45,
    "thursday": 45, "friday": 45, "saturday": 90, "sunday": 90
  }
}
```

```powershell
.\.venv\Scripts\python.exe scripts/study.py replan --state "$env:STUDYMACHINE_STATE" --profile "$env:STUDYMACHINE_STATE/updates.json" --start-date "2026-10-24T09:00:00+09:00"
```

Use the real student-supplied update and actual start in a live run. Prefer an aware start timestamp for same-day cutoffs. Missing capacity, timezone, scope or date produces disclosed conditional/unscheduled work. No block may exceed available capacity including buffers. Explain what changed and which work could not fit.

Limitations are material: rebuilding preserves observations and correction overlays, but does not subtract a complete ledger of finished study-block minutes. Already studied topics may be scheduled again. There is no automatic missed-day monitor. Updating the scope text does not semantically rebuild the topic map or question assignments; reassess source-backed scope, update `in_scope`/dependencies in a valid semantic draft, and `finish` if necessary. Updating preparation/target does not independently measure mastery or generate a new semantic curriculum. Check the actual refreshed output before claiming the requested adjustment is complete.

## Consent and language changes

Consent revocation uses `{"generation_consent":"no"}`. Policy is reevaluated, generated entries are removed, and a successful rebuild omits artifact 09 and updates the ZIP/manifest. Do not claim downloaded copies or older user backups were deleted. History still prohibits generation after any consent update. New consent alone does not author practice: if allowed and requested, the host must write grounded generated items with explanations and `finish`.

For a requested language change, update `language` through `replan`, then automatically complete the full `localized_documents` procedure in [workflow.md](workflow.md). For any refresh, rebuild stale translations from newly rendered content; preserve original question/solution text and link targets. This includes changes in dates, progress, policy, and applicable files. Stable Korean filenames remain. Structural validation does not establish semantic translation quality; the host must review it. No extra student messages are needed.

Profile/observation updates and output replacement are not one atomic transaction. After an error or interruption, compare persisted profile/policy to the current manifest before delivering artifacts. Never serve a stale generated-question package after revocation or call a base Korean package complete for a different requested language.
