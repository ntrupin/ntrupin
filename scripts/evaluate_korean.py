"""Opt-in GPT evaluation for the curated Korean passages."""

import argparse
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from server.korean_analysis import ReaderError, analyze, model_name

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/korean_passages.json"


def main():
    cases = {case["id"]: case for case in json.loads(FIXTURES.read_text())}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", metavar="CASE", nargs="*", help="Fixture IDs (all by default).")
    parser.add_argument("--list", action="store_true", help="List fixture IDs without using the API.")
    args = parser.parse_args()
    if args.list:
        print("\n".join(cases))
        return 0
    if unknown := set(args.cases) - cases.keys():
        parser.error(f"Unknown cases: {', '.join(sorted(unknown))}")
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    model = model_name()
    failures = 0
    for name in args.cases or cases:
        case = cases[name]
        print(f"\n{name} ({model})\nLook for: {case['look_for']}\n{case['text']}", flush=True)
        try:
            result = analyze(case["text"], [], model=model)
        except ReaderError as exc:
            print(exc)
            failures += 1
            continue
        print(result.model_dump_json(indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
