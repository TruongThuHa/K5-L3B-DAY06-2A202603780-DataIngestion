"""Ghi artifacts/experiment_log.csv từ kết quả đã chạy. Chạy từ starter/:  python -m src.explog"""
import csv
import json

from .embeddings import MODEL_NAME
from .run import RESULTS, ROOT, STRATEGIES

HYPOTHESIS = {
    "A": "Baseline: cắt đều 500 ký tự dễ làm đứt câu chứa bằng chứng",
    "B": "Gom theo đoạn/câu giữ trọn ý nên chunk chứa đủ bằng chứng hơn A",
    "C": "Như B + lọc section: loại các đoạn trùng ý ở phần khác khi câu hỏi chỉ định phần",
}


def _summary(split: str) -> dict[str, dict]:
    path = RESULTS / f"summary_{split}.json"
    if not path.exists():
        return {}
    return {row["strategy"]: row for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def main() -> None:
    dev, test = _summary("dev"), _summary("test")
    stats = json.loads((RESULTS / "ingest_stats.json").read_text(encoding="utf-8"))["strategies"]
    rows = []
    for name, cfg in STRATEGIES.items():
        index = stats[cfg["index"]]
        rows.append({
            "strategy": name,
            "chunking": cfg["chunking"] + (" (dùng chung index B)" if name == "C" else ""),
            "chunk_size": cfg.get("size") or f"max {cfg['max_size']}",
            "overlap": cfg.get("overlap", 0),
            "metadata": "document_id, source, page, section, page_id, language",
            "filter": "section (chỉ khi câu hỏi có filter)" if cfg["use_filter"] else "không",
            "vectorizer": f"{MODEL_NAME} (local, 384 chiều, cosine, chi phí 0)",
            "hypothesis": HYPOTHESIS[name],
            "dev_hit1": dev.get(name, {}).get("hit_at_1", ""), "dev_hit3": dev.get(name, {}).get("hit_at_3", ""),
            "test_hit1": test.get(name, {}).get("hit_at_1", ""), "test_hit3": test.get(name, {}).get("hit_at_3", ""),
            "notes": f"{index['chunks']} chunk, độ dài TB {index['len_mean']} ký tự"
                     + ("; ĐƯỢC CHỌN theo tiêu chí định trước (Hit@3 dev cao nhất)" if name == "C" else ""),
        })
    path = ROOT.parent / "artifacts" / "experiment_log.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Đã ghi {path.relative_to(ROOT.parent)}" + ("" if test else " (cột test còn trống - sẽ điền sau khi chạy test)"))


if __name__ == "__main__":
    main()
