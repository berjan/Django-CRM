"""Utilities for presenting plain-text email content safely."""

from html.parser import HTMLParser

REPLY_BOUNDARY_MARKERS = (
    "\nDe informatie opgenomen in dit bericht",
    "\nThe information contained in this message",
    "\nOn ",
    "\nOp ",
)


class _HTMLTextExtractor(HTMLParser):
    """Extract readable text without rendering untrusted email HTML."""

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
    }
    IGNORED_TAGS = {"head", "script", "style", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in self.IGNORED_TAGS:
            self._ignored_depth += 1
        elif not self._ignored_depth and (tag == "br" or tag in self.BLOCK_TAGS):
            self._append_newline()

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self.IGNORED_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif not self._ignored_depth and tag in self.BLOCK_TAGS:
            self._append_newline()

    def handle_data(self, data: str):
        if not self._ignored_depth:
            self._chunks.append(data)

    def text(self) -> str:
        lines = (
            " ".join(line.split()) for line in "".join(self._chunks).splitlines()
        )
        return "\n".join(line for line in lines if line).strip()

    def _append_newline(self):
        if self._chunks and self._chunks[-1] != "\n":
            self._chunks.append("\n")


def html_to_plain_text(body_html: str) -> str:
    """Convert an HTML email body to compact, safe, readable plain text."""
    if not body_html:
        return ""

    parser = _HTMLTextExtractor()
    parser.feed(body_html)
    parser.close()
    return parser.text()


def plain_text_email_body(body_text: str, body_html: str) -> str:
    """Return the original plain body, or derive it from HTML when absent."""
    if body_text and body_text.strip():
        return body_text
    return html_to_plain_text(body_html)


def email_body_preview(body_text: str, body_html: str, *, limit: int = 1600) -> str:
    """Return the authored part of an email without common quoted-history blocks."""
    body = plain_text_email_body(body_text, body_html)
    end = len(body)
    for marker in REPLY_BOUNDARY_MARKERS:
        index = body.find(marker)
        if index > 0:
            end = min(end, index)
    return body[: min(end, limit)].strip()
