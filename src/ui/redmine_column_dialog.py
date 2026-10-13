import tkinter as tk
from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk

from theme import COLORS
from icons import get_icon


class RedmineColumnSettingsDialog(ctk.CTkToplevel):
    """Dialog modal untuk mengatur visibilitas dan urutan kolom pada tabel task Redmine."""

    def __init__(
        self,
        parent: Any,
        all_columns: Dict[str, Any],
        visible_columns: List[str],
        default_columns: List[str],
        on_save: Callable[[List[str]], None],
    ):
        super().__init__(parent, fg_color=COLORS["window"])
        self.all_columns = all_columns
        self.default_columns = list(default_columns)
        self.on_save = on_save

        self.title("Pengaturan Kolom Tabel")
        self.geometry("490x600")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Build initial order: active columns in their current order, followed by hidden columns
        active_set = set(visible_columns)
        self._order: List[str] = [k for k in visible_columns if k in all_columns]
        for k in all_columns:
            if k not in active_set:
                self._order.append(k)

        # Boolean vars for each column checkbox
        self._vars: Dict[str, ctk.BooleanVar] = {}
        for k in all_columns:
            self._vars[k] = ctk.BooleanVar(value=(k in active_set))

        self._row_frames: List[ctk.CTkFrame] = []

        self._center_window(parent)
        self._setup_ui()

        self.bind("<Escape>", lambda _: self.destroy())

    def _center_window(self, parent: Any):
        try:
            self.update_idletasks()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            w, h = 490, 600
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _setup_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=18)

        # 1. Header
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text="",
            image=get_icon("table", (20, 20), COLORS["accent"]),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            title_row,
            text="Atur Kolom Tabel",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="Pilih kolom yang ingin ditampilkan pada daftar task dan gunakan tombol panah (▲ / ▼) untuk menyusun urutannya.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11),
            justify="left",
            wraplength=440,
        ).pack(anchor="w", pady=(4, 0))

        # 2. Toolbar (Pilih Semua, Default, Counter)
        toolbar = ctk.CTkFrame(main, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            toolbar,
            text="Pilih Semua",
            width=85,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._select_all,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            toolbar,
            text="Default",
            width=70,
            height=28,
            corner_radius=6,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._reset_default,
        ).pack(side="left")

        self.lbl_counter = ctk.CTkLabel(
            toolbar,
            text="",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=11),
        )
        self.lbl_counter.pack(side="right")

        # 3. List of Columns inside ScrollableFrame
        self.scroll_frame = ctk.CTkScrollableFrame(
            main,
            fg_color=COLORS["input_bg"],
            border_width=1,
            border_color=COLORS["line"],
            corner_radius=8,
            height=370,
        )
        self.scroll_frame.pack(fill="both", expand=True, pady=(0, 12))

        # 4. Status / Warning
        self.lbl_warning = ctk.CTkLabel(
            main,
            text="",
            text_color=COLORS["danger"],
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.lbl_warning.pack(fill="x", pady=(0, 4))

        # 5. Bottom Actions
        actions = ctk.CTkFrame(main, fg_color="transparent")
        actions.pack(fill="x", side="bottom")

        ctk.CTkButton(
            actions,
            text="Batal",
            width=80,
            height=32,
            corner_radius=8,
            fg_color=COLORS["surface"],
            hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=12),
            command=self.destroy,
        ).pack(side="left")

        self.btn_save = ctk.CTkButton(
            actions,
            text=" Simpan & Terapkan",
            image=get_icon("check", (14, 14), "#FFFFFF"),
            compound="left",
            width=150,
            height=32,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save,
        )
        self.btn_save.pack(side="right")

        self._render_column_list()
        self._update_counter()

    def _render_column_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        total = len(self._order)
        for idx, key in enumerate(self._order):
            col_info = self.all_columns.get(key)
            if not col_info:
                continue

            # col_info: (label, width, anchor, stretch, sort_key, title, extractor)
            label = col_info[0]
            title = col_info[5] if len(col_info) > 5 else label

            row = ctk.CTkFrame(
                self.scroll_frame,
                fg_color=COLORS["surface"],
                border_width=1,
                border_color=COLORS["line"],
                corner_radius=6,
                height=38,
            )
            row.pack(fill="x", pady=2, padx=2)
            row.pack_propagate(False)

            # Checkbox
            var = self._vars[key]
            cb = ctk.CTkCheckBox(
                row,
                text=title,
                variable=var,
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text"],
                border_color=COLORS["line"],
                hover_color=COLORS["surface_hover"],
                fg_color=COLORS["accent"],
                checkmark_color="#FFFFFF",
                corner_radius=4,
                command=self._on_check_changed,
            )
            cb.pack(side="left", padx=(10, 8), fill="y")

            # Header pill / preview
            pill = ctk.CTkFrame(
                row,
                fg_color=COLORS["input_bg"],
                border_width=1,
                border_color=COLORS["line"],
                corner_radius=4,
                height=22,
            )
            pill.pack(side="left", padx=(0, 8), pady=6)
            ctk.CTkLabel(
                pill,
                text=label,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=COLORS["muted"],
            ).pack(padx=6, pady=1)

            # Up / Down buttons
            btn_down = ctk.CTkButton(
                row,
                text="▼",
                width=26,
                height=24,
                corner_radius=4,
                fg_color=COLORS["surface_hover"],
                hover_color=COLORS["line"],
                text_color=COLORS["text"] if idx < total - 1 else COLORS["muted"],
                state="normal" if idx < total - 1 else "disabled",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda i=idx: self._move_down(i),
            )
            btn_down.pack(side="right", padx=(2, 6), pady=6)

            btn_up = ctk.CTkButton(
                row,
                text="▲",
                width=26,
                height=24,
                corner_radius=4,
                fg_color=COLORS["surface_hover"],
                hover_color=COLORS["line"],
                text_color=COLORS["text"] if idx > 0 else COLORS["muted"],
                state="normal" if idx > 0 else "disabled",
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda i=idx: self._move_up(i),
            )
            btn_up.pack(side="right", padx=(2, 2), pady=6)

    def _move_up(self, index: int):
        if index > 0:
            self._order[index], self._order[index - 1] = self._order[index - 1], self._order[index]
            self._render_column_list()

    def _move_down(self, index: int):
        if index < len(self._order) - 1:
            self._order[index], self._order[index + 1] = self._order[index + 1], self._order[index]
            self._render_column_list()

    def _on_check_changed(self):
        self.lbl_warning.configure(text="")
        self._update_counter()

    def _update_counter(self):
        active_count = sum(1 for v in self._vars.values() if v.get())
        total_count = len(self._order)
        self.lbl_counter.configure(text=f"{active_count} dari {total_count} kolom aktif")

    def _select_all(self):
        for var in self._vars.values():
            var.set(True)
        self._on_check_changed()

    def _reset_default(self):
        default_set = set(self.default_columns)
        self._order = list(self.default_columns) + [k for k in self.all_columns if k not in default_set]
        for key, var in self._vars.items():
            var.set(key in default_set)
        self._render_column_list()
        self._on_check_changed()

    def _save(self):
        selected = [k for k in self._order if self._vars[k].get()]
        if not selected:
            self.lbl_warning.configure(text="Pilih minimal 1 kolom untuk ditampilkan.")
            return

        try:
            self.on_save(selected)
        except Exception as e:
            self.lbl_warning.configure(text=f"Gagal menyimpan: {e}")
            return

        self.destroy()
