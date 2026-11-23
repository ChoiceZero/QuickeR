"""Checks that src/translations.json covers every tr("...") call in src/main.py.

Run it after adding or changing UI text:  python scripts/check_translations.py
Exits with 1 if a string is missing a language, a placeholder differs from the
English text, or an entry is no longer used.
"""
import ast
import json
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"


def used_keys():
    tree = ast.parse((SRC / "main.py").read_text(encoding="utf-8"))
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr":
            if not (node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                print(f"tr() needs a string literal as first argument (line {node.lineno})")
                sys.exit(1)
            keys.add(node.args[0].value)
    return keys


def main():
    data = json.loads((SRC / "translations.json").read_text(encoding="utf-8"))
    languages = [code for code in data["languages"] if code != "en"]
    strings = data["strings"]
    used = used_keys()
    errors = []

    for key in sorted(used - strings.keys()):
        errors.append(f"missing entry: {key!r}")
    for key in sorted(strings.keys() - used):
        errors.append(f"unused entry: {key!r}")
    placeholders = lambda text: sorted(re.findall(r"\{\w+\}", text))
    for key, variants in strings.items():
        for code in languages:
            text = variants.get(code)
            if not text:
                errors.append(f"{code} missing for: {key!r}")
            elif placeholders(text) != placeholders(key):
                errors.append(f"{code} placeholders differ for: {key!r}")

    print("\n".join(errors) if errors else f"OK: {len(used)} strings x {len(languages)} languages")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
