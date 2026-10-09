from datetime import date, datetime
from io import BytesIO
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote, urlparse
import webbrowser

import customtkinter as ctk
from PIL import Image, ImageTk

from theme import COLORS, get_color
from icons import get_icon
from redmine_markup import MarkupRenderer
from redmine_service import RedmineClient, RedmineError

FIELD_LABELS = {
    "status_id": "Status",
    "assigned_to_id": "Assignee",
    "priority_id": "Priority",
    "tracker_id": "Tracker",
    "project_id": "Project",
    "category_id": "Category",
    "fixed_version_id": "Target version",
    "parent_id": "Parent task",
    "subject": "Subject",
    "description": "Deskripsi",
    "start_date": "Start date",
    "due_date": "Due date",
    "done_ratio": "Done %",
    "estimated_hours": "Estimated time",
    "is_private": "Private",
}
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
THUMBNAIL_SIZE = (220, 160)
MAX_INLINE_HEIGHT = 620


def format_datetime(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%d %b %Y %H:%M")
    except ValueError:
        return value


def format_date(value: Optional[str]) -> str:
    if not value:
        return "-"
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except ValueError:
        return value


def _name(ref: Optional[Dict[str, Any]]) -> str:
    return (ref or {}).get("name") or "-"


def _is_image(attachment: Dict[str, Any]) -> bool:
    content_type = (attachment.get("content_type") or "").lower()
    return content_type.startswith("image/") or (attachment.get("filename") or "").lower().endswith(IMAGE_EXTENSIONS)


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


class RedmineIssuePanel(ctk.CTkFrame):
    """Detail satu task Redmine yang ditampilkan sebagai tab di dalam aplikasi."""

    def __init__(
        self,
        parent: Any,
        client: RedmineClient,
        issue_id: int,
        lookups: Dict[str, Dict[str, str]],
        on_loaded: Optional[Callable[[int, Dict[str, Any]], None]] = None,
        on_open_issue: Optional[Callable[[int], None]] = None,
        text_format: str = "auto",
    ):
        super().__init__(parent, fg_color="transparent")
        self.client = client
        self.issue_id = issue_id
        self.lookups = lookups
        self.text_format = text_format
        self.issue: Dict[str, Any] = {}
        self._on_loaded = on_loaded
        self._on_open_issue = on_open_issue
        self._is_loading = False

        # Gambar: cache bytes per URL agar refresh tidak mengunduh ulang
        self._image_cache: Dict[str, bytes] = {}
        self._photos: List[ImageTk.PhotoImage] = []
        self._render_gen = 0
        self._image_seq = 0
        self._attachments_by_name: Dict[str, Dict[str, Any]] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._setup_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)

        self.lbl_subject = ctk.CTkLabel(
            header, text=f"#{self.issue_id}", text_color=COLORS["text"], font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w", justify="left", wraplength=560
        )
        self.lbl_subject.grid(row=0, column=0, sticky="ew")
        self.lbl_meta = ctk.CTkLabel(header, text="Memuat detail task...", text_color=COLORS["muted"], font=ctk.CTkFont(size=11), anchor="w")
        self.lbl_meta.grid(row=1, column=0, sticky="ew")

        buttons = ctk.CTkFrame(header, fg_color="transparent")
        buttons.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(10, 0))
        self.btn_refresh = ctk.CTkButton(
            buttons, text="", image=get_icon("refresh-cw", (14, 14), COLORS["text"]), width=34, height=32,
            corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            border_width=1, border_color=COLORS["line"], command=self.refresh
        )
        self.btn_refresh.pack(side="left")
        ctk.CTkButton(
            buttons, text=" Buka di Browser", image=get_icon("external-link", (14, 14), COLORS["text"]), compound="left",
            width=140, height=32, corner_radius=8, fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"], border_width=1, border_color=COLORS["line"], font=ctk.CTkFont(size=12),
            command=self.open_in_browser
        ).pack(side="left", padx=(6, 0))

        # Tab konten: Detail (atribut + deskripsi + lampiran, seperti kotak issue di web) / Riwayat / Subtask
        self.tabview = ctk.CTkTabview(
            self, fg_color=COLORS["surface"], border_width=1, border_color=COLORS["line"], corner_radius=8,
            segmented_button_fg_color=COLORS["surface_hover"], segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
            segmented_button_unselected_color=COLORS["surface_hover"],
            segmented_button_unselected_hover_color=COLORS["surface_active"],
            text_color=COLORS["text"], anchor="w", height=200
        )
        self.tabview.grid(row=1, column=0, sticky="nsew")
        self._tab_names = {"desc": "Detail", "history": "Riwayat", "children": "Subtask & Relasi"}
        self.text_desc = self._add_text_tab(self._tab_names["desc"])
        self.text_history = self._add_text_tab(self._tab_names["history"])
        self.text_children = self._add_text_tab(self._tab_names["children"])

        self._renderers = {
            textbox: MarkupRenderer(
                textbox._textbox, on_issue=self._open_issue, on_url=self._open_url, on_image=self._insert_inline_image
            )
            for textbox in (self.text_desc, self.text_history, self.text_children)
        }
        self._apply_text_tags()

    def _add_text_tab(self, name: str) -> ctk.CTkTextbox:
        tab = self.tabview.add(name)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        textbox = ctk.CTkTextbox(
            tab, fg_color=COLORS["input_bg"], text_color=COLORS["text"], border_width=0,
            font=ctk.CTkFont(size=12), wrap="word"
        )
        textbox.grid(row=0, column=0, sticky="nsew")
        textbox._textbox.configure(padx=14, pady=10, spacing1=1, spacing3=1)
        textbox.configure(state="disabled")
        return textbox

    def _apply_text_tags(self):
        colors = {
            "text": get_color("text"), "muted": get_color("muted"), "link": get_color("accent_text"),
            "line": get_color("line"), "code_bg": get_color("surface_hover"), "code_fg": get_color("danger_text"),
        }
        for textbox, renderer in self._renderers.items():
            renderer.configure_tags(colors)
            inner = textbox._textbox
            inner.tag_configure("heading", font=renderer._fonts["b"], foreground=colors["text"])
            inner.tag_configure("section", font=renderer._fonts["h4"], foreground=colors["text"], spacing1=6, spacing3=4)
            inner.tag_configure("change", foreground=colors["link"])
            inner.tag_configure("danger", foreground=get_color("danger"))
            inner.tag_configure("attr_label", font=renderer._fonts["b"], foreground=colors["muted"])
            inner.tag_configure("attrs", tabs=(150, 450, 600), spacing1=3, spacing3=3)
            inner.tag_configure("journal", lmargin1=0, lmargin2=0)

    def on_theme_changed(self):
        self._apply_text_tags()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def refresh(self):
        if self._is_loading:
            return
        self._is_loading = True
        self.btn_refresh.configure(state="disabled")
        self.lbl_meta.configure(text="Memuat detail task...", text_color=COLORS["muted"])

        def worker():
            try:
                issue = self.client.get_issue(self.issue_id)
                self.after(0, lambda: self._on_loaded_issue(issue))
            except RedmineError as error:
                message = str(error)
                self.after(0, lambda: self._on_failed(message))

        threading.Thread(target=worker, daemon=True).start()

    def _on_failed(self, message: str):
        if not self.winfo_exists():
            return
        self._is_loading = False
        self.btn_refresh.configure(state="normal")
        self.lbl_meta.configure(text=f"Gagal memuat task: {message}", text_color=COLORS["danger"])

    def _on_loaded_issue(self, issue: Dict[str, Any]):
        if not self.winfo_exists():
            return
        self._is_loading = False
        self.btn_refresh.configure(state="normal")
        self.issue = issue
        self._remember_users(issue)
        self._render()
        if self._on_loaded:
            self._on_loaded(self.issue_id, issue)

    def _remember_users(self, issue: Dict[str, Any]):
        users = self.lookups.setdefault("assigned_to_id", {})
        for ref in [issue.get("author"), issue.get("assigned_to")] + [j.get("user") for j in issue.get("journals") or []]:
            if ref and ref.get("id"):
                users[str(ref["id"])] = ref.get("name", "")

    def _render(self):
        issue = self.issue
        self._render_gen += 1
        self._photos.clear()
        self._attachments_by_name = {
            (a.get("filename") or "").lower(): a for a in issue.get("attachments") or []
        }

        self.lbl_subject.configure(text=f"#{issue.get('id')}  {issue.get('subject', '')}")
        self.lbl_meta.configure(
            text=f"{_name(issue.get('tracker'))} • {_name(issue.get('project'))} • dibuat oleh {_name(issue.get('author'))} "
                 f"{format_datetime(issue.get('created_on'))} • diperbarui {format_datetime(issue.get('updated_on'))}",
            text_color=COLORS["muted"]
        )

        self._render_detail(issue)
        self._render_history(issue.get("journals") or [], issue)
        self._render_children(issue.get("children") or [], issue.get("relations") or [])

    # ------------------------------------------------------------------
    # Detail tab (atribut, deskripsi, lampiran)
    # ------------------------------------------------------------------

    def _begin(self, textbox: ctk.CTkTextbox) -> tk.Text:
        textbox.configure(state="normal")
        self._renderers[textbox].clear_rules()
        textbox.delete("1.0", "end")
        return textbox._textbox

    def _render_detail(self, issue: Dict[str, Any]):
        inner = self._begin(self.text_desc)

        parent = issue.get("parent")
        overdue = bool(
            issue.get("due_date") and issue["due_date"] < date.today().isoformat()
            and not (issue.get("status") or {}).get("is_closed")
        )
        attributes = [
            ("Status", _name(issue.get("status")), False), ("Start date", format_date(issue.get("start_date")), False),
            ("Priority", _name(issue.get("priority")), False), ("Due date", format_date(issue.get("due_date")), overdue),
            ("Assignee", _name(issue.get("assigned_to")), False), ("Done", f"{issue.get('done_ratio', 0)}%", False),
            ("Category", _name(issue.get("category")), False),
            ("Estimated", f"{issue['estimated_hours']} jam" if issue.get("estimated_hours") else "-", False),
            ("Target version", _name(issue.get("fixed_version")), False),
            ("Spent time", f"{issue['spent_hours']} jam" if issue.get("spent_hours") else "-", False),
            ("Parent task", f"#{parent['id']}" if parent else "-", False), ("", "", False),
        ]
        for cf in issue.get("custom_fields") or []:
            value = cf.get("value")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value if v not in (None, ""))
            attributes.append((cf.get("name", ""), str(value) if value not in (None, "") else "-", False))
        if len(attributes) % 2:
            attributes.append(("", "", False))

        renderer = self._renderers[self.text_desc]
        for idx in range(0, len(attributes), 2):
            for col, (label, value, danger) in enumerate(attributes[idx:idx + 2]):
                if col:
                    inner.insert("end", "\t", "attrs")
                if not label:
                    continue
                inner.insert("end", f"{label}:", ("attrs", "attr_label"))
                inner.insert("end", "\t", "attrs")
                if label == "Parent task" and parent:
                    renderer._insert_link(value, ("attrs",), lambda i=parent["id"]: self._open_issue(i))
                else:
                    inner.insert("end", value, ("attrs", "danger") if danger else ("attrs",))
            inner.insert("end", "\n", "attrs")

        renderer.insert_rule()
        inner.insert("end", "Deskripsi\n", "section")
        description = (issue.get("description") or "").strip()
        if description:
            renderer.render(description, self.text_format)
        else:
            inner.insert("end", "Tidak ada deskripsi.\n", "muted")

        attachments = issue.get("attachments") or []
        if attachments:
            self._render_attachments(inner, attachments, description)
        self.text_desc.configure(state="disabled")

    def _render_attachments(self, inner: tk.Text, attachments: List[Dict[str, Any]], description: str):
        renderer = self._renderers[self.text_desc]
        inner.insert("end", "\n", "spacer")
        renderer.insert_rule()
        inner.insert("end", f"Lampiran ({len(attachments)})\n", "section")
        for attachment in attachments:
            url = attachment.get("content_url")
            name = attachment.get("filename", "file")
            if url:
                renderer._insert_link(name, (), lambda a=attachment: self._open_attachment(a))
            else:
                inner.insert("end", name)
            inner.insert(
                "end",
                f"   {_format_size(attachment.get('filesize') or 0)} • {_name(attachment.get('author'))} • "
                f"{format_datetime(attachment.get('created_on'))}\n",
                "small"
            )
            if attachment.get("description"):
                inner.insert("end", f"   {attachment['description']}\n", "small")

        # Thumbnail untuk gambar yang tidak sudah tampil inline di deskripsi
        lowered = unquote(description).lower()
        thumbs = [a for a in attachments if _is_image(a) and a.get("content_url") and (a.get("filename") or "").lower() not in lowered]
        if thumbs:
            inner.insert("end", "\n", "spacer")
            for attachment in thumbs:
                self._insert_image(inner, attachment["content_url"], attachment.get("filename", ""), THUMBNAIL_SIZE)
                inner.insert("end", "  ")
            inner.insert("end", "\n")

    # ------------------------------------------------------------------
    # Gambar
    # ------------------------------------------------------------------

    def _resolve_image_source(self, src: str) -> Optional[Dict[str, str]]:
        src = src.strip()
        name = unquote(src.rsplit("/", 1)[-1]).lower()
        attachment = self._attachments_by_name.get(unquote(src).lower()) or self._attachments_by_name.get(name)
        if attachment and attachment.get("content_url"):
            return {"url": attachment["content_url"], "name": attachment.get("filename", name)}
        if re.match(r"^(https?://|/)", src):
            return {"url": src, "name": unquote(urlparse(src).path.rsplit("/", 1)[-1]) or src}
        return None

    def _insert_inline_image(self, inner: tk.Text, src: str, alt: str):
        resolved = self._resolve_image_source(src)
        if not resolved:
            inner.insert("end", f"[gambar: {alt or src}]", "muted")
            return
        width = inner.winfo_width()
        max_width = width - 60 if width > 300 else 760
        inner.insert("end", "\n")
        self._insert_image(inner, resolved["url"], resolved["name"], (max_width, MAX_INLINE_HEIGHT))
        inner.insert("end", "\n")

    def _insert_image(self, inner: tk.Text, url: str, name: str, max_size: tuple):
        self._image_seq += 1
        tag = f"img_{self._image_seq}"
        gen = self._render_gen
        inner.insert("end", f"[memuat gambar {name}…]", ("small", tag))
        if url in self._image_cache:
            # Tunda sampai teks selesai ditulis agar indeks placeholder stabil
            self.after_idle(lambda: self._place_image(inner, tag, url, name, max_size, gen))
            return

        def worker():
            try:
                data = self.client.download(url)
            except RedmineError:
                data = None
            self.after(0, lambda: self._on_image_downloaded(inner, tag, url, name, max_size, gen, data))

        threading.Thread(target=worker, daemon=True).start()

    def _on_image_downloaded(self, inner, tag, url, name, max_size, gen, data: Optional[bytes]):
        if data is not None:
            self._image_cache[url] = data
        self._place_image(inner, tag, url, name, max_size, gen)

    def _place_image(self, inner: tk.Text, tag: str, url: str, name: str, max_size: tuple, gen: int):
        if gen != self._render_gen or not self.winfo_exists():
            return
        ranges = inner.tag_ranges(tag)
        if not ranges:
            return
        start, end = ranges[0], ranges[1]
        data = self._image_cache.get(url)
        state = inner.cget("state")
        inner.configure(state="normal")
        try:
            if data is None:
                raise ValueError("download failed")
            image = Image.open(BytesIO(data))
            image.load()
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._photos.append(photo)
            inner.delete(start, end)
            inner.image_create(start, image=photo, padx=2, pady=4)
            click_tag = f"{tag}_click"
            inner.tag_add(click_tag, start)
            inner.tag_bind(click_tag, "<Button-1>", lambda _e: self._open_image_bytes(url, name))
            inner.tag_bind(click_tag, "<Enter>", lambda _e: inner.configure(cursor="hand2"))
            inner.tag_bind(click_tag, "<Leave>", lambda _e: inner.configure(cursor=""))
        except Exception:
            inner.delete(start, end)
            inner.insert(start, f"[gambar tidak dapat ditampilkan: {name}]", "small")
        finally:
            inner.configure(state=state)

    def _open_image_bytes(self, url: str, name: str):
        """Buka gambar ukuran penuh dengan viewer bawaan OS."""
        data = self._image_cache.get(url)
        if data is None:
            self._open_url(url)
            return
        folder = Path(tempfile.gettempdir()) / "domba-redmine"
        folder.mkdir(exist_ok=True)
        safe_name = re.sub(r"[^\w.\-]+", "_", name) or "image"
        path = folder / f"{self.issue_id}_{safe_name}"
        path.write_bytes(data)
        self._open_local_file(path)

    def _open_attachment(self, attachment: Dict[str, Any]):
        url = attachment["content_url"]
        name = attachment.get("filename", "file")

        def worker():
            try:
                data = self.client.download(url, max_bytes=100 * 1024 * 1024)
            except RedmineError:
                self.after(0, lambda: webbrowser.open(url))
                return
            if _is_image(attachment):
                self._image_cache.setdefault(url, data)
            folder = Path(tempfile.gettempdir()) / "domba-redmine"
            folder.mkdir(exist_ok=True)
            path = folder / f"{self.issue_id}_{re.sub(r'[^\w.\-]+', '_', name)}"
            path.write_bytes(data)
            self.after(0, lambda: self._open_local_file(path))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _open_local_file(path: Path):
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            webbrowser.open(path.as_uri())

    def _open_url(self, url: str):
        webbrowser.open(self.client.resolve_url(url))

    def _open_issue(self, issue_id: int):
        if self._on_open_issue:
            self._on_open_issue(issue_id)

    # ------------------------------------------------------------------
    # Riwayat & subtask
    # ------------------------------------------------------------------

    def _set_tab_title(self, key: str, count: int):
        # CTkTabview tidak mendukung rename tab; perbarui teks tombol segmented-nya langsung
        button = self.tabview._segmented_button._buttons_dict.get(self._tab_names[key])
        if button is not None:
            button.configure(text=f"{self._tab_names[key]} ({count})" if count else self._tab_names[key])

    def _describe_detail(self, detail: Dict[str, Any], issue: Dict[str, Any]) -> str:
        prop = detail.get("property")
        name = detail.get("name", "")
        old, new = detail.get("old_value"), detail.get("new_value")
        if prop == "attachment":
            return f"File {'ditambahkan' if new else 'dihapus'}: {new or old}"
        if prop == "relation":
            return f"Relasi {name}: {'#' + str(new) if new else 'dihapus #' + str(old)}"
        if prop == "cf":
            label = next((cf.get("name") for cf in issue.get("custom_fields") or [] if str(cf.get("id")) == str(name)), f"Custom field {name}")
        else:
            label = FIELD_LABELS.get(name, name)
        if name == "description":
            return "Deskripsi diperbarui"

        mapping = self.lookups.get(name, {}) if prop != "cf" else {}
        old_text = mapping.get(str(old), str(old)) if old not in (None, "") else None
        new_text = mapping.get(str(new), str(new)) if new not in (None, "") else None
        if name.endswith("_id") and not mapping:
            old_text = f"#{old}" if old_text else None
            new_text = f"#{new}" if new_text else None
        if old_text and new_text:
            return f"{label} diubah dari {old_text} menjadi {new_text}"
        if new_text:
            return f"{label} diisi {new_text}"
        return f"{label} dihapus (sebelumnya {old_text})"

    def _render_history(self, journals: List[Dict[str, Any]], issue: Dict[str, Any]):
        self._set_tab_title("history", len(journals))
        inner = self._begin(self.text_history)
        renderer = self._renderers[self.text_history]
        if not journals:
            inner.insert("end", "Belum ada riwayat perubahan.", "muted")
        # Terbaru di atas (urutan dibalik dari API)
        for index, journal in enumerate(reversed(journals)):
            number = len(journals) - index
            inner.insert("end", f"#{number}  ", "muted")
            inner.insert("end", _name(journal.get("user")), "heading")
            inner.insert("end", f"  •  {format_datetime(journal.get('created_on'))}\n", "muted")
            for detail in journal.get("details") or []:
                inner.insert("end", f"  ▸ {self._describe_detail(detail, issue)}\n", "change")
            notes = (journal.get("notes") or "").strip()
            if notes:
                renderer.render(notes, self.text_format)
            renderer.insert_rule()
        self.text_history.configure(state="disabled")

    def _render_children(self, children: List[Dict[str, Any]], relations: List[Dict[str, Any]]):
        self._set_tab_title("children", len(children) + len(relations))
        inner = self._begin(self.text_children)
        renderer = self._renderers[self.text_children]
        if not children and not relations:
            inner.insert("end", "Tidak ada subtask atau relasi.", "muted")
        if children:
            inner.insert("end", "Subtask\n", "section")
            for child in children:
                renderer._insert_link(f"#{child['id']}", (), lambda i=child["id"]: self._open_issue(i))
                inner.insert("end", f"  {_name(child.get('tracker'))}: {child.get('subject', '')}\n")
        if relations:
            inner.insert("end", ("\n" if children else "") + "Relasi\n", "section")
            for relation in relations:
                other = relation["issue_to_id"] if relation.get("issue_id") == self.issue_id else relation.get("issue_id")
                inner.insert("end", f"{relation.get('relation_type', '').replace('_', ' ')}  ", "muted")
                renderer._insert_link(f"#{other}", (), lambda i=other: self._open_issue(i))
                inner.insert("end", "\n")
        self.text_children.configure(state="disabled")

    def open_in_browser(self):
        webbrowser.open(self.client.issue_url(self.issue_id))
