"""Renderer ringan format teks Redmine (Textile & Markdown) ke widget tk.Text.

Tidak bertujuan 100% identik dengan Redmine web, tetapi mencakup sintaks yang umum dipakai:
heading, bold/italic/underline/strike, inline code, blok kode, list, quote, tabel,
garis pemisah, link, referensi task (#123), dan gambar inline.
"""

import re
import sys
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Dict, List, Optional, Sequence

if sys.platform == "win32":
    MONO_FAMILY = "Consolas"
elif sys.platform == "darwin":
    MONO_FAMILY = "Menlo"
else:
    MONO_FAMILY = "DejaVu Sans Mono"

FORMAT_OPTIONS = {"Otomatis": "auto", "Textile": "textile", "Markdown": "markdown"}

_TEXTILE_HINTS = [
    r"^h[1-6]\.\s", r"^bq\.\s", r"^p[<>=(]*\.\s", r'"[^"\n]+":(?:https?://|/)', r"!\S+\.(?:png|jpe?g|gif|bmp|webp)!",
    r"(?<![\w@])@[^@\s][^@\n]*@", r"^\|_\.", r"^\*{1,3}\s", r"^#{1,3}\s+\S.*(?<!#)$",
]
_MARKDOWN_HINTS = [
    r"^```", r"^~~~", r"\]\([^)\s]+\)", r"\*\*[^*\n]+\*\*", r"^\s*[-+]\s", r"`[^`\n]+`", r"^\s*\d+\.\s",
    r"^\|?\s*:?-{3,}:?\s*\|", r"^#{1,6}\s",
]


def detect_format(text: str) -> str:
    """Tebak format teks; Textile adalah default Redmine sehingga menang bila seri."""
    textile = sum(len(re.findall(p, text, re.MULTILINE | re.IGNORECASE)) for p in _TEXTILE_HINTS)
    markdown = sum(len(re.findall(p, text, re.MULTILINE)) for p in _MARKDOWN_HINTS)
    return "markdown" if markdown > textile else "textile"


class MarkupRenderer:
    def __init__(
        self,
        widget: tk.Text,
        on_issue: Optional[Callable[[int], None]] = None,
        on_url: Optional[Callable[[str], None]] = None,
        on_image: Optional[Callable[[tk.Text, str, str], None]] = None,
    ):
        self.w = widget
        self.on_issue = on_issue
        self.on_url = on_url
        self.on_image = on_image
        self._fonts: Dict[str, tkfont.Font] = {}
        self._link_seq = 0
        self.md = False
        self._rules: List[tk.Frame] = []
        self._line_color = "#888888"
        widget.bind("<Configure>", self._resize_rules, add="+")

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def configure_tags(self, colors: Dict[str, str]) -> None:
        base = tkfont.Font(font=self.w.cget("font"))
        family = base.actual("family")
        size = base.actual("size")

        def font(scale: float = 1.0, mono: bool = False, **kwargs) -> tkfont.Font:
            scaled = int(round(size * scale)) or size
            return tkfont.Font(family=MONO_FAMILY if mono else family, size=scaled, **kwargs)

        self._fonts = {
            "h1": font(1.55, weight="bold"), "h2": font(1.35, weight="bold"), "h3": font(1.18, weight="bold"),
            "h4": font(1.05, weight="bold"), "b": font(weight="bold"), "i": font(slant="italic"),
            "bi": font(weight="bold", slant="italic"), "code": font(0.95, mono=True),
            "th": font(0.95, mono=True, weight="bold"), "small": font(0.9),
        }
        w = self.w
        self._line_color = colors["line"]
        self._rules = [r for r in self._rules if r.winfo_exists()]
        for rule in self._rules:
            rule.configure(bg=self._line_color)
        for level, key in ((1, "h1"), (2, "h2"), (3, "h3"), (4, "h4"), (5, "h4"), (6, "h4")):
            w.tag_configure(f"h{level}", font=self._fonts[key], foreground=colors["text"], spacing1=10, spacing3=4)
        w.tag_configure("b", font=self._fonts["b"])
        w.tag_configure("i", font=self._fonts["i"])
        w.tag_configure("bi", font=self._fonts["bi"])
        w.tag_configure("u", underline=True)
        w.tag_configure("s", overstrike=True)
        w.tag_configure("code", font=self._fonts["code"], background=colors["code_bg"], foreground=colors["code_fg"])
        w.tag_configure("pre", font=self._fonts["code"], background=colors["code_bg"], foreground=colors["text"],
                        lmargin1=12, lmargin2=12, rmargin=12, spacing1=1, spacing3=1)
        w.tag_configure("quote", foreground=colors["muted"], lmargin1=18, lmargin2=18, font=self._fonts["i"])
        w.tag_configure("link", foreground=colors["link"], underline=True)
        w.tag_configure("muted", foreground=colors["muted"])
        w.tag_configure("small", font=self._fonts["small"], foreground=colors["muted"])
        w.tag_configure("hr", foreground=colors["line"])
        w.tag_configure("table", font=self._fonts["code"])
        w.tag_configure("th", font=self._fonts["th"])
        w.tag_configure("spacer", font=font(0.45))
        for level in range(1, 6):
            w.tag_configure(f"li{level}", lmargin1=8 + 18 * (level - 1), lmargin2=8 + 18 * (level - 1) + 16)
        w.tag_configure("bullet", foreground=colors["muted"])
        # Tag link harus menang atas font/warna tag lain
        w.tag_raise("link")

    # ------------------------------------------------------------------
    # Garis pemisah (embedded frame 1px yang mengikuti lebar widget)
    # ------------------------------------------------------------------

    def _rule_width(self) -> int:
        width = self.w.winfo_width()
        padding = int(self.w.cget("padx") or 0) * 2
        return max(100, width - padding - 8) if width > 1 else 600

    def insert_rule(self) -> None:
        rule = tk.Frame(self.w, height=1, width=self._rule_width(), bg=self._line_color, bd=0, highlightthickness=0)
        self._rules.append(rule)
        self.w.window_create("end", window=rule, pady=6)
        self.w.insert("end", "\n")

    def clear_rules(self) -> None:
        for rule in self._rules:
            if rule.winfo_exists():
                rule.destroy()
        self._rules = []

    def _resize_rules(self, _event=None) -> None:
        width = self._rule_width()
        self._rules = [r for r in self._rules if r.winfo_exists()]
        for rule in self._rules:
            rule.configure(width=width)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, source: str, text_format: str = "auto") -> None:
        source = (source or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        if text_format == "auto":
            text_format = detect_format(source)
        self.md = text_format == "markdown"

        lines = source.split("\n")
        counters: List[tuple] = []
        last_blank = False
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Blok kode: ``` / ~~~ (markdown) atau <pre> (keduanya)
            fence = re.match(r"^(```|~~~)", stripped) if self.md else None
            if fence:
                block, i = self._collect_until(lines, i + 1, lambda l, f=fence.group(1): l.strip().startswith(f))
                self._insert_pre(block)
                last_blank = False
                continue
            if re.match(r"^<pre\b", stripped, re.IGNORECASE):
                i = self._render_pre_html(lines, i)
                last_blank = False
                continue

            if not stripped:
                if not last_blank:
                    self.w.insert("end", "\n", "spacer")
                last_blank = True
                counters = []
                i += 1
                continue
            last_blank = False

            # Macro Redmine
            collapse = re.match(r"^\{\{collapse\((.*?)\)\s*$", stripped)
            if collapse:
                title = collapse.group(1).split(",")[0].strip() or "Detail"
                self.w.insert("end", f"▾ {title}\n", ("b", "muted"))
                i += 1
                continue
            if stripped == "}}" or re.fullmatch(r"\{\{[<>]?toc\}\}", stripped):
                i += 1
                continue

            if re.fullmatch(r"(-\s*){3,}|(\*\s*){3,}|(_\s*){3,}", stripped):
                self.insert_rule()
                i += 1
                continue

            heading = (
                re.match(r"^(#{1,6})\s+(.*?)\s*#*$", stripped) if self.md
                else re.match(r"^h([1-6])(?:\([^)]*\)|\{[^}]*\}|[<>=])*\.\s+(.*)$", stripped)
            )
            if heading:
                level = len(heading.group(1)) if self.md else int(heading.group(1))
                self._inline(heading.group(2), (f"h{level}",))
                self.w.insert("end", "\n", f"h{level}")
                counters = []
                i += 1
                continue

            quote = re.match(r"^(?:bq\.\s+|>\s?)(.*)$", stripped) if not self.md else re.match(r"^>\s?(.*)$", stripped)
            if quote:
                self.w.insert("end", "│ ", ("quote", "hr"))
                self._inline(quote.group(1), ("quote",))
                self.w.insert("end", "\n", "quote")
                i += 1
                continue

            if stripped.startswith("|"):
                rows, i = self._collect_while(lines, i, lambda l: l.strip().startswith("|"))
                self._insert_table(rows)
                continue

            if self._try_list_item(line, counters):
                i += 1
                continue
            counters = []

            if not self.md:
                stripped = re.sub(r"^p(?:\([^)]*\)|\{[^}]*\}|[<>=])*\.\s+", "", stripped)
            self._inline(line.rstrip() if self.md else stripped, ())
            self.w.insert("end", "\n")
            i += 1

    def _try_list_item(self, line: str, counters: List[tuple]) -> bool:
        if self.md:
            match = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
            if not match:
                return False
            level = min(5, len(match.group(1).replace("\t", "    ")) // 2 + 1)
            marker = match.group(2)
            ordered = marker[0].isdigit()
            content = match.group(3)
            bullet = f"{marker[:-1]}." if ordered else "•"
        else:
            match = re.match(r"^([*#]+)\s+(.*)$", line.strip())
            if not match:
                return False
            markers = match.group(1)
            level = min(5, len(markers))
            ordered = markers[-1] == "#"
            content = match.group(2)
            # counters[n] = (ordered, nomor) per level; ganti jenis list = mulai hitungan baru
            del counters[level:]
            while len(counters) < level:
                counters.append((ordered, 0))
            if counters[level - 1][0] != ordered:
                counters[level - 1] = (ordered, 0)
            counters[level - 1] = (ordered, counters[level - 1][1] + 1)
            bullet = f"{counters[level - 1][1]}." if ordered else ("•" if level % 2 else "◦")

        tag = f"li{level}"
        self.w.insert("end", f"{bullet} ", (tag, "bullet"))
        self._inline(content, (tag,))
        self.w.insert("end", "\n", tag)
        return True

    @staticmethod
    def _collect_until(lines: List[str], start: int, is_end: Callable[[str], bool]):
        block = []
        i = start
        while i < len(lines) and not is_end(lines[i]):
            block.append(lines[i])
            i += 1
        return block, i + 1

    @staticmethod
    def _collect_while(lines: List[str], start: int, keep: Callable[[str], bool]):
        block = []
        i = start
        while i < len(lines) and keep(lines[i]):
            block.append(lines[i])
            i += 1
        return block, i

    def _render_pre_html(self, lines: List[str], start: int) -> int:
        block: List[str] = []
        i = start
        while i < len(lines):
            block.append(lines[i])
            if re.search(r"</pre>", lines[i], re.IGNORECASE):
                break
            i += 1
        text = "\n".join(block)
        text = re.sub(r"</?pre[^>]*>|</?code[^>]*>", "", text, flags=re.IGNORECASE)
        self._insert_pre(text.strip("\n").split("\n"))
        return i + 1

    def _insert_pre(self, block: Sequence[str]) -> None:
        text = "\n".join(block)
        text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        self.w.insert("end", text + "\n", "pre")

    def _insert_table(self, rows: List[str]) -> None:
        parsed: List[List[str]] = []
        header_rows = set()
        for row in rows:
            body = row.strip()
            body = body[1:] if body.startswith("|") else body
            body = body[:-1] if body.endswith("|") else body
            cells = [c.strip() for c in body.split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c) and parsed:
                header_rows.add(len(parsed) - 1)  # baris pemisah markdown
                continue
            is_header = False
            clean = []
            for cell in cells:
                attr = re.match(r"^((?:_|[<>=^~]|\\\d+|/\d+|\{[^}]*\}|\([^)]*\))+)\.\s*", cell)
                if attr:
                    is_header = is_header or "_" in attr.group(1)
                    cell = cell[attr.end():]
                clean.append(self._plain(cell))
            if is_header:
                header_rows.add(len(parsed))
            parsed.append(clean)
        if not parsed:
            return

        columns = max(len(r) for r in parsed)
        widths = [max((len(r[c]) if c < len(r) else 0) for r in parsed) for c in range(columns)]
        border = "─"
        for idx, row in enumerate(parsed):
            cells = [(row[c] if c < len(row) else "").ljust(widths[c]) for c in range(columns)]
            tag = ("table", "th") if idx in header_rows else ("table",)
            self.w.insert("end", " " + "  │  ".join(cells) + "\n", tag)
            if idx in header_rows:
                self.w.insert("end", border + "──┼──".join(border * w for w in widths) + border + "\n", ("table", "hr"))

    def _plain(self, text: str) -> str:
        text = re.sub(r'"([^"]+)":\S+', r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        return re.sub(r"(\*\*|__|[*_@`+])(.+?)\1", r"\2", text)

    # ------------------------------------------------------------------
    # Inline
    # ------------------------------------------------------------------

    def _patterns(self):
        if self.md:
            return [
                ("code", r"`([^`\n]+)`"),
                ("image", r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)"),
                ("link", r"\[([^\]]+)\]\(\s*<?([^)\s>]+)>?[^)]*\)"),
                ("url", r"(?<![\w/\"(<])(https?://[^\s<>\"']*[^\s<>\"'.,;:!?)\]])"),
                ("issue", r"(?<![\w&/#])#(\d+)\b"),
                ("bi", r"(\*\*\*|___)(?=\S)(.+?)(?<=\S)\1"),
                ("b", r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"),
                ("i", r"(?<![\w*])(\*)(?=\S)(.+?)(?<=\S)\*(?![\w*])"),
                ("i", r"(?<![\w_])(_)(?=\S)(.+?)(?<=\S)_(?![\w_])"),
                ("s", r"(~~)(.+?)~~"),
            ]
        return [
            ("code", r"(?<![\w@])@([^@\n]+?)@(?![\w@])"),
            ("image", r"!(?:\([^)]*\))?(?:\{[^}]*\})?[<>=]?([^\s!()]+?)(?:\(([^)]*)\))?!"),
            ("link", r'"([^"\n]+?)(?:\([^)]*\))?":((?:https?://|/|mailto:)[^\s<>"]*[^\s<>".,;:!?)\]])'),
            ("url", r"(?<![\w/\"(<:])(https?://[^\s<>\"']*[^\s<>\"'.,;:!?)\]])"),
            ("issue", r"(?<![\w&/#])#(\d+)\b"),
            ("b", r"(?<![\w*])(\*\*?)(?=\S)(.+?)(?<=\S)\1(?![\w*])"),
            ("i", r"(?<![\w_])(__?)(?=\S)(.+?)(?<=\S)\1(?![\w_])"),
            ("u", r"(?<![\w+])(\+)(?=\S)(.+?)(?<=\S)\+(?![\w+])"),
            ("s", r"(?:(?<=\s)|^)(-)(?=[^\s-])(.+?)(?<=[^\s-])-(?=$|[\s.,;:!?])"),
        ]

    def _inline(self, text: str, tags: tuple) -> None:
        patterns = [(name, re.compile(p)) for name, p in self._patterns()]
        pos = 0
        while pos < len(text):
            best = None
            for name, regex in patterns:
                match = regex.search(text, pos)
                if match and (best is None or match.start() < best[1].start()):
                    best = (name, match)
            if best is None:
                break
            name, match = best
            if match.start() > pos:
                self.w.insert("end", text[pos:match.start()], tags)
            self._emit(name, match, tags)
            pos = match.end()
        if pos < len(text):
            self.w.insert("end", text[pos:], tags)

    def _emit(self, name: str, match: re.Match, tags: tuple) -> None:
        if name == "code":
            self.w.insert("end", match.group(1), tags + ("code",))
        elif name == "image":
            if self.md:
                alt, src = match.group(1), match.group(2)
            else:
                src, alt = match.group(1), match.group(2) or ""
            if self.on_image:
                self.on_image(self.w, src, alt)
            else:
                self.w.insert("end", alt or src, tags + ("muted",))
        elif name == "link":
            label, url = match.group(1), match.group(2)
            self._insert_link(label, tags, lambda u=url: self.on_url and self.on_url(u))
        elif name == "url":
            url = match.group(1)
            self._insert_link(url, tags, lambda u=url: self.on_url and self.on_url(u))
        elif name == "issue":
            issue_id = int(match.group(1))
            self._insert_link(f"#{issue_id}", tags, lambda i=issue_id: self.on_issue and self.on_issue(i))
        else:
            style = name
            if name in ("b", "i") and ({"b", "i"} - {name}) & set(tags):
                style = "bi"
            self._inline(match.group(2), tags + (style,))

    def _insert_link(self, label: str, tags: tuple, callback: Callable[[], None]) -> None:
        self._link_seq += 1
        tag = f"md_link_{self._link_seq}"
        self.w.insert("end", label, tags + ("link", tag))
        self.w.tag_bind(tag, "<Button-1>", lambda _e: callback())
        self.w.tag_bind(tag, "<Enter>", lambda _e: self.w.configure(cursor="hand2"))
        self.w.tag_bind(tag, "<Leave>", lambda _e: self.w.configure(cursor=""))
