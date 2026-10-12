from pathlib import Path
import threading
from tkinter import filedialog, messagebox
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk

from theme import COLORS, get_color
from icons import get_icon
from redmine_service import RedmineClient, RedmineError
from redmine_markup import MarkupRenderer

DONE_RATIOS = ["0%", "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class RedmineEditTaskDialog(ctk.CTkToplevel):
    """Dialog edit task bergaya Redmine web dengan toolbar formatting Notes, Preview, Lampiran, dan smooth scrolling."""

    def __init__(
        self,
        parent: Any,
        client: RedmineClient,
        issue: Dict[str, Any],
        lookups: Dict[str, Dict[str, str]],
        status_ids: Dict[str, int],
        priority_ids: Dict[str, int],
        on_saved: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent, fg_color=COLORS["window"])
        self.client = client
        self.issue = issue
        self.issue_id = issue.get("id", 0)
        self.lookups = lookups
        self.status_ids = status_ids
        self.priority_ids = priority_ids
        self.on_saved = on_saved
        self._selected_files: List[Path] = []
        self._file_descriptions: Dict[Path, str] = {}
        self._mode = "edit"  # 'edit' atau 'preview'

        self.title(f"Edit Task #{self.issue_id}")
        self.geometry("640x700")
        self.minsize(580, 520)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        # Posisikan dialog di tengah horizontal dan agak ke atas secara vertikal
        self.update_idletasks()
        try:
            p_w = parent.winfo_width()
            p_h = parent.winfo_height()
            p_x = parent.winfo_rootx()
            p_y = parent.winfo_rooty()

            x = p_x + (p_w - 640) // 2
            # Geser agak ke atas (-75 px) agar lebih proporsional dan tidak menempel di bawah
            y = max(35, p_y + (p_h - 700) // 2 - 75)
            self.geometry(f"+{max(0, x)}+{max(30, y)}")
        except Exception:
            pass

        # Tata letak: Header di atas, Footer di bawah (selalu tampak), Form scrollable di tengah
        self._build_header()
        self._build_footer()
        self._build_form()

        # Setup smooth & fast mousewheel scrolling across all components
        self.after(60, lambda: self._bind_mousewheel_recursive(self.scroll_frame))

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=64, corner_radius=0, border_width=1, border_color=COLORS["line"])
        header.pack(side="top", fill="x")
        header.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=20, pady=10)

        ctk.CTkLabel(
            left,
            text=f"Edit Task #{self.issue_id}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        ).pack(anchor="w")

        subj = (self.issue.get("subject") or "").strip()
        tracker_name = ((self.issue.get("tracker") or {}).get("name") or "").strip()
        header_text = f"[{tracker_name}] {subj}" if tracker_name else subj
        if len(header_text) > 75:
            header_text = header_text[:74] + "…"
        ctk.CTkLabel(
            left,
            text=header_text,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=540,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

    # ------------------------------------------------------------------
    # Form Body (Scrollable Frame)
    # ------------------------------------------------------------------

    def _build_form(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(side="top", fill="both", expand=True, padx=16, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # 1. Properties Card (Status, % Done, Priority, Assignee)
        self._build_properties_section()

        # 2. Notes Section (Redmine Styled with toolbar & preview)
        self._build_notes_section()

        # 3. Files / Attachments Section (Redmine Styled)
        self._build_files_section()

    def _build_properties_section(self):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        card.pack(fill="x", pady=(0, 12))
        card.grid_columnconfigure((0, 1), weight=1, uniform="props")

        def label(text: str, row: int, col: int):
            ctk.CTkLabel(
                card, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["text"], anchor="w"
            ).grid(row=row, column=col, sticky="w", padx=(16 if col == 0 else 8, 16), pady=(12 if row == 0 else 6, 4))

        def place(widget, row: int, col: int, pady=(0, 8)):
            widget.grid(row=row, column=col, sticky="ew", padx=(16 if col == 0 else 8, 16), pady=pady)

        # Row 0: Status & % Done
        label("Status *", 0, 0)
        label("% Done *", 0, 1)

        status_vals = list(self.status_ids.keys()) or ["New"]
        current_status = (self.issue.get("status") or {}).get("name", "")
        self.opt_status = ctk.CTkOptionMenu(
            card, values=status_vals, height=34, corner_radius=8,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12), dynamic_resizing=False
        )
        self.opt_status.set(current_status if current_status in status_vals else status_vals[0])
        place(self.opt_status, 1, 0)

        current_done = f"{self.issue.get('done_ratio', 0)}%"
        self.opt_done = ctk.CTkOptionMenu(
            card, values=DONE_RATIOS, height=34, corner_radius=8,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12), dynamic_resizing=False
        )
        self.opt_done.set(current_done if current_done in DONE_RATIOS else "0%")
        place(self.opt_done, 1, 1)

        # Row 1: Priority & Assignee
        label("Prioritas", 2, 0)
        label("Assignee", 2, 1)

        priority_vals = ["(Tidak diubah)"] + list(self.priority_ids.keys())
        current_priority = (self.issue.get("priority") or {}).get("name", "")
        self.opt_priority = ctk.CTkOptionMenu(
            card, values=priority_vals, height=34, corner_radius=8,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12), dynamic_resizing=False
        )
        self.opt_priority.set(current_priority if current_priority in priority_vals else priority_vals[0])
        place(self.opt_priority, 3, 0, pady=(0, 14))

        assignee_lookup = self.lookups.get("assigned_to_id", {})
        self._user_names_to_id = {name: int(uid) for uid, name in assignee_lookup.items() if str(uid).isdigit()}
        assignee_vals = ["(Tidak diubah)"] + list(self._user_names_to_id.keys())
        current_assignee = (self.issue.get("assigned_to") or {}).get("name", "")
        self.opt_assignee = ctk.CTkOptionMenu(
            card, values=assignee_vals, height=34, corner_radius=8,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12), dynamic_resizing=False
        )
        self.opt_assignee.set(current_assignee if current_assignee in assignee_vals else assignee_vals[0])
        place(self.opt_assignee, 3, 1, pady=(0, 14))

    # ------------------------------------------------------------------
    # Notes Section (Redmine Styled)
    # ------------------------------------------------------------------

    def _build_notes_section(self):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        card.pack(fill="x", pady=(0, 12))
        card.grid_columnconfigure(0, weight=1)

        # Fieldset Header: Notes
        lbl_head = ctk.CTkLabel(card, text="Notes", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text"])
        lbl_head.pack(anchor="w", padx=16, pady=(12, 6))

        # Toolbar Frame
        toolbar = ctk.CTkFrame(card, fg_color=COLORS["input_bg"], corner_radius=6, border_width=1, border_color=COLORS["line"])
        toolbar.pack(fill="x", padx=16, pady=(0, 6))

        # Mode buttons: Edit & Preview
        self.btn_mode_edit = ctk.CTkButton(
            toolbar, text="Edit", width=46, height=24, corner_radius=4,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["surface_active"],
            text_color=COLORS["text"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self._switch_to_edit
        )
        self.btn_mode_edit.pack(side="left", padx=(4, 2), pady=3)

        self.btn_mode_preview = ctk.CTkButton(
            toolbar, text="Preview", width=56, height=24, corner_radius=4,
            fg_color="transparent", hover_color=COLORS["surface_hover"],
            text_color=COLORS["muted"], font=ctk.CTkFont(size=11),
            command=self._switch_to_preview
        )
        self.btn_mode_preview.pack(side="left", padx=(0, 8), pady=3)

        # Separator line
        sep = ctk.CTkFrame(toolbar, width=1, height=18, fg_color=COLORS["line"])
        sep.pack(side="left", padx=(0, 6), pady=3)

        # Formatting buttons container (hidden when in preview mode)
        self.formatting_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        self.formatting_frame.pack(side="left", fill="x", expand=True)

        tool_buttons = [
            ("B", "Tebal (*teks*)", lambda: self._wrap_markup("*", "*", "teks")),
            ("I", "Miring (_teks_)", lambda: self._wrap_markup("_", "_", "teks")),
            ("U", "Garis Bawah (+teks+)", lambda: self._wrap_markup("+", "+", "teks")),
            ("S", "Coret (-teks-)", lambda: self._wrap_markup("-", "-", "teks")),
            ('"', "Kutipan (bq. teks)", lambda: self._prefix_markup("bq. ", "Kutipan")),
            ("@", "Inline Code (@kode@)", lambda: self._wrap_markup("@", "@", "kode")),
            ("H1", "Judul 1 (h1. Judul)", lambda: self._prefix_markup("h1. ", "Judul 1")),
            ("H2", "Judul 2 (h2. Subjudul)", lambda: self._prefix_markup("h2. ", "Judul 2")),
            ("H3", "Judul 3 (h3. Subjudul)", lambda: self._prefix_markup("h3. ", "Judul 3")),
            ("•", "Daftar Poin (* Poin)", lambda: self._prefix_markup("* ", "Poin")),
            ("1.", "Daftar Nomor (# Nomor)", lambda: self._prefix_markup("# ", "Langkah 1")),
            ("←", "Kurangi Indent", self._outdent_markup),
            ("→", "Tambah Indent", self._indent_markup),
            ("pre", "Preformatted (<pre>...</pre>)", lambda: self._wrap_markup("<pre>\n", "\n</pre>", "blok kode")),
            ("<>", "Blok Kode", lambda: self._wrap_markup("<code class=\"text\">\n", "\n</code>", "kode program")),
            ("🔗", "Tautan Link", self._insert_link),
            ("🖼", "Gambar (!gambar.png!)", lambda: self._wrap_markup("!", "!", "nama_file.png")),
            ("?", "Panduan Format Redmine", self._show_formatting_help),
        ]

        for text, tooltip, cmd in tool_buttons:
            btn = ctk.CTkButton(
                self.formatting_frame, text=text, width=24, height=22, corner_radius=3,
                fg_color="transparent", hover_color=COLORS["surface_hover"],
                text_color=COLORS["text"], font=ctk.CTkFont(size=11, weight="bold" if len(text) <= 2 else "normal"),
                command=cmd
            )
            btn.pack(side="left", padx=1, pady=3)

        # Container for Editor & Preview (stacked)
        self.notes_body = ctk.CTkFrame(card, fg_color="transparent")
        self.notes_body.pack(fill="x", padx=16, pady=(0, 8))
        self.notes_body.grid_columnconfigure(0, weight=1)

        # 1. Textarea Editor
        self.txt_notes = ctk.CTkTextbox(
            self.notes_body, height=150, corner_radius=6, border_width=1, border_color=COLORS["line"],
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], font=ctk.CTkFont(family="Consolas" if tk.TkVersion >= 8.6 else "TkFixedFont", size=12),
            wrap="word"
        )
        self.txt_notes.grid(row=0, column=0, sticky="nsew")

        # 2. Preview Widget (read-only tk.Text dengan MarkupRenderer)
        self.preview_container = ctk.CTkFrame(self.notes_body, fg_color=COLORS["input_bg"], corner_radius=6, border_width=1, border_color=COLORS["line"], height=150)
        self.preview_container.grid_columnconfigure(0, weight=1)
        self.preview_container.grid_rowconfigure(0, weight=1)

        self.txt_preview = tk.Text(
            self.preview_container,
            bg=get_color("input_bg"),
            fg=get_color("text"),
            bd=0,
            highlightthickness=0,
            padx=12,
            pady=10,
            wrap="word",
            font=("Segoe UI", 10),
            height=8,
        )
        self.txt_preview.grid(row=0, column=0, sticky="nsew")
        self.renderer = MarkupRenderer(self.txt_preview)
        self._apply_renderer_tags()

        # Checkbox Private Notes
        self.chk_private = ctk.CTkCheckBox(
            card,
            text="Private notes",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text"],
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            border_color=COLORS["line"],
        )
        self.chk_private.pack(anchor="w", padx=16, pady=(0, 14))

    def _apply_renderer_tags(self):
        colors = {
            "text": get_color("text"), "muted": get_color("muted"), "link": get_color("accent_text"),
            "line": get_color("line"), "code_bg": get_color("surface_hover"), "code_fg": get_color("danger_text"),
        }
        self.renderer.configure_tags(colors)

    def _switch_to_edit(self):
        if self._mode == "edit":
            return
        self._mode = "edit"
        self.btn_mode_edit.configure(fg_color=COLORS["surface_hover"], text_color=COLORS["text"], font=ctk.CTkFont(size=11, weight="bold"))
        self.btn_mode_preview.configure(fg_color="transparent", text_color=COLORS["muted"], font=ctk.CTkFont(size=11))
        self.formatting_frame.pack(side="left", fill="x", expand=True)

        self.preview_container.grid_remove()
        self.txt_notes.grid()
        self.txt_notes.focus_set()
        self.after(30, lambda: self._bind_mousewheel_recursive(self.scroll_frame))

    def _switch_to_preview(self):
        if self._mode == "preview":
            return
        self._mode = "preview"
        self.btn_mode_preview.configure(fg_color=COLORS["surface_hover"], text_color=COLORS["text"], font=ctk.CTkFont(size=11, weight="bold"))
        self.btn_mode_edit.configure(fg_color="transparent", text_color=COLORS["muted"], font=ctk.CTkFont(size=11))
        self.formatting_frame.pack_forget()

        # Render preview
        raw_text = self.txt_notes.get("1.0", "end-1c").strip()
        self.txt_preview.configure(state="normal")
        self.txt_preview.delete("1.0", "end")
        self.renderer.clear_rules()
        if not raw_text:
            self.txt_preview.insert("end", "(Belum ada catatan yang ditulis)", "muted")
        else:
            self._apply_renderer_tags()
            self.renderer.render(raw_text, "auto")
        self.txt_preview.configure(state="disabled")

        self.txt_notes.grid_remove()
        self.preview_container.grid(row=0, column=0, sticky="nsew")
        self.after(30, lambda: self._bind_mousewheel_recursive(self.scroll_frame))

    # Formatting helper actions
    def _wrap_markup(self, prefix: str, suffix: str, placeholder: str):
        self._switch_to_edit()
        inner: tk.Text = self.txt_notes._textbox
        try:
            sel_first = inner.index("sel.first")
            sel_last = inner.index("sel.last")
            selected = inner.get(sel_first, sel_last)
            inner.delete(sel_first, sel_last)
            inner.insert(sel_first, f"{prefix}{selected}{suffix}")
            inner.mark_set("insert", f"{sel_first}+{len(prefix)+len(selected)+len(suffix)}c")
        except tk.TclError:
            cursor = inner.index("insert")
            inner.insert(cursor, f"{prefix}{placeholder}{suffix}")
            inner.mark_set("insert", f"{cursor}+{len(prefix)}c")
            inner.tag_add("sel", f"{cursor}+{len(prefix)}c", f"{cursor}+{len(prefix)+len(placeholder)}c")
        inner.focus_set()

    def _prefix_markup(self, prefix: str, placeholder: str):
        self._switch_to_edit()
        inner: tk.Text = self.txt_notes._textbox
        try:
            sel_first = inner.index("sel.first")
            sel_last = inner.index("sel.last")
            selected = inner.get(sel_first, sel_last)
            lines = selected.split("\n")
            new_text = "\n".join(f"{prefix}{l}" if l.strip() else l for l in lines)
            inner.delete(sel_first, sel_last)
            inner.insert(sel_first, new_text)
        except tk.TclError:
            cursor = inner.index("insert")
            line_start = inner.index(f"{cursor} linestart")
            inner.insert(line_start, prefix)
        inner.focus_set()

    def _indent_markup(self):
        self._switch_to_edit()
        inner: tk.Text = self.txt_notes._textbox
        try:
            sel_first = inner.index("sel.first")
            sel_last = inner.index("sel.last")
            selected = inner.get(sel_first, sel_last)
            lines = selected.split("\n")
            new_lines = []
            for l in lines:
                if l.startswith("* "):
                    new_lines.append(f"** {l[2:]}")
                elif l.startswith("# "):
                    new_lines.append(f"## {l[2:]}")
                else:
                    new_lines.append(f"  {l}")
            inner.delete(sel_first, sel_last)
            inner.insert(sel_first, "\n".join(new_lines))
        except tk.TclError:
            inner.insert("insert", "  ")
        inner.focus_set()

    def _outdent_markup(self):
        self._switch_to_edit()
        inner: tk.Text = self.txt_notes._textbox
        try:
            sel_first = inner.index("sel.first")
            sel_last = inner.index("sel.last")
            selected = inner.get(sel_first, sel_last)
            lines = selected.split("\n")
            new_lines = []
            for l in lines:
                if l.startswith("** "):
                    new_lines.append(f"* {l[3:]}")
                elif l.startswith("## "):
                    new_lines.append(f"# {l[3:]}")
                elif l.startswith("  "):
                    new_lines.append(l[2:])
                elif l.startswith(" "):
                    new_lines.append(l[1:])
                else:
                    new_lines.append(l)
            inner.delete(sel_first, sel_last)
            inner.insert(sel_first, "\n".join(new_lines))
        except tk.TclError:
            pass
        inner.focus_set()

    def _insert_link(self):
        self._switch_to_edit()
        inner: tk.Text = self.txt_notes._textbox
        try:
            sel_first = inner.index("sel.first")
            sel_last = inner.index("sel.last")
            selected = inner.get(sel_first, sel_last)
            inner.delete(sel_first, sel_last)
            inner.insert(sel_first, f'"{selected}":https://example.com')
        except tk.TclError:
            inner.insert("insert", '"Teks Link":https://example.com')
        inner.focus_set()

    def _show_formatting_help(self):
        guide = (
            "Panduan Format Teks Redmine:\n\n"
            "• Tebal: *teks* atau **teks**\n"
            "• Miring: _teks_\n"
            "• Garis Bawah: +teks+\n"
            "• Coret: -teks- atau ~~teks~~\n"
            "• Kutipan: bq. Kalimat kutipan\n"
            "• Inline Code: @kode_program@\n"
            "• Judul: h1. Judul Utama, h2. Subjudul\n"
            "• Daftar Poin: * Poin Satu\n"
            "• Daftar Angka: # Langkah Satu\n"
            "• Link: \"Label\":https://url.com atau [Label](https://url.com)\n"
            "• Task Redmine: #1234\n"
            "• Gambar: !nama_file.png!\n"
            "• Blok Kode: <pre>isi kode</pre>"
        )
        messagebox.showinfo("Bantuan Format Redmine", guide, parent=self)

    # ------------------------------------------------------------------
    # Files Section (Redmine Styled)
    # ------------------------------------------------------------------

    def _build_files_section(self):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        card.pack(fill="x", pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)

        # Header: Files
        ctk.CTkLabel(card, text="Files", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(12, 6))

        # Action bar: [Choose Files] + Status label + (Maximum size: 5 MB)
        action_bar = ctk.CTkFrame(card, fg_color="transparent")
        action_bar.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkButton(
            action_bar, text="Choose Files", width=105, height=28, corner_radius=6,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            text_color=COLORS["text"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11, weight="bold"), command=self._pick_files
        ).pack(side="left", padx=(0, 10))

        self.lbl_file_count = ctk.CTkLabel(action_bar, text="No file chosen", font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"])
        self.lbl_file_count.pack(side="left")

        ctk.CTkLabel(action_bar, text="(Maximum size: 5 MB)", font=ctk.CTkFont(size=11), text_color=COLORS["muted"]).pack(side="right")

        # Container list file yang dipilih
        self.files_container = ctk.CTkFrame(card, fg_color="transparent")
        self.files_container.pack(fill="x", padx=16, pady=(0, 12))
        self._render_files_list()

    def _pick_files(self):
        file_paths = filedialog.askopenfilenames(
            parent=self,
            title="Pilih File Lampiran",
            filetypes=[
                ("Semua File", "*.*"),
                ("Gambar (PNG, JPG, GIF, WebP)", "*.png;*.jpg;*.jpeg;*.gif;*.webp"),
                ("Dokumen (PDF, DOCX, TXT, ZIP, Log)", "*.pdf;*.docx;*.txt;*.zip;*.log;*.tar;*.gz"),
            ]
        )
        if file_paths:
            over_limit_files = []
            for p in file_paths:
                path_obj = Path(p)
                try:
                    if path_obj.stat().st_size > MAX_FILE_SIZE_BYTES:
                        over_limit_files.append(path_obj.name)
                except Exception:
                    pass
                if path_obj not in self._selected_files:
                    self._selected_files.append(path_obj)

            if over_limit_files:
                messagebox.showwarning(
                    "Peringatan Ukuran File",
                    f"File berikut melebihi batas 5 MB:\n• " + "\n• ".join(over_limit_files) +
                    "\n\nServer Redmine mungkin menolak berkas yang melebihi batas upload.",
                    parent=self
                )
            self._render_files_list()

    def _remove_file(self, path_obj: Path):
        if path_obj in self._selected_files:
            self._selected_files.remove(path_obj)
            self._file_descriptions.pop(path_obj, None)
            self._render_files_list()

    def _render_files_list(self):
        for child in self.files_container.winfo_children():
            child.destroy()

        count = len(self._selected_files)
        if count == 0:
            self.lbl_file_count.configure(text="No file chosen", text_color=COLORS["text_secondary"])
            return

        self.lbl_file_count.configure(text=f"{count} file dipilih", text_color=COLORS["text"])

        for path in self._selected_files:
            row = ctk.CTkFrame(self.files_container, fg_color=COLORS["input_bg"], corner_radius=6, border_width=1, border_color=COLORS["line"])
            row.pack(fill="x", pady=3)
            row.grid_columnconfigure(1, weight=1)

            # Icon
            ctk.CTkLabel(row, text="", image=get_icon("file", (14, 14), COLORS["accent"])).grid(row=0, column=0, padx=(8, 4), pady=6)

            # File name and size
            try:
                size_kb = path.stat().st_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                is_oversized = path.stat().st_size > MAX_FILE_SIZE_BYTES
            except Exception:
                size_str = ""
                is_oversized = False

            info_text = f"{path.name} ({size_str})" if size_str else path.name
            ctk.CTkLabel(
                row, text=info_text, font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["danger"] if is_oversized else COLORS["text"], anchor="w"
            ).grid(row=0, column=1, sticky="w", padx=4, pady=6)

            # Optional description entry (seperti input description di Redmine)
            desc_entry = ctk.CTkEntry(
                row, height=26, corner_radius=5, font=ctk.CTkFont(size=11),
                placeholder_text="Keterangan opsional (deskripsi lampiran)...",
                fg_color=COLORS["surface"], text_color=COLORS["text"], border_width=1, border_color=COLORS["line"]
            )
            desc_entry.grid(row=0, column=2, sticky="ew", padx=(4, 6), pady=6)
            if path in self._file_descriptions:
                desc_entry.insert(0, self._file_descriptions[path])

            def on_desc_change(event, p=path, ent=desc_entry):
                self._file_descriptions[p] = ent.get()

            desc_entry.bind("<KeyRelease>", on_desc_change)

            # Remove button
            ctk.CTkButton(
                row, text="", image=get_icon("x", (12, 12), COLORS["muted"]), width=24, height=24,
                corner_radius=4, fg_color="transparent", hover_color=COLORS["surface_hover"],
                command=lambda p=path: self._remove_file(p)
            ).grid(row=0, column=3, padx=(2, 6), pady=6)

        # Rebind mousewheel scrolling pada widget baru
        self.after(30, lambda: self._bind_mousewheel_recursive(self.files_container))

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=60, corner_radius=0, border_width=1, border_color=COLORS["line"])
        footer.pack(side="bottom", fill="x")
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_error = ctk.CTkLabel(
            footer, text="", font=ctk.CTkFont(size=11), text_color=COLORS["danger"], anchor="w", wraplength=340, justify="left"
        )
        self.lbl_error.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=16, pady=12)

        self.btn_cancel = ctk.CTkButton(
            actions, text="Batal", width=80, height=34, corner_radius=8,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=12), command=self.destroy
        )
        self.btn_cancel.pack(side="left", padx=(0, 8))

        self.btn_save = ctk.CTkButton(
            actions, text=" Simpan Perubahan", image=get_icon("check", (14, 14), "#FFFFFF"), compound="left",
            width=150, height=34, corner_radius=8, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=12, weight="bold"), command=self._save_changes
        )
        self.btn_save.pack(side="left")

    # ------------------------------------------------------------------
    # Smooth Mousewheel Scrolling (Cepat & Responsif)
    # ------------------------------------------------------------------

    def _bind_mousewheel_recursive(self, widget: Any):
        """Bind mousewheel scroll ke semua child widget secara rekursif agar dapat di-scroll dengan cepat dan mulus."""
        try:
            canvas = getattr(self.scroll_frame, "_parent_canvas", None)
            if not canvas or not canvas.winfo_exists():
                return

            def _scroll(event):
                try:
                    if not canvas.winfo_exists():
                        return
                    if event.delta:
                        # Windows mousewheel (delta biasanya ±120).
                        # Langkah 40 pixel per notch membuat scrolling sangat responsif & cepat
                        delta_pixels = -int(event.delta / 3)
                        if delta_pixels == 0:
                            delta_pixels = -20 if event.delta > 0 else 20
                        canvas.yview_scroll(delta_pixels, "units")
                    elif event.num == 4:
                        canvas.yview_scroll(-35, "units")
                    elif event.num == 5:
                        canvas.yview_scroll(35, "units")
                except Exception:
                    pass
                return "break"

            # Bind pada root window dialog juga
            self.bind("<MouseWheel>", _scroll, add="+")
            self.bind("<Button-4>", _scroll, add="+")
            self.bind("<Button-5>", _scroll, add="+")

            # Untuk text editor (txt_notes), scroll canvas jika teks tidak meluap
            is_inner_textbox = hasattr(widget, "yview") and isinstance(widget, (tk.Text, tk.Listbox))
            if is_inner_textbox:
                def _textbox_scroll(event):
                    try:
                        first, last = widget.yview()
                        # Jika teks belum meluap vertikal, teruskan ke canvas form
                        if first <= 0.001 and last >= 0.999:
                            _scroll(event)
                            return "break"
                    except Exception:
                        pass
                widget.bind("<MouseWheel>", _textbox_scroll, add="+")
                widget.bind("<Button-4>", _textbox_scroll, add="+")
                widget.bind("<Button-5>", _textbox_scroll, add="+")
            else:
                widget.bind("<MouseWheel>", _scroll, add="+")
                widget.bind("<Button-4>", _scroll, add="+")
                widget.bind("<Button-5>", _scroll, add="+")

            for child in widget.winfo_children():
                self._bind_mousewheel_recursive(child)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Save & Submit
    # ------------------------------------------------------------------

    def _save_changes(self):
        updates: Dict[str, Any] = {}

        # 1. Status
        status_name = self.opt_status.get()
        if status_name in self.status_ids:
            updates["status_id"] = self.status_ids[status_name]

        # 2. % Done
        done_str = self.opt_done.get().replace("%", "").strip()
        if done_str.isdigit():
            updates["done_ratio"] = int(done_str)

        # 3. Priority
        prio_name = self.opt_priority.get()
        if prio_name in self.priority_ids:
            updates["priority_id"] = self.priority_ids[prio_name]

        # 4. Assignee
        assignee_name = self.opt_assignee.get()
        if assignee_name in self._user_names_to_id:
            updates["assigned_to_id"] = self._user_names_to_id[assignee_name]

        # 5. Notes & Private notes
        notes = self.txt_notes.get("1.0", "end-1c").strip()
        if notes:
            updates["notes"] = notes
            if self.chk_private.get():
                updates["private_notes"] = True

        files_to_upload = list(self._selected_files)
        descriptions = dict(self._file_descriptions)

        self.btn_save.configure(state="disabled", text=" Menyimpan...")
        self.btn_cancel.configure(state="disabled")
        self.lbl_error.configure(text="")

        def worker():
            try:
                # Upload lampiran jika ada
                if files_to_upload:
                    uploads_payload = []
                    for idx, fpath in enumerate(files_to_upload):
                        self.after(0, lambda i=idx+1, total=len(files_to_upload): self.lbl_error.configure(
                            text=f"Mengunggah lampiran ({i}/{total})...", text_color=COLORS["muted"]
                        ))
                        upload_res = self.client.upload_file(fpath)
                        item = {
                            "token": upload_res["token"],
                            "filename": upload_res["filename"],
                            "content_type": upload_res.get("content_type", "application/octet-stream"),
                        }
                        desc = descriptions.get(fpath, "").strip()
                        if desc:
                            item["description"] = desc
                        uploads_payload.append(item)
                    updates["uploads"] = uploads_payload

                self.after(0, lambda: self.lbl_error.configure(text="Memperbarui task Redmine...", text_color=COLORS["muted"]))
                self.client.update_issue(self.issue_id, updates)
                self.after(0, self._on_success)
            except RedmineError as err:
                msg = str(err)
                self.after(0, lambda: self._on_error(msg))
            except Exception as err:
                msg = f"Terjadi kesalahan: {err}"
                self.after(0, lambda: self._on_error(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self):
        if not self.winfo_exists():
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()

    def _on_error(self, message: str):
        if not self.winfo_exists():
            return
        self.btn_save.configure(state="normal", text=" Simpan Perubahan")
        self.btn_cancel.configure(state="normal")
        self.lbl_error.configure(text=message, text_color=COLORS["danger"])
