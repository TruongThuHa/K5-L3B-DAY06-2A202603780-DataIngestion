"""Chấm truy xuất tự động (Hit@1, Evidence Hit@3) và tổng hợp theo cấu hình + dev/test.

Chỉ chấm được 'có chứa đủ bằng chứng hay không'. Nhãn coherence và grounding phải chấm tay.
"""
from typing import Any

from .ingestion import flatten


def gold_options(question: dict[str, Any]) -> list[tuple[str, int, str]]:
    options = [(question["gold_source_id"], question["gold_page"], question["evidence_quote"])]
    for alt in question.get("alternative_gold", []):
        options.append((question["gold_source_id"], alt["gold_page"], alt["evidence_quote"]))
    return options


def is_hit(hit: dict[str, Any], question: dict[str, Any]) -> bool:
    """Hit = đúng nguồn + đúng trang gold + chứa ĐỦ đoạn evidence."""
    text = flatten(hit["text"])
    return any(hit["document_id"] == src and hit["page"] == page and flatten(ev) in text
               for src, page, ev in gold_options(question))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    gold_pages = {page for _, page, _ in gold_options(question)}
    flags = [is_hit(h, question) for h in hits]
    result = {
        "hit_at_1": bool(flags[:1] and flags[0]),
        "hit_at_3": any(flags[:3]),
        "hit_ranks": [i + 1 for i, f in enumerate(flags) if f],
        # đúng trang nhưng không chứa đủ evidence -> thường do evidence bị cắt giữa 2 chunk
        "gold_page_but_split": any(h["page"] in gold_pages for h in hits[:3]) and not any(flags[:3]),
    }
    if question.get("filter"):
        result["filter_respected"] = all(all(h.get(k) == v for k, v in question["filter"].items()) for h in hits)
    return result


def summarize(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for key in sorted({(t["strategy"], t["split"]) for t in traces}):
        group = [t for t in traces if (t["strategy"], t["split"]) == key]
        n = len(group)
        h1 = sum(t["eval"]["hit_at_1"] for t in group)
        h3 = sum(t["eval"]["hit_at_3"] for t in group)
        with_filter = [t for t in group if t["filter_applied"]]
        respected = sum(t["eval"].get("filter_respected", False) for t in with_filter)
        rows.append({
            "strategy": key[0], "split": key[1], "n": n,
            "hit_at_1": f"{h1}/{n}", "hit_at_1_pct": round(100 * h1 / n, 1),
            "hit_at_3": f"{h3}/{n}", "hit_at_3_pct": round(100 * h3 / n, 1),
            "filter_compliance": f"{respected}/{len(with_filter)}" if with_filter else "N/A",
            "split_evidence_cases": sum(t["eval"]["gold_page_but_split"] for t in group),
        })
    return rows
