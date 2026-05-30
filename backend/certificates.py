from __future__ import annotations

import re
from datetime import datetime

from .schemas import QuizAttemptOut, QuizRunOut


PDF_MIME_TYPE = "application/pdf"


def build_certificate_pdf(quiz: QuizRunOut, attempt: QuizAttemptOut) -> bytes:
    lines = [
        ("Books Czar", 30, 72, 720),
        ("Certificate of Completion", 24, 72, 674),
        ("This certifies that", 13, 72, 620),
        (attempt.learner_name, 22, 72, 590),
        ("successfully completed the mastery knowledge check", 13, 72, 548),
        (quiz.title, 18, 72, 520),
        (f"Score: {attempt.score:.1f}% | Passing score: {quiz.passing_score:.0f}%", 13, 72, 474),
        (f"Scoped books: {len(quiz.book_ids)} | Questions: {quiz.question_count}", 13, 72, 448),
        (f"Completed: {_format_date(attempt.created_at)}", 13, 72, 422),
        (f"Certificate ID: {attempt.id}", 10, 72, 120),
    ]
    stream = ["BT", "/F1 12 Tf"]
    for text, size, x, y in lines:
        stream.append(f"/F1 {size} Tf")
        stream.append(f"{x} {y} Td ({_escape_pdf_text(text)}) Tj")
        stream.append(f"{-x} {-y} Td")
    stream.append("ET")
    content = "\n".join(stream).encode("utf-8")
    return _assemble_pdf(content)


def certificate_filename(learner_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", learner_name.strip()).strip(".-").lower()
    return f"books-czar-certificate-{(slug or 'completion')[:80]}.pdf"


def _format_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def _assemble_pdf(content: bytes) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_at = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _escape_pdf_text(value: str) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    return clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
