"""Điền nhãn chấm tay vào 3 bảng audit và tính điểm tổng hợp. Chạy từ starter/:  python -m src.apply_labels

Nhãn coherence/grounding do Claude (AI) đề xuất, tác giả đọc lại và đồng ý (ghi ở cột labeled_by).
Nhãn metadata theo quy tắc kiểm tra tự động ghi trong cột note.
"""
import csv
import json
from pathlib import Path

from .run import RESULTS

AUDIT = RESULTS / "audit"
LABELER = "Claude (AI) đề xuất; tác giả Trương Thị Thu Hà đã đọc lại và đồng ý"

COHERENCE = {  # (position_id, strategy A/B): (điểm 0-2, lý do)
    ("pos013", "A"): (1, "Phần giữa là câu trọn về xu hướng công nghệ; đầu cắt giữa câu, cuối cắt giữa từ 'vulnera'"),
    ("pos013", "B"): (2, "Trọn các câu về xu hướng toàn cầu/quốc gia, kết thúc đúng cuối câu"),
    ("pos014", "A"): (1, "Bắt đầu giữa từ 'f programs.', kết thúc giữa câu 'emergence of'; ý chính về cải cách vẫn hiểu"),
    ("pos014", "B"): (2, "Trọn đoạn về cải cách và chiến lược 2021–2030, tự hiểu được"),
    ("pos015", "A"): (1, "Câu đầu mất chủ ngữ ('nrolments...'); câu 4,5→2,2 triệu còn trọn; cuối cắt 'is below'"),
    ("pos015", "B"): (2, "Trọn đoạn về mở rộng rồi chững lại của tuyển sinh, đủ chủ thể và số liệu"),
    ("pos016", "A"): (0, "Chỉ là chú thích hình, bắt đầu giữa từ 'ucation', kết thúc 'Refer'; không rõ hình nào"),
    ("pos016", "B"): (1, "Chú thích + ghi chú hình đầy đủ nhưng thiếu chính hình; dính tiêu đề mục sau 'Quality and Relevance'"),
    ("pos017", "A"): (1, "Đầu cắt giữa từ 'novative', cuối cắt 'Malaysi'; phần giữa về nghiên cứu vẫn hiểu"),
    ("pos017", "B"): (2, "Một câu trọn ý về thiếu hạ tầng ICT; chỉ dư tiêu đề mục sau ở cuối"),
    ("pos018", "A"): (1, "Đầu cắt 'overnance', cuối cắt giữa câu 'limit'; ý phân mảnh quản lý vẫn hiểu"),
    ("pos018", "B"): (2, "Trọn đoạn về quản trị phân mảnh, kết thúc đúng cuối câu"),
    ("pos019", "A"): (1, "Đầu cắt 'tween 2004', cuối cắt 'wh'; câu số liệu 0,33% GDP còn trọn"),
    ("pos019", "B"): (1, "Câu đầu 'this concept' không rõ chỉ cái gì (đuôi mục trước); phần sau về tài chính rõ"),
    ("pos020", "A"): (1, "Câu đầu mất chủ ngữ ('ulated a mechanism'), 'such a policy' thiếu ngữ cảnh; cuối cắt giữa câu"),
    ("pos020", "B"): (1, "Bắt đầu bằng ghi chú của hình ES.3 tách khỏi hình; 'For instance' thiếu ý phía trước"),
    ("pos021", "A"): (1, "Đầu cắt 'ry school graduates', cuối cắt ngay trước con số mục tiêu 2030"),
    ("pos021", "B"): (2, "Trọn đoạn về đa dạng hóa cơ sở để mở rộng tiếp cận, tự hiểu được"),
    ("pos022", "A"): (1, "Đầu là mảnh câu 'experienced researchers.', cuối cắt 'the Governm'"),
    ("pos022", "B"): (2, "Trọn các câu về chiến lược ICT và điều kiện tự chủ, tự hiểu được"),
}

GROUNDING = {  # (question_id, strategy): (điểm 0-2, lý do)
    ("q16", "A"): (2, "Chunk [2] tr.31 có trọn câu 'About 93 percent ... economically secure'"),
    ("q16", "B"): (2, "Chunk [1] tr.31 có trọn câu 93% kèm ngữ cảnh so sánh 70% toàn quốc"),
    ("q16", "C"): (2, "Giống B (không có filter): chunk [1] tr.31 đủ trả lời"),
    ("q17", "A"): (2, "Chunk [2] tr.50 có câu 'Vietnam is at the bottom of the list' theo H-indicator"),
    ("q17", "B"): (2, "Chunk [2] tr.17 có câu theo H-index Vietnam xếp dưới tất cả; [1] tr.50 bị cắt trước câu chính"),
    ("q17", "C"): (2, "Giống B (không có filter): chunk [2] tr.17 đủ trả lời"),
    ("q18", "A"): (2, "Chunk [1] tr.26 (Executive Summary) có trọn mục 36: từ 0,23% lên ít nhất 0,8% GDP vào 2030"),
    ("q18", "B"): (2, "Chunk [2] tr.23 (Executive Summary) có số 0,23% → ít nhất 0,8% GDP vào 2030; câu bị cắt phần đầu nhưng đủ số liệu"),
    ("q18", "C"): (2, "Lọc executive_summary: chunk [1] tr.23 đủ số liệu; cả 3 chunk đều thuộc đúng phần được hỏi"),
    ("q19", "A"): (2, "Chunk [1] tr.20 có trọn câu SLP do VSPB quản lý là hỗ trợ duy nhất ở cấp hệ thống"),
    ("q19", "B"): (2, "Chunk [1] tr.64 có trọn câu SLP/VSPB 'only form of student aid'"),
    ("q19", "C"): (2, "Giống B (không có filter): chunk [1] tr.64 đủ trả lời"),
    ("q20", "A"): (1, "Bằng chứng 34 điểm % bị cắt đôi giữa chunk [1] và [2]; phải ghép lại mới đủ, [2] mất chữ 'ethnic'"),
    ("q20", "B"): (2, "Chunk [1] tr.16 có trọn câu: thanh niên DTTS ít hơn 34 điểm % so với nhóm đa số"),
    ("q20", "C"): (2, "Giống B (không có filter): chunk [1] tr.16 đủ trả lời"),
}

SECTION_PAGES = {"executive_summary": range(13, 30), "introduction": range(31, 36),
                 "diagnosis": range(37, 65), "policy_options": range(65, 97)}


def _read(name: str) -> list[dict]:
    with (AUDIT / name).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write(name: str, rows: list[dict]) -> None:
    with (AUDIT / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    summary: dict = {"labeled_by": LABELER, "coherence": {}, "metadata": {}, "grounding": {}}

    rows = _read("audit_coherence.csv")
    for r in rows:
        r["score_0_2"], r["reason"] = COHERENCE[(r["position_id"], r["strategy"][0])]
        r["labeled_by"] = LABELER
    _write("audit_coherence.csv", rows)
    for s in ("A", "B"):
        scores = [r["score_0_2"] for r in rows if r["strategy"][0] == s]
        summary["coherence"][s] = {"n": len(scores), "sum": sum(scores), "mean_of_2": round(sum(scores) / len(scores), 2)}
    summary["coherence"]["C"] = dict(summary["coherence"]["B"], note="C dùng chung chunk với B")

    rows = _read("audit_metadata.csv")
    for r in rows:
        page = int(r["page"])
        r["source_ok_Y_N"] = "Y" if r["source"] == "data/he2020.pdf" else "N"
        r["page_ok_Y_N"] = "Y" if r["auto_text_found_on_page"] == "yes" else "N"
        r["section_ok_Y_N"] = "Y" if page in SECTION_PAGES.get(r["section"], range(0)) else "N"
        r["note"] = ("Kiểm tra tự động: source đúng file; page_ok = text của chunk có trong text trang PDF đó; "
                     "section_ok = số trang nằm trong khoảng trang của section (manifest)")
    _write("audit_metadata.csv", rows)
    for s in ("A", "B", "C"):
        group = [r for r in rows if r["strategy"] == s]
        ok = sum(all(r[k] == "Y" for k in ("source_ok_Y_N", "page_ok_Y_N", "section_ok_Y_N")) for r in group)
        filtered = {r["question_id"] for r in group if r["filter_applied"] != "{}"}
        respected = sum(all(json.loads(r["filter_applied"]).get("section") == r["section"]
                            for r in group if r["question_id"] == q) for q in filtered)
        summary["metadata"][s] = {"records_ok": f"{ok}/{len(group)}",
                                  "filter_compliance": f"{respected}/{len(filtered)}" if filtered else "N/A"}

    rows = _read("audit_grounding.csv")
    for r in rows:
        r["score_0_2"], r["reason"] = GROUNDING[(r["question_id"], r["strategy"])]
        r["labeled_by"] = LABELER
    _write("audit_grounding.csv", rows)
    for s in ("A", "B", "C"):
        scores = [r["score_0_2"] for r in rows if r["strategy"] == s]
        summary["grounding"][s] = {"n": len(scores), "count_0": scores.count(0), "count_1": scores.count(1),
                                   "count_2": scores.count(2), "mean_of_2": round(sum(scores) / len(scores), 2)}

    Path(AUDIT / "audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Cấu hình | Coherence (TB/2) | Metadata đúng | Filter | Grounding (TB/2; số câu 0/1/2)")
    for s in ("A", "B", "C"):
        c, m, g = summary["coherence"][s], summary["metadata"][s], summary["grounding"][s]
        print(f"   {s}     |      {c['mean_of_2']:<10} |    {m['records_ok']:<8}  | {m['filter_compliance']:<6} | "
              f"{g['mean_of_2']} ; {g['count_0']}/{g['count_1']}/{g['count_2']}")
    print("Đã điền nhãn vào results/audit/*.csv và ghi results/audit/audit_summary.json")


if __name__ == "__main__":
    main()
