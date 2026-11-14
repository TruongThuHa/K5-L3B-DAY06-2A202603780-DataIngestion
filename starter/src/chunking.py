"""Hai cách chia chunk: A = cố định theo số ký tự, B = theo đoạn văn (giới hạn kích thước)."""
import re

from .models import Chunk, DocumentPage

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"(])")


def _make(page: DocumentPage, strategy: str, index: int, text: str, start: int | None = None) -> Chunk:
    meta = dict(page.metadata)
    meta.update({"strategy": strategy, "chunk_index": index})
    if start is not None:
        meta["char_start"] = start
    return Chunk(chunk_id=f"{page.document_id}-p{page.page:03d}-{strategy}{index:02d}",
                 document_id=page.document_id, source=page.source, page=page.page,
                 text=text.strip(), metadata=meta)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Cấu hình A: cắt mỗi `size` ký tự, chồng lấn `overlap` ký tự, không quan tâm câu/đoạn."""
    if not 0 <= overlap < size:
        raise ValueError("overlap phải >= 0 và nhỏ hơn size")
    text = page.text.replace("\n", " ")
    step = size - overlap
    chunks, start, index = [], 0, 0
    while start < len(text):
        chunks.append(_make(page, "A", index, text[start:start + size], start))
        if start + size >= len(text):
            break
        start += step
        index += 1
    return chunks


def _paragraphs(text: str) -> list[str]:
    """Đoán ranh giới đoạn từ các dòng PDF: dòng trước kết thúc câu + dòng sau viết hoa, hoặc dòng ngắn là tiêu đề."""
    paras: list[list[str]] = [[]]
    lines = [line for line in text.split("\n") if line]
    for i, line in enumerate(lines):
        prev = lines[i - 1] if i else ""
        is_heading = len(line) < 60 and not line.endswith((".", ",", ";"))
        new_para = (not prev or prev.endswith((".", "!", "?", ":")) and line[:1].isupper()
                    or is_heading or (len(prev) < 60 and not prev.endswith((".", ",", ";"))))
        if new_para and paras[-1]:
            paras.append([])
        paras[-1].append(line)
    return [" ".join(p) for p in paras if p]


def _split_long(paragraph: str, max_size: int) -> list[str]:
    """Đoạn quá dài: tách theo câu; câu quá dài mới cắt cứng."""
    pieces: list[str] = []
    for sentence in SENTENCE_END.split(paragraph):
        while len(sentence) > max_size:
            pieces.append(sentence[:max_size])
            sentence = sentence[max_size:]
        pieces.append(sentence)
    return pieces


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Cấu hình B: gom các đoạn liền nhau đến tối đa `max_size` ký tự, không cắt giữa câu."""
    units: list[str] = []
    for para in _paragraphs(page.text):
        units.extend([para] if len(para) <= max_size else _split_long(para, max_size))
    chunks, current, index = [], "", 0
    for unit in units:
        if current and len(current) + 1 + len(unit) > max_size:
            chunks.append(_make(page, "B", index, current))
            index += 1
            current = unit
        else:
            current = f"{current}\n{unit}" if current else unit
    if current:
        chunks.append(_make(page, "B", index, current))
    return chunks
