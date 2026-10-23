# End-to-end synthetic fixtures

All course notes, examinations, exercises, and solutions in this directory are
newly authored synthetic Korean examples. They contain no private student data
and do not describe actual courses, instructors, or historical examinations.

`semantic_stubs.json` is an **explicit, hand-authored semantic test stub**, not
real model output. The tests supply it at the documented host-agent boundary;
they do not mock ingestion, policy, planning, rendering, persistence, or ZIP
packaging. Passing these tests does not establish automatic semantic extraction
or general mathematical solving by a model.

Source IDs in the JSON use fixture filenames as symbolic aliases. The test
adapter binds those aliases and their locations to the real ingestion manifest.
It changes no question wording, solution text, topic classification, or answers.
The profile's exam date is set relative to the test date so the examples remain
future-dated. Runtime inputs, state, copied originals, and outputs live under
pytest's `tmp_path`, outside Git checkouts.

The three exams represent three variants across two sittings. There are five
historical leaf questions: three on equations and two on differentiation. The
context parent and ordinary exercise must not increase historical counts. Both
topics occur in two of the three variants. Equations occur in one sitting and
differentiation in two.

`corrupt_history.pdf.txt` is deliberately invalid PDF text. Tests copy it to a
temporary `.pdf` path to exercise unreadable-history handling without storing
a binary document or relying on successful optional PDF extraction.
