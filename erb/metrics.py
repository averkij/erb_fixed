"""Upstream Python normalization, explicitly pinned to fuzzywuzzy 0.18's
difflib backend (no optional Levenshtein acceleration/backend switching).
ES is a percentage in [0,100], including upstream integer rounding per pair.
"""
from collections import Counter
from difflib import SequenceMatcher
import re

from .data import CATEGORIES

ES_IMPLEMENTATION = "upstream-remove_comments+fuzzywuzzy-0.18.0-ratio/difflib-autojunk=True"
STATUSES = ("pass", "test_fail", "timeout", "oom", "infrastructure_error")


def normalize(code):
    code = re.sub(r'(\"\"\".*?\"\"\"|\'\'\'.*?\'\'\')', '', code, flags=re.DOTALL)
    return "\n".join(line for line in code.split("\n") if line.strip() != "").strip()


def edit_similarity(gold, generated):
    # Preserve upstream evaluate_es_score/cal_edit_sim argument orientation too:
    # SequenceMatcher can be asymmetric when autojunk is active.
    a, b = normalize(gold), normalize(generated)
    if a == b:
        return 100
    if not a or not b:
        return 0
    return int(round(100 * SequenceMatcher(None, a, b, autojunk=True).ratio()))


def group_summary(rows, expected):
    counts = Counter(r["status"] for r in rows)
    infra = counts["infrastructure_error"]
    complete = len(rows) == expected and infra == 0
    scored = len(rows) - infra
    return {"expected": expected, "recorded": len(rows), "scored": scored,
            "passes": counts["pass"], "statuses": {s: counts[s] for s in STATUSES},
            "complete": complete,
            "micro_pass_at_1_percent": 100 * counts["pass"] / expected if complete and expected else None,
            "observed_pass_fraction": {"numerator": counts["pass"], "denominator": scored},
            "es_percent": sum(r["es"] for r in rows) / len(rows) if rows else None,
            "es_denominator": len(rows)}


def summarize(rows, tasks):
    summary = group_summary(rows, len(tasks))
    summary["es_implementation"] = ES_IMPLEMENTATION
    summary["categories"] = {
        c: group_summary([r for r in rows if r["fill_type"] == c], sum(t["fill_type"] == c for t in tasks))
        for c in CATEGORIES}
    summary["repositories"] = {
        repo: group_summary([r for r in rows if r["repo_name"] == repo], sum(t["repo_name"] == repo for t in tasks))
        for repo in sorted({t["repo_name"] for t in tasks})}
    return summary
