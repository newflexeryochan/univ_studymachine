"""Developer adapter; the hosting agent executes these steps invisibly for students."""

import argparse
import json
import sys
from pathlib import Path

from jsonschema.exceptions import ValidationError

from . import workflow


def read(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf-8-sig")) if path else default


def main(argv=None):
    # JSON is a UTF-8 transport even on Windows hosts with a legacy console codepage.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Univ StudyMachine host-agent helpers")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "intake", "review", "answer", "finish", "resume", "record", "correct", "replan"):
        p = sub.add_parser(command)
        p.add_argument("--state", required=True)
        if command == "prepare":
            p.add_argument("--materials", nargs="+", required=True)
            p.add_argument("--profile")
            p.add_argument("--categories")
            p.add_argument("--defer-intake", action="store_true")
        elif command == "intake":
            p.add_argument("--profile")
        elif command == "review":
            p.add_argument("--reviews", required=True)
        elif command == "answer":
            p.add_argument("--answers", required=True)
        elif command == "finish":
            p.add_argument("--draft", required=True)
            p.add_argument("--start-date")
        elif command == "record":
            p.add_argument("--question", required=True)
            p.add_argument("--correct", choices=("yes", "no"), required=True)
            p.add_argument("--note", default="")
            p.add_argument("--observed-at")
        elif command == "correct":
            p.add_argument("--corrections", required=True)
        elif command == "replan":
            p.add_argument("--profile")
            p.add_argument("--start-date")
    a = parser.parse_args(argv)
    try:
        if a.command == "prepare":
            result = workflow.prepare(a.state, a.materials, read(a.profile, {}), read(a.categories), a.defer_intake)
        elif a.command == "intake":
            result = workflow.open_intake(a.state, read(a.profile))
        elif a.command == "review":
            result = workflow.review_sources(a.state, read(a.reviews))
        elif a.command == "answer":
            result = workflow.answer(a.state, read(a.answers))
        elif a.command == "finish":
            result = workflow.finish(a.state, read(a.draft), a.start_date)
        elif a.command == "resume":
            result = workflow.resume(a.state)
        elif a.command == "record":
            result = workflow.record(a.state, a.question, a.correct == "yes", a.note, a.observed_at)
        elif a.command == "correct":
            result = workflow.correct(a.state, read(a.corrections))
        else:
            result = workflow.replan(a.state, read(a.profile), a.start_date)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, ValidationError) as exc:
        print(json.dumps({"error": str(exc), "status": "incomplete"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
