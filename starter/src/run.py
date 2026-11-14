"""Chạy pipeline Day 06. Chạy từ thư mục starter/:

    python -m src.run check     # kiểm tra 20 evidence có trong text đã đọc
    python -m src.run ingest    # đọc, chia chunk A/B, tạo vector, lưu vào pgvector
    python -m src.run evaluate --split dev    # chạy 15 câu dev cho A, B, C
    python -m src.run evaluate --split test   # chỉ chạy SAU KHI đã chốt cấu hình trên dev
"""
import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .evaluation import evaluate_query, gold_options, summarize
from .ingestion import flatten, load_corpus

ROOT = Path(__file__).resolve().parents[1]          # thư mục starter/
MANIFEST = ROOT / "data" / "manifest.json"
QUESTIONS = ROOT.parent / "benchmark" / "questions.json"
RESULTS = ROOT / "results"

# Ba cấu hình. C dùng chung chunk/vector với B, chỉ khác ở bộ lọc metadata -> so sánh B–C có kiểm soát.
STRATEGIES = {
    "A": {"index": "A", "chunking": "fixed_size", "size": 500, "overlap": 50, "use_filter": False},
    "B": {"index": "B", "chunking": "by_paragraph", "max_size": 800, "use_filter": False},
    "C": {"index": "B", "chunking": "by_paragraph", "max_size": 800, "use_filter": True},
}
TOP_K = 3


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_chunks(pages):
    return {
        "A": [c for p in pages for c in fixed_size(p, STRATEGIES["A"]["size"], STRATEGIES["A"]["overlap"])],
        "B": [c for p in pages for c in by_paragraph(p, STRATEGIES["B"]["max_size"])],
    }


def cmd_check() -> None:
    pages, _ = load_corpus(MANIFEST)
    text = {(p.document_id, p.page): flatten(p.text) for p in pages}
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    bad = 0
    for q in questions:
        for src, page, ev in gold_options(q):
            if flatten(ev) not in text.get((src, page), ""):
                bad += 1
                print(f"  KHÔNG THẤY: {q['id']} trang {page}: {ev[:60]}...")
    dev = sum(q["split"] == "dev" for q in questions)
    print(f"{len(questions)} câu ({dev} dev / {len(questions) - dev} test), "
          f"{sum(1 for q in questions if q.get('filter'))} câu có filter")
    print("Evidence OK: tất cả đều có trong text đã chuẩn hóa" if bad == 0 else f"Có {bad} evidence không khớp")


def cmd_ingest() -> None:
    from .embeddings import LocalEmbedder
    from .store import PgVectorStore

    load_dotenv(ROOT / ".env")
    t0 = time.perf_counter()
    pages, log = load_corpus(MANIFEST)
    chunks = build_chunks(pages)
    t_chunk = time.perf_counter() - t0

    embedder = LocalEmbedder()
    store = PgVectorStore(os.getenv("DATABASE_URL", ""), embedder.dimensions)
    store.create_schema()

    stats = {"run_at": _now(), "embedding_model": embedder.model_name, "dimensions": embedder.dimensions,
             "vector_store": "PostgreSQL 16 + pgvector, cosine distance, exact search (không dùng index ANN)",
             "content_pages": len(pages), "load_and_chunk_seconds": round(t_chunk, 2), "cost_usd": 0,
             "page_log": {s: sum(1 for x in log if x["status"] == s) for s in ("excluded", "empty", "error")},
             "strategies": {}}
    for name, items in chunks.items():
        before = store.count(name)
        t1 = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in items])
        result = store.upsert(name, items, vectors, embedder.model_name)
        lengths = [len(c.text) for c in items]
        stats["strategies"][name] = {
            "chunks": len(items), "rows_in_db_before": before, "rows_in_db_after": store.count(name),
            **result, "embed_and_store_seconds": round(time.perf_counter() - t1, 2),
            "total_chars": sum(lengths), "len_min": min(lengths), "len_median": int(statistics.median(lengths)),
            "len_mean": round(statistics.mean(lengths), 1), "len_max": max(lengths)}

    _write_json(RESULTS / "ingest_stats.json", stats)
    _write_json(RESULTS / "ingest_page_log.json", log)
    with (RESULTS / "chunks_preview.jsonl").open("w", encoding="utf-8") as f:
        for name, items in chunks.items():
            for c in items:
                f.write(json.dumps({"strategy": name, "chunk_id": c.chunk_id, "page": c.page,
                                    "section": c.metadata.get("section"), "text": c.text}, ensure_ascii=False) + "\n")
    print(f"Đã đọc {len(pages)} trang nội dung. Trang bị loại/rỗng/lỗi: {stats['page_log']}")
    for name, s in stats["strategies"].items():
        print(f"  {name}: {s['chunks']} chunk | trong DB trước {s['rows_in_db_before']} -> sau {s['rows_in_db_after']} "
              f"| độ dài TB {s['len_mean']} ký tự | {s['embed_and_store_seconds']} giây")
    print("Kết quả lưu ở results/ingest_stats.json (chạy lại lần 2: số dòng 'sau' phải giữ nguyên = không nhân đôi)")


def cmd_evaluate(split: str) -> None:
    from .embeddings import LocalEmbedder
    from .store import PgVectorStore

    load_dotenv(ROOT / ".env")
    questions = [q for q in json.loads(QUESTIONS.read_text(encoding="utf-8")) if q["split"] == split]
    embedder = LocalEmbedder()
    store = PgVectorStore(os.getenv("DATABASE_URL", ""), embedder.dimensions)
    traces = []
    for q in questions:
        qvec = embedder.embed_query(q["question"])
        for name, cfg in STRATEGIES.items():
            filters = q.get("filter") if cfg["use_filter"] else None
            hits = store.search(cfg["index"], qvec, TOP_K, filters)
            traces.append({"run_at": _now(), "strategy": name, "split": split, "question_id": q["id"],
                           "question": q["question"], "type": q["type"], "filter_applied": filters,
                           "gold_page": q["gold_page"], "evidence_quote": q["evidence_quote"],
                           "hits": [{k: h[k] for k in ("chunk_id", "document_id", "source", "page", "section",
                                                       "score", "text")} for h in hits],
                           "eval": evaluate_query(q, hits)})
    summary = summarize(traces)
    with (RESULTS / f"traces_{split}.jsonl").open("w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    _write_json(RESULTS / f"summary_{split}.json", {"run_at": _now(), "config": STRATEGIES, "rows": summary})
    with (RESULTS / f"summary_{split}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"Kết quả {split.upper()} ({len(questions)} câu):")
    print(f"  {'Cấu hình':<9}{'Hit@1':>8}{'Hit@3':>8}  {'Filter':>7}  Evidence bị cắt")
    for r in summary:
        print(f"  {r['strategy']:<9}{r['hit_at_1']:>8}{r['hit_at_3']:>8}  {r['filter_compliance']:>7}  {r['split_evidence_cases']}")
    print(f"Chi tiết từng câu: results/traces_{split}.jsonl | Bảng: results/summary_{split}.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Day 06 pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("ingest")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--split", choices=["dev", "test"], required=True)
    args = parser.parse_args()
    try:
        {"check": cmd_check, "ingest": cmd_ingest}.get(args.cmd, lambda: cmd_evaluate(args.split))()
    except Exception as exc:  # báo lỗi rõ ràng, không âm thầm chuyển sang dữ liệu giả
        print(f"LỖI: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
