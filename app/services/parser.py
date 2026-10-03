"""AST & Structural Document Parser for Enterprise Formats (Markdown, DOCX, PDF, Plaintext)."""

import io
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import docx
import pypdf


@dataclass
class DocumentSection:
    """Represents a structurally parsed section within a document."""

    title: str
    header_path: List[str]
    content: str
    section_header: str
    doc_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert section to dictionary representation."""
        return {
            "title": self.title,
            "header_path": self.header_path,
            "content": self.content,
            "section_header": self.section_header,
            "doc_id": self.doc_id,
            "metadata": self.metadata,
        }


class DocumentParser:
    """Multi-format enterprise document parser respecting headings, hierarchy, and tables."""

    @classmethod
    def parse_markdown(
        cls, text: str, doc_id: str, base_metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentSection]:
        """Parse Markdown text into hierarchical sections based on #, ##, ### headers."""
        meta = base_metadata.copy() if base_metadata else {}
        lines = text.splitlines()
        sections: List[DocumentSection] = []

        current_headers: Dict[int, str] = {}
        current_content_lines: List[str] = []
        current_title = meta.get("title", doc_id)
        current_section_header = "Introduction"

        def flush_section():
            nonlocal current_content_lines, current_section_header, current_headers
            content = "\n".join(current_content_lines).strip()
            if content:
                # Build header path ordered by heading level
                sorted_levels = sorted(current_headers.keys())
                header_path = [current_headers[lvl] for lvl in sorted_levels]
                section_hdr = (
                    " > ".join(header_path) if header_path else "Document Body"
                )
                sections.append(
                    DocumentSection(
                        title=current_title,
                        header_path=header_path,
                        content=content,
                        section_header=section_hdr,
                        doc_id=doc_id,
                        metadata=meta,
                    )
                )
            current_content_lines = []

        heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

        for line in lines:
            match = heading_pattern.match(line)
            if match:
                flush_section()
                level = len(match.group(1))
                heading_text = match.group(2).strip()

                # Remove deeper headers when moving up or across hierarchy
                current_headers = {
                    lvl: txt for lvl, txt in current_headers.items() if lvl < level
                }
                current_headers[level] = heading_text
                current_section_header = heading_text
            else:
                current_content_lines.append(line)

        flush_section()

        # If no sections were produced, wrap entire content
        if not sections and text.strip():
            sections.append(
                DocumentSection(
                    title=current_title,
                    header_path=[],
                    content=text.strip(),
                    section_header="Document Body",
                    doc_id=doc_id,
                    metadata=meta,
                )
            )

        return sections

    @classmethod
    def parse_docx(
        cls,
        file_input: Any,
        doc_id: str,
        base_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentSection]:
        """Parse Microsoft Word (.docx) document into sections based on Heading styles."""
        meta = base_metadata.copy() if base_metadata else {}
        doc = (
            docx.Document(file_input)
            if not isinstance(file_input, (str, Path))
            else docx.Document(str(file_input))
        )

        sections: List[DocumentSection] = []
        current_headers: Dict[int, str] = {}
        current_content_lines: List[str] = []
        current_title = meta.get("title", doc_id)
        current_section_header = "Introduction"

        def flush_section():
            nonlocal current_content_lines, current_headers, current_section_header
            content = "\n".join(current_content_lines).strip()
            if content:
                sorted_levels = sorted(current_headers.keys())
                header_path = [current_headers[lvl] for lvl in sorted_levels]
                section_hdr = (
                    " > ".join(header_path) if header_path else "Document Body"
                )
                sections.append(
                    DocumentSection(
                        title=current_title,
                        header_path=header_path,
                        content=content,
                        section_header=section_hdr,
                        doc_id=doc_id,
                        metadata=meta,
                    )
                )
            current_content_lines = []

        heading_re = re.compile(r"^Heading\s*(\d+)$", re.IGNORECASE)

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            style_name = paragraph.style.name if paragraph.style else ""
            match = heading_re.match(style_name)

            if match:
                flush_section()
                level = int(match.group(1))
                current_headers = {
                    lvl: txt for lvl, txt in current_headers.items() if lvl < level
                }
                current_headers[level] = text
                current_section_header = text
            else:
                current_content_lines.append(text)

        # Also extract structured table text if present
        for table in doc.tables:
            table_lines = []
            for row in table.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_lines.append(" | ".join(cells))
            if table_lines:
                current_content_lines.append("\n" + "\n".join(table_lines) + "\n")

        flush_section()

        if not sections:
            # Fallback to plain text extract
            full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            if full_text.strip():
                sections.append(
                    DocumentSection(
                        title=current_title,
                        header_path=[],
                        content=full_text.strip(),
                        section_header="Document Body",
                        doc_id=doc_id,
                        metadata=meta,
                    )
                )

        return sections

    @classmethod
    def parse_pdf(
        cls,
        file_input: Any,
        doc_id: str,
        base_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentSection]:
        """Parse PDF document extracting text per page and section headers."""
        meta = base_metadata.copy() if base_metadata else {}
        reader = (
            pypdf.PdfReader(file_input)
            if not isinstance(file_input, (str, Path))
            else pypdf.PdfReader(str(file_input))
        )

        sections: List[DocumentSection] = []
        current_title = meta.get("title", doc_id)

        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text or not text.strip():
                continue

            page_meta = meta.copy()
            page_meta["page_number"] = page_idx
            section_header = f"Page {page_idx}"

            # Check if first line looks like a title
            first_line = text.strip().splitlines()[0]
            if len(first_line) < 80 and not first_line.endswith("."):
                section_header = f"Page {page_idx}: {first_line.strip()}"

            sections.append(
                DocumentSection(
                    title=current_title,
                    header_path=[f"Page {page_idx}"],
                    content=text.strip(),
                    section_header=section_header,
                    doc_id=doc_id,
                    metadata=page_meta,
                )
            )

        return sections

    @classmethod
    def parse_file(
        cls,
        file_path_or_bytes: Any,
        filename: str,
        doc_id: str,
        base_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[DocumentSection]:
        """Unified entrypoint: auto-detects document format by file extension or content."""
        ext = os.path.splitext(filename)[1].lower()

        if ext in [".md", ".markdown", ".txt"]:
            if isinstance(file_path_or_bytes, (str, Path)):
                content = Path(file_path_or_bytes).read_text(
                    encoding="utf-8", errors="replace"
                )
            elif isinstance(file_path_or_bytes, bytes):
                content = file_path_or_bytes.decode("utf-8", errors="replace")
            else:
                content = file_path_or_bytes.read().decode("utf-8", errors="replace")
            return cls.parse_markdown(content, doc_id, base_metadata)

        elif ext in [".docx"]:
            if isinstance(file_path_or_bytes, bytes):
                file_input = io.BytesIO(file_path_or_bytes)
            else:
                file_input = file_path_or_bytes
            return cls.parse_docx(file_input, doc_id, base_metadata)

        elif ext in [".pdf"]:
            if isinstance(file_path_or_bytes, bytes):
                file_input = io.BytesIO(file_path_or_bytes)
            else:
                file_input = file_path_or_bytes
            return cls.parse_pdf(file_input, doc_id, base_metadata)

        else:
            # Fallback to plain text
            if isinstance(file_path_or_bytes, (str, Path)):
                content = Path(file_path_or_bytes).read_text(
                    encoding="utf-8", errors="replace"
                )
            elif isinstance(file_path_or_bytes, bytes):
                content = file_path_or_bytes.decode("utf-8", errors="replace")
            else:
                content = file_path_or_bytes.read().decode("utf-8", errors="replace")
            return cls.parse_markdown(content, doc_id, base_metadata)
