"""Đọc PDF, chuẩn hóa text, giữ số trang và section để truy vết nguồn."""
import json
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode (NFC), gộp khoảng trắng trong từng dòng, giữ xuống dòng để còn nhận ra đoạn văn."""
    text = unicodedata.normalize("NFC", text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):  # bỏ các dòng trống liên tiếp
            out.append(line)
    return "\n".join(out).strip()


def flatten(text: str) -> str:
    """Dạng 'phẳng' (một dòng) để so khớp bằng chứng: NFC + gộp mọi khoảng trắng."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def load_pdf(path: Path, document_id: str, source: str,
             page_meta: dict[int, dict]) -> tuple[list[DocumentPage], list[dict]]:
    """Đọc các trang được tính trong manifest. Trả về (danh sách trang, nhật ký lỗi)."""
    reader = PdfReader(path)
    pages: list[DocumentPage] = []
    log: list[dict] = []
    for number in sorted(page_meta):
        try:
            raw = reader.pages[number - 1].extract_text() or ""
        except Exception as exc:  # ghi lỗi, không bỏ qua âm thầm
            log.append({"document_id": document_id, "page": number, "status": "error", "detail": repr(exc)})
            continue
        text = normalize_text(raw)
        if not text:
            log.append({"document_id": document_id, "page": number, "status": "empty", "detail": "không có chữ (có thể là ảnh scan)"})
            continue
        pages.append(DocumentPage(document_id=document_id, source=source, page=number,
                                  text=text, metadata=dict(page_meta[number])))
    counted = set(page_meta)
    for number in range(1, len(reader.pages) + 1):
        if number not in counted:
            log.append({"document_id": document_id, "page": number, "status": "excluded",
                        "detail": "không tính theo counting_rule trong manifest"})
    return pages, log


def load_corpus(manifest_path: Path) -> tuple[list[DocumentPage], list[dict]]:
    """Đọc mọi tài liệu khai báo trong manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.resolve().parent.parent  # thư mục starter/
    all_pages: list[DocumentPage] = []
    all_log: list[dict] = []
    for src in manifest["sources"]:
        page_meta = {p["pdf_page"]: {"page_id": p["page_id"], "section": p["section"], "language": src.get("language")}
                     for p in src["pages"]}
        path = base / src["local_path"]
        if not path.exists():
            raise FileNotFoundError(f"Không thấy file {path}. Kiểm tra local_path trong manifest.")
        pages, log = load_pdf(path, src["source_id"], src["local_path"], page_meta)
        all_pages.extend(pages)
        all_log.extend(log)
    return all_pages, all_log
