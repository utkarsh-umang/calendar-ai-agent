"""
Entry point for the evaluation suite.

Usage (from project root inside Docker or with .env loaded):
    python -m eval.run_eval

Or directly:
    python eval/run_eval.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from eval.cases import TEST_CASES
from eval.runner import run_all
from eval.report import generate_report


async def main():
    results = await run_all(TEST_CASES)

    total = len(results)
    passed = sum(r["score"] for r in results)
    success_rate = passed / total * 100

    print("\n" + "="*55)
    print(f"  FINAL SCORE: {passed}/{total} ({success_rate:.0f}%)")
    print("="*55)

    # breakdown by category
    categories = {}
    for r in results:
        cat = r["category"]
        categories.setdefault(cat, {"passed": 0, "total": 0})
        categories[cat]["total"] += 1
        categories[cat]["passed"] += r["score"]

    print("\n  By category:")
    for cat, counts in categories.items():
        print(f"    {cat}: {counts['passed']}/{counts['total']}")

    generate_report(results, "EVALUATION.md")
    print("\n  Done. See EVALUATION.md for the full report.\n")


if __name__ == "__main__":
    asyncio.run(main())
