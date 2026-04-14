"""
Generates EVALUATION.md from eval results.
"""

from datetime import datetime


def generate_report(results: list[dict], output_path: str = "EVALUATION.md"):
    total = len(results)
    passed = sum(r["score"] for r in results)
    success_rate = (passed / total * 100) if total > 0 else 0

    lines = []
    lines.append("# Evaluation Report — Calendar Agent\n")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"**Success Rate: {passed}/{total} ({success_rate:.0f}%)**\n")
    lines.append("\n---\n")

    # summary table
    lines.append("## Results Summary\n")
    lines.append("| ID | Description | Category | Scorer | Result |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        status = "✅ PASS" if r["score"] == 1 else "❌ FAIL"
        lines.append(
            f"| {r['id']} | {r['description']} | {r['category']} | {r['scorer']} | {status} |"
        )

    lines.append("\n---\n")

    # per test detail
    lines.append("## Detailed Results\n")
    for r in results:
        status = "✅ PASS" if r["score"] == 1 else "❌ FAIL"
        lines.append(f"### {r['id']} — {r['description']} {status}\n")
        lines.append(f"**Category:** {r['category']}  ")
        lines.append(f"**Scorer:** {r['scorer']}\n")
        lines.append(f"**User message:** `{r['message']}`\n")
        lines.append(f"**Agent response:**\n> {r['response'][:300]}{'...' if len(r.get('response','')) > 300 else ''}\n")
        lines.append(f"**Score reason:** {r['reason']}\n")

    lines.append("\n---\n")

    # failure analysis
    failures = [r for r in results if r["score"] == 0]
    if failures:
        lines.append("## Failure Analysis\n")
        for r in failures:
            lines.append(f"### {r['id']} — {r['description']}\n")
            lines.append(f"**What went wrong:** {r['reason']}\n")
            lines.append(f"**Proposed fix:** See README.md trade-offs section.\n")
    else:
        lines.append("## Failure Analysis\n")
        lines.append("All test cases passed.\n")

    lines.append("\n---\n")
    lines.append("## Methodology\n")
    lines.append(
        "Three scoring strategies were used:\n\n"
        "- **tool_called** — verifies the agent invoked the correct Google Calendar API tool "
        "by inspecting Langfuse trace spans. Pass/fail is deterministic.\n"
        "- **llm_judge** — uses GPT-4o-mini to evaluate whether the agent's natural language "
        "response meets the expected behavior criteria. Used for rule adherence and graceful "
        "handling cases where deterministic checks are insufficient.\n"
        "- **state_check** — queries MongoDB directly after the agent runs to verify the "
        "correct data was persisted. Used for memory/preference saving tests.\n"
    )

    report = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(report)

    print(f"\n  Report written to {output_path}")
    return report
