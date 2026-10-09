from pathlib import Path
import threading
from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk

from theme import COLORS
from icons import get_icon
from redmine_service import RedmineClient, RedmineError

DONE_RATIOS = ["0%", "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]


class RedmineEditTaskDialog(ctk.CTkToplevel):
    """Dialog resizable untuk mengedit Status, % Done, Assignee, serta mengunggah Lampiran (Attachment) ke task Redmine."""

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

        self.title(f"Edit Task #{self.issue_id}")
        self.geometry("560x540")
        self.minsize(500, 460)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - 560) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - 540) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_form()
        self._build_footer()

        # Keyboard shortcuts
        self.bind("<Control-s>", lambda _: self._save_changes())
        self.bind("<Command-s>", lambda _: self._save_changes())

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=64, corner_radius=0, border_width=1, border_color=COLORS["line"])
        header.grid(row=0, column=0, sticky="ew")
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
        if len(subj) > 70:
            subj = subj[:69] + "…"
        ctk.CTkLabel(
            left,
            text=subj,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

    def _build_form(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # 1. Properties Card (Status, % Done, Assignee)
        card_props = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        card_props.pack(fill="x", pady=(0, 12))
        card_props.grid_columnconfigure((0, 1), weight=1, uniform="fields")

        def label(text: str, row: int, col: int, colspan: int = 1):
            ctk.CTkLabel(
                card_props, text=text, font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["text"], anchor="w"
            ).grid(row=row, column=col, columnspan=colspan, sticky="w", padx=(16 if col == 0 else 8, 16), pady=(12 if row == 0 else 8, 4))

        def place(widget, row: int, col: int, colspan: int = 1, pady=(0, 10)):
            widget.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=(16 if col == 0 else 8, 16), pady=pady)

        # Status & % Done
        label("Status *", 0, 0)
        label("% Done *", 0, 1)

        status_vals = list(self.status_ids.keys()) or ["New"]
        current_status = (self.issue.get("status") or {}).get("name", "")
        self.opt_status = ctk.CTkOptionMenu(
            card_props, values=status_vals, height=34, corner_radius=8,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12), dynamic_resizing=False
        )
        self.opt_status.set(current_status if current_status in status_vals else status_vals[0])
        place(self.opt_status, 1, 0)

        current_done = f"{self.issue.get('done_ratio', 0)}%"
        self.opt_done = ctk.CTkOptionMenu(
            card_props, values=DONE_RATIOS, height=34, corner_radius=8,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12), dynamic_resizing=False
        )
        self.opt_done.set(current_done if current_done in DONE_RATIOS else "0%")
        place(self.opt_done, 1, 1)

        # Assignee (full width)
        label("Assignee", 2, 0, colspan=2)

        assignee_lookup = self.lookups.get("assigned_to_id", {})
        self._user_names_to_id = {name: int(uid) for uid, name in assignee_lookup.items() if str(uid).isdigit()}
        assignee_vals = ["(Tidak diubah)"] + list(self._user_names_to_id.keys())
        current_assignee = (self.issue.get("assigned_to") or {}).get("name", "")

        self.opt_assignee = ctk.CTkOptionMenu(
            card_props, values=assignee_vals, height=34, corner_radius=8,
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], button_color=COLORS["surface_hover"],
            button_hover_color=COLORS["line"], font=ctk.CTkFont(size=12), dynamic_resizing=False
        )
        self.opt_assignee.set(current_assignee if current_assignee in assignee_vals else assignee_vals[0])
        place(self.opt_assignee, 3, 0, colspan=2, pady=(0, 14))

        # 2. Files / Attachment Card
        card_files = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        card_files.pack(fill="x", pady=(0, 12))
        card_files.grid_columnconfigure(0, weight=1)

        header_files = ctk.CTkFrame(card_files, fg_color="transparent")
        header_files.pack(fill="x", padx=16, pady=(12, 6))
        header_files.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header_files, text="Lampiran File (Attachments)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["text"]
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header_files, text=" + Pilih File...", image=get_icon("paperclip", (13, 13), COLORS["text"]), compound="left",
            width=115, height=28, corner_radius=7, fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            text_color=COLORS["text"], border_width=1, border_color=COLORS["line"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self._pick_files
        ).grid(row=0, column=1, sticky="e")

        self.files_container = ctk.CTkFrame(card_files, fg_color="transparent")
        self.files_container.pack(fill="x", padx=16, pady=(0, 12))
        self._render_files_list()

        # 3. Notes / Catatan Perubahan Card
        card_notes = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS["line"])
        card_notes.pack(fill="x", pady=(0, 8))
        card_notes.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card_notes, text="Catatan / Komentar (Opsional)", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["text"]
        ).pack(anchor="w", padx=16, pady=(12, 4))

        self.txt_notes = ctk.CTkTextbox(
            card_notes, height=75, corner_radius=8, border_width=1, border_color=COLORS["line"],
            fg_color=COLORS["input_bg"], text_color=COLORS["text"], font=ctk.CTkFont(size=12)
        )
        self.txt_notes.pack(fill="x", padx=16, pady=(0, 14))

    def _pick_files(self):
        file_paths = filedialog.askopenfilenames(
            parent=self,
            title="Pilih File Lampiran",
            filetypes=[
                ("Semua File", "*.*"),
                ("Gambar (PNG, JPG, GIF)", "*.png;*.jpg;*.jpeg;*.gif;*.webp"),
                ("Dokumen (PDF, DOCX, TXT, ZIP)", "*.pdf;*.docx;*.txt;*.zip;*.log"),
            ]
        )
        if file_paths:
            for p in file_paths:
                path_obj = Path(p)
                if path_obj not in self._selected_files:
                    self._selected_files.append(path_obj)
            self._render_files_list()

    def _remove_file(self, path_obj: Path):
        if path_obj in self._selected_files:
            self._selected_files.remove(path_obj)
            self._render_files_list()

    def _render_files_list(self):
        for child in self.files_container.winfo_children():
            child.destroy()

        if not self._selected_files:
            ctk.CTkLabel(
                self.files_container, text="Belum ada file yang dipilih", font=ctk.CTkFont(size=11), text_color=COLORS["muted"]
            ).pack(anchor="w", pady=2)
            return

        for path in self._selected_files:
            row = ctk.CTkFrame(self.files_container, fg_color=COLORS["input_bg"], corner_radius=6, border_width=1, border_color=COLORS["line"])
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text="", image=get_icon("file", (13, 13), COLORS["accent"])).grid(row=0, column=0, padx=(8, 4), pady=4)

            # Format file size
            try:
                size_kb = path.stat().st_size / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            except Exception:
                size_str = ""

            info_text = f"{path.name}  ({size_str})" if size_str else path.name
            ctk.CTkLabel(
                row, text=info_text, font=ctk.CTkFont(size=11), text_color=COLORS["text"], anchor="w"
            ).grid(row=0, column=1, sticky="w", padx=4, pady=4)

            ctk.CTkButton(
                row, text="", image=get_icon("x", (11, 11), COLORS["muted"]), width=20, height=20,
                corner_radius=4, fg_color="transparent", hover_color=COLORS["surface_hover"],
                command=lambda p=path: self._remove_file(p)
            ).grid(row=0, column=2, padx=(2, 6), pady=4)

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=56, corner_radius=0, border_width=1, border_color=COLORS["line"])
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_error = ctk.CTkLabel(
            footer, text="", font=ctk.CTkFont(size=11), text_color=COLORS["danger"], anchor="w", wraplength=320, justify="left"
        )
        self.lbl_error.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=16, pady=10)

        self.btn_cancel = ctk.CTkButton(
            actions, text="Batal", width=80, height=34, corner_radius=8,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=12), command=self.destroy
        )
        self.btn_cancel.pack(side="left", padx=(0, 8))

        self.btn_save = ctk.CTkButton(
            actions, text=" Simpan Perubahan", image=get_icon("check", (14, 14), "#FFFFFF"), compound="left",
            width=145, height=34, corner_radius=8, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=12, weight="bold"), command=self._save_changes
        )
        self.btn_save.pack(side="left")

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

        # 3. Assignee
        assignee_name = self.opt_assignee.get()
        if assignee_name in self._user_names_to_id:
            updates["assigned_to_id"] = self._user_names_to_id[assignee_name]

        # 4. Notes
        notes = self.txt_notes.get("1.0", "end-1c").strip()
        if notes:
            updates["notes"] = notes

        files_to_upload = list(self._selected_files)

        self.btn_save.configure(state="disabled", text=" Menyimpan...")
        self.btn_cancel.configure(state="disabled")
        self.lbl_error.configure(text="")

        def worker():
            try:
                # Upload files jika ada
                if files_to_upload:
                    uploads_payload = []
                    for idx, fpath in enumerate(files_to_upload):
                        self.after(0, lambda i=idx+1, total=len(files_to_upload): self.lbl_error.configure(
                            text=f"Mengunggah lampiran ({i}/{total})...", text_color=COLORS["muted"]
                        ))
                        upload_res = self.client.upload_file(fpath)
                        uploads_payload.append({
                            "token": upload_res["token"],
                            "filename": upload_res["filename"],
                            "content_type": upload_res.get("content_type", "application/octet-stream"),
                        })
                    updates["uploads"] = uploads_payload

                self.after(0, lambda: self.lbl_error.configure(text="Memperbarui task...", text_color=COLORS["muted"]))
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
