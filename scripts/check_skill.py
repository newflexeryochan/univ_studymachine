"""Check installable entrypoint, bundled references, and published schema consistency."""

import json
import re
from pathlib import Path

from studymachine.contracts import schema_documents


def check(root):
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n") or "name: univ-studymachine" not in skill:
        raise ValueError("Missing canonical Skill frontmatter")
    for link in re.findall(r"\]\(([^)]+)\)", skill):
        if "://" not in link and not (root / link.split("#")[0]).exists():
            raise ValueError(f"Missing bundled reference: {link}")
    for name, expected in schema_documents().items():
        actual = json.loads((root / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError(f"Published schema drift: {name}")
    return "Canonical Skill, references and versioned schemas validated"


if __name__ == "__main__":
    print(check(Path(__file__).resolve().parents[1]))
