"""Tạo 3 bảng chấm tay (coherence, metadata, grounding). Chạy từ starter/:  python -m src.audit

Code chỉ chuẩn bị bảng; cột điểm/nhãn để TRỐNG cho người chấm tự điền.
"""
import csv
import json
from pathlib import Path

from .ingestion import flatten, load_corpus
from .run import MANIFEST, QUESTIONS, RESULTS, build_chunks

COHERENCE_PAGES = 10  # 10 vị trí chọn TRƯỚC khi xem điểm: điểm giữa của 10 trang nội dung đầu tiên


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig để Numbers/Excel hiện đúng tiếng Việt
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def coherence_sheet(pages, chunks) -> list[dict]:
    rows = []
    for page in sorted(pages, key=lambda p: p.page)[:COHERENCE_PAGES]:
        flat = flatten(page.text)
        mid = len(flat) // 2
        probe = flat[mid:mid + 25]
        for strategy in ("A", "B"):
            candidates = [c for c in chunks[strategy] if c.page == page.page]
            chosen = next((c for c in candidates if probe in flatten(c.text)), None) or \
                next((c for c in candidates if flat[mid:mid + 8] in flatten(c.text)), candidates[0])
            rows.append({"position_id": f"pos{page.page:03d}", "page": page.page,
                         "section": page.metadata.get("section"),
                         "strategy": strategy + (" (C dùng chung chunk của B)" if strategy == "B" else ""),
                         "chunk_id": chosen.chunk_id, "position_text": probe, "chunk_text": chosen.text,
                         "score_0_2": "", "reason": ""})
    return rows


def metadata_sheet(traces, page_text) -> list[dict]:
    rows = []
    for t in traces:
        for rank, h in enumerate(t["hits"], 1):
            on_page = flatten(h["text"]) in page_text.get((h["document_id"], h["page"]), "")
            rows.append({"question_id": t["question_id"], "strategy": t["strategy"], "rank": rank,
                         "chunk_id": h["chunk_id"], "source": h["source"], "page": h["page"],
                         "section": h["section"], "filter_applied": json.dumps(t["filter_applied"] or {}),
                         "auto_text_found_on_page": "yes" if on_page else "NO - check",
                         "chunk_text_start": flatten(h["text"])[:200],
                         "source_ok_Y_N": "", "page_ok_Y_N": "", "section_ok_Y_N": "", "note": ""})
    return rows


def grounding_sheet(traces, questions) -> list[dict]:
    by_id = {q["id"]: q for q in questions}
    rows = []
    for t in traces:
        q = by_id[t["question_id"]]
        top3 = "\n\n".join(f"[{i}] p.{h['page']} ({h['section']}): {flatten(h['text'])}"
                           for i, h in enumerate(t["hits"], 1))
        rows.append({"question_id": t["question_id"], "strategy": t["strategy"], "question": q["question"],
                     "expected_answer": q["expected_answer"], "auto_evidence_hit_at_3": t["eval"]["hit_at_3"],
                     "top3_chunks": top3, "score_0_2": "", "reason": ""})
    return rows


def main() -> None:
    trace_file = RESULTS / "traces_test.jsonl"
    if not trace_file.exists():
        raise SystemExit("Chưa có results/traces_test.jsonl. Chạy: python -m src.run evaluate --split test")
    traces = [json.loads(line) for line in trace_file.open(encoding="utf-8")]
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    pages, _ = load_corpus(MANIFEST)
    page_text = {(p.document_id, p.page): flatten(p.text) for p in pages}
    out = RESULTS / "audit"
    out.mkdir(parents=True, exist_ok=True)
    sheets = {"audit_coherence.csv": coherence_sheet(pages, build_chunks(pages)),
              "audit_metadata.csv": metadata_sheet(traces, page_text),
              "audit_grounding.csv": grounding_sheet(traces, questions)}
    for name, rows in sheets.items():
        _write(out / name, rows)
        print(f"  results/audit/{name}: {len(rows)} dòng cần chấm")


if __name__ == "__main__":
    main()
