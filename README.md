# Day 06 · Data Ingestion Engineering — Bài nộp của Trương Thị Thu Hà (2A202603780, L3B)

Pipeline biến báo cáo World Bank 2020 về giáo dục đại học Việt Nam (82 trang) thành kho tri thức truy xuất được, rồi so sánh 3 cấu hình chuẩn bị dữ liệu trên 20 câu hỏi có bằng chứng. Đề bài gốc: https://github.com/VinUni-AI20k/K5-L3-Day06-DataIngestionEngineering

- Báo cáo: [report/individual/2A202603780_TruongThiThuHa.md](report/individual/2A202603780_TruongThiThuHa.md)
- Thông tin học viên: [STUDENT.md](STUDENT.md)

## Cấu trúc

~~~text
STUDENT.md
benchmark/questions.json, README.md     # 20 câu (15 dev / 5 test), gold evidence, cách chia, tiêu chí chọn
artifacts/experiment_log.csv            # cấu hình, giả thuyết, kết quả A/B/C
starter/data/he2020.pdf, manifest.json  # corpus (CC BY 3.0 IGO) + manifest trang/quyền/số ký tự
starter/src/                            # code pipeline
starter/results/                        # thống kê ingest, log trang, trace top-3, bảng kết quả, audit
report/individual/2A202603780_TruongThiThuHa.md
~~~

## Cài đặt (macOS, Python 3.13, Docker Desktop)

~~~bash
cd starter
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py        # kỳ vọng: Setup OK
~~~

Embedding: `BAAI/bge-small-en-v1.5` chạy local (tự tải ~130 MB lần đầu, không cần API key, chi phí 0). Vector store: PostgreSQL 16 + pgvector (cosine, exact search).

## Chạy (từ thư mục `starter/`)

~~~bash
python -m src.run check                  # 20/20 evidence có trong text đã chuẩn hóa
python -m src.run ingest                 # đọc, chia chunk A/B, embed, lưu; chạy 2 lần để kiểm tra không nhân đôi
python -m src.run evaluate --split dev   # 15 câu dev cho A, B, C
python -m src.explog                     # ghi artifacts/experiment_log.csv
python -m src.run evaluate --split test  # 5 câu test, chạy 1 lần sau khi đã chốt cấu hình
python -m src.audit                      # tạo bảng chấm tay
python -m src.apply_labels               # điền nhãn đã duyệt + tính điểm audit
~~~

## Kết quả chính

| Cấu hình | Dev Hit@1 | Dev Hit@3 | Test Hit@1 | Test Hit@3 | Coherence /2 | Grounding /2 |
|---|---|---|---|---|---|---|
| A: cố định 500/50 | 8/15 | 11/15 | 2/5 | 4/5 | 0,9 | 1,8 |
| B: theo đoạn ≤800 | 9/15 | 11/15 | 4/5 | 5/5 | 1,7 | 2,0 |
| C: B + lọc `section` (được chọn) | 9/15 | 12/15 | 5/5 | 5/5 | 1,7 | 2,0 |

Test chỉ có 5 câu nên không kết luận tổng quát. Chi tiết và hạn chế xem báo cáo.
