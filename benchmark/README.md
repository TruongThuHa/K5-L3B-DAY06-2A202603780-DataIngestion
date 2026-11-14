# Benchmark — Day 06

Bộ câu hỏi: `questions.json` (20 câu: 15 dev / 5 test). Corpus: `he2020` (World Bank 2020, xem `starter/data/manifest.json`).

## Các trường của mỗi câu

| Trường | Ý nghĩa |
|---|---|
| `id`, `split` | Mã câu; `dev` (dùng để thử và chọn cấu hình) hoặc `test` (chỉ chạy một lần sau khi đã chốt cấu hình) |
| `type` | `direct` (hỏi thẳng), `paraphrase` (diễn đạt lại bằng từ khác), `conditional` (có điều kiện / ngoại lệ), `filter` (cần lọc metadata) |
| `question`, `expected_answer` | Câu hỏi và đáp án mong đợi |
| `gold_source_id`, `gold_page`, `gold_section` | Nguồn, trang PDF và phần chứa bằng chứng chính |
| `evidence_quote` | Đoạn trích nguyên văn làm bằng chứng |
| `filter` | Bộ lọc metadata cấp trước khi truy xuất (chỉ cấu hình C dùng); `null` = không lọc |
| `alternative_gold` | Các trang khác cũng chứa đủ bằng chứng; trúng trang nào trong số này cũng tính là đúng |

## Cách chia dev/test (chốt trước khi chạy thử)

- Chia theo **trang nguồn**: 5 câu test lấy từ các trang không có câu dev nào làm gold chính (tr. 16, 20, 26, 31, 50).
- Có 3 câu lọc metadata: `q12`, `q13` (dev) và `q18` (test).
- Có đủ các loại câu: direct, paraphrase, conditional/ngoại lệ, filter.

**Nguy cơ rò rỉ:** phần Executive Summary tóm tắt lại các chương, nên một số chủ đề của test (ví dụ học bổng/vay vốn, nghiên cứu) cũng xuất hiện trong dev hoặc ở trang khác. Không đổi bộ test sau khi xem kết quả.

## Tiêu chí chọn cấu hình (định nghĩa trước khi xem test)

1. Ưu tiên Evidence Hit@3 trên dev cao nhất.
2. Nếu hòa: Hit@1 trên dev.
3. Nếu vẫn hòa: điểm grounding thủ công, rồi đến tài nguyên (số chunk, thời gian nạp).

## Kiểm chứng bằng chứng

- Đã kiểm tra tự động: mọi `evidence_quote` (kể cả `alternative_gold`) đều nằm nguyên văn trong text của trang tương ứng sau chuẩn hóa (pypdf `extract_text()`, Unicode NFC, gộp khoảng trắng thành một dấu cách).
- Câu `filter`: trang gold đều thuộc đúng `section` của bộ lọc.
- Bộ câu hỏi được soạn với sự hỗ trợ của Claude (AI); học viên đọc lại và đối chiếu từng câu với PDF.

## Trường hợp đặc biệt đã biết

- `q04`: Executive Summary cũng có ý này, nhưng câu bị **cắt qua hai trang 18–19**, nên chỉ tính trang 57.
- `q07`: Trang 15 có số 4,5 → 2,2 triệu nhưng không nêu Decision 37, nên không đủ bằng chứng; chỉ tính trang 38.
- `q12`, `q13`, `q18`: cùng thông tin có ở phần khác (tr. 21, 19, 89), nhưng bị loại vì câu hỏi chỉ định phần cụ thể. Đây chính là chỗ bộ lọc metadata có tác dụng.
- `q20`: trang 39 có số liệu 45% và 11% (chênh lệch 34 điểm); câu "34 percentage points" ở trang 39–40 bị cắt qua trang.
