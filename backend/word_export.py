from __future__ import annotations

import re
from datetime import UTC, datetime
from html import escape
from io import BytesIO
from typing import TypedDict
from zipfile import ZIP_DEFLATED, ZipFile

from .schemas import SynthesisRunOut


WORD_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


AUDIENCE_LABELS = {
    "board": "Board",
    "c_suite": "C-Suite",
    "cdao_leadership": "CDAO Leadership",
    "technical_leaders": "Technical Leaders",
}

LENS_LABELS = {
    "all": "All",
    "strategy": "Strategy",
    "risk_governance": "Risk/Governance",
    "operating_model": "Operating Model",
    "investment": "Investment",
    "talent_change": "Talent/Change",
}

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


class MarkdownSection(TypedDict):
    title: str
    lines: list[str]


def build_synthesis_docx(run: SynthesisRunOut) -> bytes:
    title, sections = _parse_markdown(run.markdown)
    document_title = run.title.strip() or title
    paragraphs = [
        _paragraph("Books Czar Board Brief", style="Title"),
        _paragraph(document_title, style="Subtitle"),
        _paragraph(_metadata_line(run), style="Meta"),
        _paragraph(f"Objective: {run.objective.strip()}", style="Meta"),
    ]

    for section in sections:
        paragraphs.append(_paragraph(section["title"], style="Heading1"))
        for line in _presentable_lines(section["lines"]):
            style = "Callout" if section["title"] == "Executive Takeaway" else "Bullet"
            text = line if style == "Callout" else f"• {line}"
            paragraphs.append(_paragraph(text, style=style))

    if run.sources:
        paragraphs.append(_paragraph("Source Evidence", style="Heading1"))
        for index, source in enumerate(run.sources, start=1):
            paragraphs.append(_paragraph(f"[S{index}] {source.title}", style="Heading2"))
            location = source.location or "Unknown location"
            paragraphs.append(_paragraph(f"{location} | Score: {source.score:.2f}", style="Meta"))
            paragraphs.append(_paragraph(source.excerpt, style="Normal"))

    document_xml = _document_xml("\n".join(paragraphs))
    generated_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        docx.writestr("_rels/.rels", ROOT_RELS_XML)
        docx.writestr("docProps/app.xml", APP_PROPS_XML)
        docx.writestr("docProps/core.xml", _core_props_xml(document_title, generated_at))
        docx.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS_XML)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", STYLES_XML)
    return buffer.getvalue()


def word_filename(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title.strip()).strip(".-").lower()
    return f"books-czar-{(slug or 'board-brief')[:80]}.docx"


def _metadata_line(run: SynthesisRunOut) -> str:
    audience = AUDIENCE_LABELS.get(run.audience, run.audience)
    lens = LENS_LABELS.get(run.lens, run.lens)
    created = _format_export_date(run.created_at)
    source_label = "source" if len(run.sources) == 1 else "sources"
    return f"Audience: {audience} | Lens: {lens} | Sources: {len(run.sources)} {source_label} | Generated: {created}"


def _format_export_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    hour = parsed.strftime("%I").lstrip("0") or "0"
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year} at {hour}:{parsed.strftime('%M %p')}"


def _parse_markdown(markdown: str) -> tuple[str, list[MarkdownSection]]:
    title = "Synthesis Brief"
    sections: list[MarkdownSection] = []
    current: MarkdownSection | None = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading = HEADING_RE.match(line)
        if heading:
            heading_text = _clean_markdown(heading.group(2))
            if line.startswith("# ") and title == "Synthesis Brief":
                title = heading_text
                current = None
                continue
            current = {"title": heading_text, "lines": []}
            sections.append(current)
            continue
        if current is None and line:
            current = {"title": "Summary", "lines": []}
            sections.append(current)
        if current is not None:
            current["lines"].append(line)

    return title, sections


def _presentable_lines(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        text = _clean_markdown(re.sub(r"^[-*+]\s+", "", line))
        if text:
            cleaned.append(text)
    return cleaned


def _clean_markdown(value: str) -> str:
    value = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    return value.strip()


def _paragraph(text: str, *, style: str = "Normal") -> str:
    return (
        f"<w:p><w:pPr><w:pStyle w:val=\"{escape(style)}\"/></w:pPr>"
        f"<w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def _document_xml(paragraphs: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{paragraphs}"
        "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        "<w:pgMar w:top=\"1080\" w:right=\"1080\" w:bottom=\"1080\" w:left=\"1080\" "
        "w:header=\"720\" w:footer=\"720\" w:gutter=\"0\"/></w:sectPr>"
        "</w:body></w:document>"
    )


def _core_props_xml(title: str, generated_at: str) -> str:
    escaped_title = escape(title)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escaped_title}</dc:title>"
        "<dc:creator>Books Czar</dc:creator>"
        "<cp:lastModifiedBy>Books Czar</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{generated_at}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{generated_at}</dcterms:modified>'
        "</cp:coreProperties>"
    )


CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

ROOT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOCUMENT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

APP_PROPS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Books Czar</Application>
</Properties>"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="140" w:line="276" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:color w:val="1F3F38"/><w:sz w:val="34"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:after="260"/></w:pPr>
    <w:rPr><w:color w:val="3F423C"/><w:sz w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="260" w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:color w:val="181A17"/><w:sz w:val="25"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="140" w:after="80"/></w:pPr>
    <w:rPr><w:b/><w:color w:val="315B52"/><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Meta">
    <w:name w:val="Meta"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:after="80"/></w:pPr>
    <w:rPr><w:color w:val="716D63"/><w:sz w:val="18"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Callout">
    <w:name w:val="Callout"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:shd w:val="clear" w:color="auto" w:fill="EDF7EE"/><w:spacing w:after="180"/></w:pPr>
    <w:rPr><w:color w:val="233E35"/><w:sz w:val="23"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Bullet">
    <w:name w:val="Bullet"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="360" w:hanging="180"/><w:spacing w:after="110"/></w:pPr>
    <w:rPr><w:color w:val="3F423C"/><w:sz w:val="21"/></w:rPr>
  </w:style>
</w:styles>"""
