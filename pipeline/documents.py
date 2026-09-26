"""Dependency-light extraction for common manuscript container formats."""
import io
import os
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.current = []
        self.heading = None
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"head", "script", "style", "svg", "nav"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"h1", "h2"}:
            self._flush()
            self.heading = tag
        elif tag in {"p", "div", "li", "br"}:
            self._flush()

    def handle_endtag(self, tag):
        if tag in {"head", "script", "style", "svg", "nav"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"h1", "h2", "p", "div", "li"}:
            self._flush()
            if tag in {"h1", "h2"}:
                self.heading = None

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.current.append(data.strip())

    def _flush(self):
        if self.current:
            text = " ".join(self.current)
            self.lines.append(("# " if self.heading == "h1" else "") + text)
            self.current = []

    def text(self):
        self._flush()
        return "\n\n".join(self.lines)


def _docx_sources(filename: str, data: bytes) -> list[tuple[str, str]]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    sections, title, body = [], None, []
    for paragraph in root.findall(".//w:body/w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if not text:
            continue
        style = paragraph.find("./w:pPr/w:pStyle", ns)
        style_name = style.get(f"{{{ns['w']}}}val", "") if style is not None else ""
        if style_name.lower().replace(" ", "") in {"heading1", "title"}:
            if title is not None or body:
                sections.append((f"{filename}-{len(sections)+1}",
                                 f"# {title or os.path.splitext(filename)[0]}\n\n" + "\n\n".join(body)))
            title, body = text, []
        else:
            body.append(text)
    if title is not None or body:
        sections.append((f"{filename}-{len(sections)+1}",
                         f"# {title or os.path.splitext(filename)[0]}\n\n" + "\n\n".join(body)))
    return sections


def _epub_sources(filename: str, data: bytes) -> list[tuple[str, str]]:
    sources = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = []
        try:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next(node.attrib["full-path"] for node in container.iter()
                            if node.tag.endswith("}rootfile") or node.tag == "rootfile")
            package = ET.fromstring(archive.read(rootfile))
            manifest = {node.attrib["id"]: node.attrib for node in package.iter()
                        if (node.tag.endswith("}item") or node.tag == "item")
                        and "id" in node.attrib and "href" in node.attrib}
            for node in package.iter():
                if not (node.tag.endswith("}itemref") or node.tag == "itemref"):
                    continue
                item = manifest.get(node.attrib.get("idref"))
                if not item or "nav" in item.get("properties", "").split():
                    continue
                if item.get("media-type") not in {"application/xhtml+xml", "text/html"}:
                    continue
                name = posixpath.normpath(posixpath.join(posixpath.dirname(rootfile),
                                                       item["href"].split("#", 1)[0]))
                if name in archive.namelist():
                    names.append(name)
        except (KeyError, StopIteration, ET.ParseError):
            pass
        if not names:
            names = sorted(n for n in archive.namelist()
                           if n.lower().endswith((".xhtml", ".html", ".htm"))
                           and "nav" not in os.path.basename(n).lower())
        for name in names:
            parser = _TextHTMLParser()
            parser.feed(archive.read(name).decode("utf-8", errors="replace"))
            text = parser.text().strip()
            if text:
                sources.append((os.path.basename(name), text))
    return sources


def document_to_sources(filename: str, data: bytes) -> list[tuple[str, str]]:
    ext = os.path.splitext(filename)[1].lower()
    if ext in {".txt", ".md", ".markdown"}:
        return [(filename, data.decode("utf-8", errors="replace"))]
    if ext == ".docx":
        return _docx_sources(filename, data)
    if ext == ".epub":
        return _epub_sources(filename, data)
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF import requires the pypdf dependency") from exc
        pages = [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        return [(filename, text)] if text else []
    raise ValueError("supported manuscript types are .txt, .md, .docx, .epub, and .pdf")
