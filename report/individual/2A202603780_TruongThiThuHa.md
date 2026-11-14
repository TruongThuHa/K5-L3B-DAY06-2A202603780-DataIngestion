# Báo cáo cá nhân — Day 6

Học viên: Trương Thị Thu Hà · MSSV 2A202603780 · Lớp L3B

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Báo cáo World Bank (2020) *Improving the Performance of Higher Education in Vietnam: Strategic Priorities and Policy Options* (`he2020`, https://hdl.handle.net/10986/33681), giấy phép **CC BY 3.0 IGO** (ghi trên trang hồ sơ Open Knowledge Repository), truy cập 2026-11-14, SHA-256 của file ghi trong manifest. PDF có 102 trang vật lý; tính **82 trang nội dung**: Executive Summary + Chương 1–3 (PDF tr. 13–96). Loại: bìa, bản quyền, mục lục, viết tắt, lời cảm ơn (tr. 1–12), trang trắng (tr. 30, 36), tài liệu tham khảo và bìa sau (tr. 97–102). Chi tiết từng trang (page_id, section, số ký tự) trong `starter/data/manifest.json`.
- **Chuẩn hóa, lỗi và giới hạn:** đọc bằng `pypdf` (`extract_text`), chuẩn hóa Unicode NFC, gộp khoảng trắng trong dòng, giữ xuống dòng để nhận đoạn. Kết quả: 82/82 trang đọc được, 0 trang rỗng, 0 lỗi; 20 trang bị loại theo quy tắc (`results/ingest_page_log.json`). Giới hạn: pypdf cảnh báo thiếu `fontTools` khi đọc font trang trí (chữ vẫn đọc đúng, kiểm chứng bằng `python -m src.run check`: 20/20 evidence khớp); bảng/hình bị trích thành chuỗi số rời; dòng tiêu đề chạy (running header) và số trang lẫn vào text; không cần OCR.
- **Embedding, vector store, metric, lệnh chạy, chi phí:** `BAAI/bge-small-en-v1.5` chạy local qua `sentence-transformers==6.3.0`, 384 chiều, vector chuẩn hóa; query thêm tiền tố khuyến nghị của BGE ("Represent this sentence for searching relevant passages: "), document không thêm. Vector store: PostgreSQL 16.16 + pgvector 0.8.7 (Docker, `starter/docker-compose.yml`), khoảng cách **cosine**, **exact search** (không tạo index ANN). Lệnh: `python -m src.run ingest` / `evaluate --split dev|test`. Chi phí: **0 USD** (không dùng API). Phiên bản thư viện: `starter/results/pip_freeze.txt`.
- **Metadata:** bắt buộc `document_id`, `source`, `page` (số trang PDF); bổ sung `section` (4 giá trị: `executive_summary`, `introduction`, `diagnosis`, `policy_options`), `page_id`, `language`, `chunk_index`. Giá trị `section` lấy từ tiêu đề chương in trong PDF và khoảng trang ghi trong manifest (không đoán). Chọn `section` vì Executive Summary lặp lại số liệu của các chương, nên khi người dùng chỉ định phần cần tra, lọc theo `section` giúp loại các đoạn trùng ý ở phần khác.

## Cấu hình và benchmark
- **A / B / C:** A = cắt cố định 500 ký tự, chồng lấn 50, không lọc. B = theo đoạn/câu (đoán ranh giới đoạn từ dòng PDF, đoạn dài tách theo câu), tối đa 800 ký tự, không lọc. C = **dùng chung chunk và vector của B**, chỉ thêm lọc SQL `section = <giá trị>` khi câu hỏi có `filter`; câu không có filter thì C chạy không lọc. Khác biệt duy nhất B–C là bộ lọc. Cùng corpus, model, store, metric và top-3 cho cả ba (`artifacts/experiment_log.csv`).
- **Benchmark:** 20 câu (`benchmark/questions.json`): 15 dev / 5 test, chia theo trang nguồn trước khi chạy thử (commit `Add corpus manifest and benchmark (dev/test split before experiments)`). Loại câu: direct, paraphrase, conditional/ngoại lệ, filter. 3 câu filter: q12, q13 (dev), q18 (test). Mỗi câu có đáp án, trang gold, evidence nguyên văn và các trang gold thay thế (khi nhiều trang hợp lệ). Kiểm chứng: tự động (mọi evidence nằm nguyên văn trong text trang sau chuẩn hóa) + đối chiếu thủ công 5 câu test với PDF bằng Cmd+F.
- **Tiêu chí chọn chiến lược (chốt trước test, ghi trong `benchmark/README.md`):** (1) Evidence Hit@3 trên dev cao nhất; (2) nếu hòa: Hit@1 dev; (3) grounding, rồi tài nguyên. Quyết định chọn C được commit trước khi chạy test (commit `Choose config C on dev ... before running test`); test chạy đúng một lần.

## Kết quả
| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 8/15 | 11/15 | 585 | embed+lưu 2,41 s | 0 |
| B | dev | 9/15 | 11/15 | 416 | embed+lưu 5,99 s | 0 |
| C | dev | 9/15 | **12/15** | 416 (dùng chung B) | như B | 0 |
| A | test | 2/5 | 4/5 | 585 | — | 0 |
| B | test | 4/5 | 5/5 | 416 | — | 0 |
| C | test | **5/5** | **5/5** | 416 | — | 0 |

Độ dài chunk (ký tự): A tối thiểu 52, trung vị 500, trung bình 469,4, tối đa 500 (tổng 274.610, gồm phần chồng lấn); B tối thiểu 22, trung vị 645, trung bình 599,2, tối đa 800 (tổng 249.267). Thời gian đo một lần trên MacBook Air (lần ingest thứ 2, model đã có sẵn), xem `starter/results/ingest_stats.json`. Nạp lại lần 2: A 585 → 585 dòng, B 416 → 416 dòng (không nhân đôi; chunk_id ổn định + upsert + xóa chunk cũ).

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,9 (10) | 15/15 | N/A | 0/1/4 · 1,8 |
| B | 1,7 (10) | 15/15 | N/A | 0/0/5 · 2,0 |
| C | 1,7 (10, cùng chunk B) | 15/15 | 1/1 (test); 2/2 (dev) | 0/0/5 · 2,0 |

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:** trace top-3 đầy đủ (câu hỏi, chunk_id, text, score, metadata, nhãn tự động) ở `starter/results/traces_dev.jsonl`, `traces_test.jsonl`; bảng tổng hợp `summary_dev.csv`, `summary_test.csv`; nhãn ở `starter/results/audit/` (`audit_coherence.csv`, `audit_metadata.csv`, `audit_grounding.csv`, `audit_summary.json`). Coherence: 10 vị trí chọn trước khi xem điểm = điểm giữa text của 10 trang nội dung đầu (tr. 13–22), chấm chunk chứa vị trí đó cho A và B. Metadata và grounding: 5 câu test × top-3 cho từng cấu hình. **Phương pháp chấm:** nhãn coherence và grounding do Claude (AI) đề xuất theo thang 0–2 của GUIDE, tác giả đọc lại từng nhãn và đồng ý; metadata kiểm bằng quy tắc tự động (source đúng file; text của chunk có trong text trang đó; số trang nằm trong khoảng trang của section). Nguy cơ thiên lệch: người chấm cũng là người làm bài, không có người chấm độc lập thứ hai.

## Phân tích và kết luận
- **A–B (đổi cách chia chunk):** Hit@3 dev bằng nhau (11/15), test B tốt hơn (5/5 so với 4/5); Hit@1 B cao hơn ở cả dev (9 so với 8) và test (4 so với 2). B có ít chunk hơn (416 so với 585), ít trường hợp "đúng trang nhưng evidence bị cắt" hơn (dev 2 so với 3; test 0 so với 1) và coherence cao hơn rõ (1,7 so với 0,9). Ngược lại, A thắng ở q03 (paraphrase, gold tr. 15): chunk ngắn của A khớp đúng câu về tỷ lệ giảng viên có bằng thạc sĩ/tiến sĩ, còn B/C trả về tr. 48, 52. Lưu ý: A–B đổi cả phương pháp lẫn kích thước (500 so với tối đa 800) nên không tách được riêng ảnh hưởng của từng yếu tố.
- **B–C (chỉ thêm lọc `section`):** C hơn B 1 câu Hit@3 trên dev (q13) và 1 câu Hit@1 trên test (q18); cả 3 câu filter đều tuân thủ lọc. Không có câu nào C làm xấu hơn B.
- **Ví dụ 1 – q13 (dev, filter `diagnosis`, gold tr. 59):** B trả về tr. 20, 19 (Executive Summary nhắc lại cùng số liệu US$316) và một chunk tr. 59 nhưng câu evidence bị cắt → miss. C lọc `diagnosis` nên cả top-3 ở tr. 59 và có chunk chứa đủ evidence → hit. Đây là đúng trường hợp `section` được thiết kế để xử lý.
- **Ví dụ 2 – q20 (test, gold tr. 16):** A cắt câu "youth from ethnic minority communities are 34 percentages points less likely…" ra hai chunk liền nhau (chunk 1 dừng ở "le", chunk 2 mất chữ "ethnic") → Evidence Hit@3 = 0 và grounding chỉ 1/2. B giữ trọn câu trong một chunk → hit ở hạng 1.
- **Ví dụ 3 – q12 (dev, filter `policy_options`, gold tr. 68):** cả A, B, C đều miss. C đã lọc đúng phần (tr. 67, 67, 65) nhưng không xếp được trang có bảng mô phỏng 3,6 triệu sinh viên lên top-3. Lọc chỉ thu hẹp phạm vi, không sửa được thứ hạng; câu hỏi số liệu nằm trong bảng vẫn khó với embedding.
- **Chiến lược chọn và đánh đổi:** chọn **C** (theo tiêu chí đã chốt: Hit@3 dev cao nhất 12/15). C cần người dùng/ngữ cảnh cung cấp phần cần tra *trước* khi truy xuất; khi không có filter, C hoạt động như B. B/C tốn thời gian embed hơn A ở lần đo này nhưng ít chunk hơn (lưu trữ ít hơn). Áp dụng phù hợp cho tài liệu có cấu trúc chương rõ và tóm tắt lặp lại nội dung.
- **Hạn chế:** chỉ 1 tài liệu, tiếng Anh; test chỉ 5 câu, dev 15 câu: chênh 1 câu = 6,7 điểm % (dev) hoặc 20 điểm % (test), không đủ để kết luận tổng quát. `section` thô (4 giá trị). `page` là số trang PDF, khác số trang in (trang in = trang PDF − 12). Running header lẫn vào chunk. Nhãn coherence/grounding do AI đề xuất và một người duyệt; metadata kiểm tự động. Thời gian đo một lần, trên một máy, có dao động.
- **Nếu làm lại/mở rộng:** bỏ header/số trang và xử lý bảng riêng; thử A với cùng kích thước 800 để tách ảnh hưởng của kích thước; thêm hybrid BM25 cho câu hỏi số liệu (như q12); thêm nhiều câu test và người chấm thứ hai; thử model đa ngữ để hỏi bằng tiếng Việt.

## Sử dụng AI
Dùng Claude (Anthropic) để: giải thích bài lab, chọn và kiểm tra giấy phép tài liệu, soạn manifest và 20 câu hỏi (tác giả đối chiếu 5 câu test với PDF), viết code pipeline trong `starter/src/` (tác giả chạy trên máy mình, kết quả trong `results/` là kết quả chạy thật), đề xuất nhãn audit (tác giả đọc lại) và soạn nháp báo cáo này (tác giả đọc lại và chỉnh). Cách kiểm tra: lệnh `check` (20/20 evidence), ingest 2 lần không nhân đôi, kết quả dev/test lưu trong trace.
