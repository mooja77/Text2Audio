import io
import zipfile

import pytest

from pipeline.documents import document_to_sources


def test_text_document_decodes():
    assert document_to_sources("a.txt", b"hello") == [("a.txt", "hello")]


def test_docx_heading_one_creates_sections():
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
      <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>One</w:t></w:r></w:p>
      <w:p><w:r><w:t>First body.</w:t></w:r></w:p>
      <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Two</w:t></w:r></w:p>
      <w:p><w:r><w:t>Second body.</w:t></w:r></w:p>
    </w:body></w:document>'''
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", xml)
    sources = document_to_sources("book.docx", buf.getvalue())
    assert len(sources) == 2
    assert sources[0][1].startswith("# One") and "First body" in sources[0][1]


def test_epub_extracts_html_content():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("OEBPS/ch1.xhtml", "<html><body><h1>Start</h1><p>Hello.</p></body></html>")
    sources = document_to_sources("book.epub", buf.getvalue())
    assert sources and "# Start" in sources[0][1] and "Hello." in sources[0][1]


def test_epub_uses_spine_order_and_skips_head():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("META-INF/container.xml", '''<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
            <rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>''')
        archive.writestr("OEBPS/content.opf", '''<package xmlns="http://www.idpf.org/2007/opf">
            <manifest><item id="one" href="z.xhtml" media-type="application/xhtml+xml"/>
            <item id="two" href="a.xhtml" media-type="application/xhtml+xml"/></manifest>
            <spine><itemref idref="one"/><itemref idref="two"/></spine></package>''')
        archive.writestr("OEBPS/z.xhtml", "<html><head><title>Hidden</title></head><body><p>First.</p></body></html>")
        archive.writestr("OEBPS/a.xhtml", "<html><body><p>Second.</p></body></html>")
    sources = document_to_sources("book.epub", buf.getvalue())
    assert [name for name, _ in sources] == ["z.xhtml", "a.xhtml"]
    assert sources[0][1] == "First."


def test_unknown_document_rejected():
    with pytest.raises(ValueError):
        document_to_sources("book.exe", b"no")
