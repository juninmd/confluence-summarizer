"""Confluence storage format -> Markdown, with macros, tables and images."""

import re
from typing import Callable, Iterable, List, Optional

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.backup.refs import ImageRef

_CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)
_CDATA_TOKEN = "\x00cdata-%d\x00"
_CDATA_BACK = re.compile(r"\x00cdata-(\d+)\x00")

_INLINE = {
    "strong": "**", "b": "**", "em": "*", "i": "*",
    "del": "~~", "s": "~~", "strike": "~~",
}  # fmt: skip
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_BLOCKS = {
    "p", "div", "section", "article", "main", "header", "footer", "figure",
    "figcaption", "details", "blockquote", "pre", "table", "ul", "ol", "hr",
    "ac:task-list", "ac:structured-macro", "ac:adf-extension", "ac:layout",
    "ac:layout-section", "ac:layout-cell", "ac:placeholder",
}  # fmt: skip
_SKIP = {"ac:adf-fallback", "script", "style", "ac:parameter", "ac:plain-text-body"}


def _ws(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text.replace("\xa0", " "))


class Converter:
    """Convert a page's storage HTML into Markdown.

    ``resolve_image`` receives an :class:`ImageRef` and returns a Markdown-ready
    path (or ``None``); ``resolve_link`` receives a page title and returns the
    relative path of its Markdown file (or ``None``).
    """

    def __init__(
        self,
        resolve_image: Optional[Callable[[ImageRef], Optional[str]]] = None,
        resolve_link: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        self.resolve_image = resolve_image or (lambda ref: None)
        self.resolve_link = resolve_link or (lambda title: None)
        self.missing_images: List[str] = []
        self._cdata: List[str] = []

    # ── public API ─────────────────────────────────────
    def convert(self, html: str) -> str:
        self.missing_images = []
        self._cdata = []

        def protect(match: "re.Match[str]") -> str:
            self._cdata.append(match.group(1))
            return _CDATA_TOKEN % (len(self._cdata) - 1)

        guarded = _CDATA_RE.sub(protect, html or "")
        if not guarded.strip():
            return ""
        soup = BeautifulSoup(guarded, "html.parser")
        text = self._blocks(soup)
        return self._clean(self._restore(text))

    # ── helpers ────────────────────────────────────────
    def _restore(self, text: str) -> str:
        return _CDATA_BACK.sub(lambda m: self._cdata[int(m.group(1))], text)

    @staticmethod
    def _clean(text: str) -> str:
        lines = [line.rstrip() for line in text.split("\n")]
        cleaned = "\n".join(lines).strip("\n")
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return f"{cleaned}\n" if cleaned.strip() else ""

    def _blocks(self, node: Tag) -> str:
        out: List[str] = []
        pending: List[object] = []

        def flush() -> None:
            if not pending:
                return
            text = self._inline_nodes(pending).strip()
            pending.clear()
            if text:
                out.append(text)

        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                # whitespace between inline siblings separates words; keep it
                if str(child).strip() or pending:
                    pending.append(child)
                continue
            if not isinstance(child, Tag):
                continue
            if child.name in _SKIP:
                continue
            if child.name in _BLOCKS or child.name in _HEADINGS:
                flush()
                block = self._block(child)
                if block:
                    out.append(block)
            else:
                pending.append(child)
        flush()
        return "\n\n".join(out)

    def _block(self, tag: Tag) -> str:
        name = tag.name
        if name in _HEADINGS:
            text = self._inline_nodes(tag.children).strip()
            return f"{'#' * _HEADINGS[name]} {text}" if text else ""
        if name == "hr":
            return "---"
        if name == "pre":
            return self._code(self._restore(tag.get_text()), "")
        if name in ("p", "figcaption", "ac:placeholder"):
            return self._inline_nodes(tag.children)
        if name == "blockquote":
            inner = self._blocks(tag)
            return "\n".join(f"> {line}" for line in inner.split("\n") if line.strip())
        if name in ("ul", "ol"):
            return self._list(tag, ordered=name == "ol")
        if name == "table":
            return self._table(tag)
        if name == "ac:task-list":
            return self._tasks(tag)
        if name == "ac:structured-macro":
            return self._macro(tag)
        if name == "ac:adf-extension":
            return self._adf(tag)
        # div/p/section/... and layout scaffolding: just their content
        return self._blocks(tag)

    def _inline_nodes(self, nodes: Iterable[object]) -> str:
        parts = [self._inline(node) for node in nodes]
        text = "".join(parts)
        text = _CDATA_BACK.sub(lambda m: self._cdata[int(m.group(1))], text)
        return _ws(text).strip()

    def _inline(self, node: object) -> str:
        if isinstance(node, Comment):
            return ""
        if isinstance(node, NavigableString):
            return str(node)
        if not isinstance(node, Tag):
            return ""
        name = node.name
        if name in _SKIP:
            return ""
        if name in _INLINE:
            inner = self._inline_nodes(node.children).strip()
            marker = _INLINE[name]
            return f"{marker}{inner}{marker}" if inner else ""
        if name in ("code", "tt", "kbd", "samp"):
            inner = self._inline_nodes(node.children).strip()
            return f"`{inner}`" if inner else ""
        if name == "br":
            return "\n"
        if name == "a":
            return self._anchor(node)
        if name == "ac:image":
            return self._image(node)
        if name == "ac:link":
            return self._link(node)
        if name == "ac:emoticon":
            return node.get("ac:emoji-fallback") or node.get("ac:emoji-shortname") or ""
        if name == "time":
            return node.get("datetime") or self._inline_nodes(node.children)
        if name in ("ac:inline-comment-marker", "sup", "sub", "span"):
            return self._inline_nodes(node.children)
        if name == "ac:structured-macro":
            return self._macro(node)
        if name in _BLOCKS:
            return self._blocks(node)
        return self._inline_nodes(node.children)

    def _anchor(self, tag: Tag) -> str:
        href = (tag.get("href") or "").strip()
        inner = self._inline_nodes(tag.children).strip()
        if not href:
            return inner
        return f"[{inner or href}]({href})"

    # ── images, links ──────────────────────────────────
    def _resolve(self, ref: ImageRef, label: str) -> str:
        path = self.resolve_image(ref)
        if path:
            return f"![{label}]({path})"
        self.missing_images.append(ref.value)
        return f"<!-- missing image: {ref.value} -->"

    def _image(self, tag: Tag) -> str:
        alt = tag.get("ac:alt") or ""
        attachment = tag.find("ri:attachment")
        url = tag.find("ri:url")
        if attachment is not None:
            filename = attachment.get("ri:filename") or ""
            owner = attachment.find("ri:page")
            ref = ImageRef(
                "attachment", filename, owner.get("ri:content-title") if owner else ""
            )
            return self._resolve(ref, alt)
        if url is not None:
            ref = ImageRef("url", url.get("ri:value") or "")
            return self._resolve(ref, alt)
        self.missing_images.append("image")
        return "<!-- missing image: image -->"

    def _link(self, tag: Tag) -> str:
        body = tag.find("ac:link-body") or tag.find("ac:plain-text-link-body")
        text = self._inline_nodes(body.children).strip() if body else ""
        page = tag.find("ri:page")
        if page is not None:
            title = page.get("ri:content-title") or ""
            target = self.resolve_link(title)
            if target:
                return f"[{text or title}]({target})"
            return text or title
        if tag.find("ri:user") is not None:
            return text or "@user"
        attachment = tag.find("ri:attachment")
        if attachment is not None:
            filename = attachment.get("ri:filename") or ""
            return text or filename
        if tag.find("ri:url") is not None:
            target = (tag.find("ri:url").get("ri:value") or "").strip()
            return f"[{text or target}]({target})"
        return text

    # ── lists and tables ───────────────────────────────
    def _list(self, tag: Tag, ordered: bool, depth: int = 0) -> str:
        pad = "  " * depth
        lines: List[str] = []
        index = 1
        for item in tag.find_all("li", recursive=False):
            nested = [c for c in item.find_all(["ul", "ol"], recursive=False)]
            for child in nested:
                child.extract()
            body = self._inline_nodes(item.children).strip()
            body = " ".join(line.strip() for line in body.split("\n") if line.strip())
            marker = f"{index}." if ordered else "-"
            lines.append(f"{pad}{marker} {body}".rstrip())
            index += 1
            for child in nested:
                lines.append(self._list(child, ordered=child.name == "ol", depth=depth + 1))
        return "\n".join(line for line in lines if line)

    def _tasks(self, tag: Tag) -> str:
        lines: List[str] = []
        for task in tag.find_all("ac:task", recursive=False):
            status = task.find("ac:task-status")
            body = task.find("ac:task-body")
            done = status is not None and (status.get_text() or "").strip() == "complete"
            text = self._inline_nodes(body.children).strip() if body else ""
            lines.append(f"- [{'x' if done else ' '}] {text}".rstrip())
        return "\n".join(lines)

    def _table(self, tag: Tag) -> str:
        rows = tag.find_all("tr")
        if not rows:
            return ""
        if tag.find("table") is not None or tag.find(attrs={"colspan": True}) or tag.find(
            attrs={"rowspan": True}
        ):
            return str(tag)
        grid: List[List[Tag]] = []
        header: List[Tag] = []
        for row in rows:
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                return str(tag)
            if row.find("th") is not None and not header:
                header = cells
            else:
                grid.append(cells)
        width = max([len(header)] + [len(row) for row in grid]) if header or grid else 0
        if width == 0:
            return ""
        if not header:
            header = []
        head = self._row([self._cell(c) for c in header], width)
        sep = "| " + " | ".join(["---"] * width) + " |"
        body = "\n".join(
            self._row([self._cell(c) for c in row], width) for row in grid
        )
        return "\n".join(part for part in (head, sep, body) if part)

    @staticmethod
    def _row(cells: List[str], width: int) -> str:
        padded = (cells + [""] * width)[:width]
        row = "| " + " | ".join(padded) + " |"
        return re.sub(r" {2,}(?=\|)", " ", row)

    def _cell(self, cell: Tag) -> str:
        text = self._inline_nodes(cell.children).strip()
        text = text.replace("\n", " ").replace("|", "\\|")
        return re.sub(r"\s+", " ", text).strip()

    # ── code and macros ────────────────────────────────
    @staticmethod
    def _code(content: str, language: str) -> str:
        body = (content or "").strip("\n")
        fence = "```"
        while fence in body:
            fence += "`"
        return f"{fence}{language}\n{body}\n{fence}"

    @staticmethod
    def _params(tag: Tag) -> dict:
        return {
            param.get("ac:name") or "": (param.get_text() or "").strip()
            for param in tag.find_all("ac:parameter", recursive=False)
        }

    def _macro(self, tag: Tag) -> str:
        name = (tag.get("ac:name") or "").strip()
        params = self._params(tag)
        body = tag.find("ac:rich-text-body")
        inner = self._blocks(body) if body is not None else ""
        plain = tag.find("ac:plain-text-body")

        if name == "code":
            body = self._restore(plain.get_text()) if plain is not None else ""
            return self._code(body, params.get("language", ""))
        if name in ("info", "note", "warning", "tip", "panel"):
            if name == "panel":
                return inner
            label = {"info": "NOTE", "note": "NOTE", "warning": "WARNING", "tip": "TIP"}[name]
            title = params.get("title") or ""
            lines = [f"> [!{label}]"]
            if title:
                lines.append(f"> **{title}**")
            lines.extend(f"> {line}" for line in inner.split("\n") if line.strip())
            return "\n".join(lines)
        if name == "expand":
            title = params.get("title") or "Detalhes"
            return f"<details>\n<summary>{title}</summary>\n\n{inner}\n\n</details>"
        if name == "status":
            return f"**[{params.get('title', '')}]**"
        if name == "jira":
            return f"JIRA: {params.get('key', '')}"
        if name == "toc":
            return ""
        if name == "include":
            page = tag.find("ri:page")
            title = page.get("ri:content-title") if page is not None else ""
            return f"[Included page: {title or '?'}]"
        if name == "excerpt":
            return f"<!-- macro: excerpt -->\n{inner}"
        if name == "drawio":
            diagram = params.get("diagramName") or "diagram"
            ref = ImageRef("attachment", f"{diagram}.png")
            path = self.resolve_image(ref)
            if path:
                return f"![{diagram}]({path})"
            self.missing_images.append(f"{diagram}.png")
            return f"<!-- missing diagram preview: {diagram} -->"
        return f"<!-- unsupported macro: {name} {params} -->"

    def _adf(self, tag: Tag) -> str:
        node = tag.find("ac:adf-node")
        if node is None:
            return ""
        kind = node.get("type") or ""
        content = node.find("ac:adf-content")
        inner = self._blocks(content) if content is not None else ""
        if kind == "panel":
            attr = node.find("ac:adf-attribute", attrs={"key": "panel-type"})
            kind_name = (attr.get_text() if attr is not None else "").strip().upper() or "NOTE"
            lines = [f"> [!{kind_name}]"]
            lines.extend(f"> {line}" for line in inner.split("\n") if line.strip())
            return "\n".join(lines)
        return inner
