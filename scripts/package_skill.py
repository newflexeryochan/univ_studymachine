"""Package one self-contained Skill using an explicit implementation-only allowlist."""

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["SKILL.md", "pyproject.toml", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"]
DIRS = ["agents", "references", "assets", "schemas", "docs", "scripts"]


def package(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    target = output / "univ-studymachine.zip"
    paths = [ROOT / name for name in FILES] + [ROOT / "scripts/study.py"]
    for directory in DIRS:
        paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix != ".pyc"
                     and not any(part.endswith(".egg-info") for part in p.parts))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(set(paths)):
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                raise ValueError("Package must contain only repository implementation files")
            bundle.write(path, "univ-studymachine/" + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as bundle:
        if bundle.testzip():
            raise ValueError("Invalid Skill ZIP")
    target.with_suffix(".zip.sha256").write_text(hashlib.sha256(target.read_bytes()).hexdigest() + "\n", encoding="ascii")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    print(package(parser.parse_args().output))
