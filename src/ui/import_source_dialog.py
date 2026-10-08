from typing import Callable
import customtkinter as ctk
from theme import COLORS


class ImportSourceDialog(ctk.CTkToplevel):
    """Dialog pemilihan sumber import: Pullman Backup, Navicat, atau DBeaver."""

    SOURCES = [
        ("pullman", "Pullman Backup (.json)", "File backup/export bawaan aplikasi ini, berisi host & grup (bisa terenkripsi)."),
        ("navicat", "Navicat", "Ambil host dari SSH Tunnel yang tersimpan pada file export koneksi Navicat (.ncx)."),
        ("dbeaver", "DBeaver", "Ambil host dari SSH Tunnel yang tersimpan pada project archive DBeaver (.dbp) atau data-sources.json."),
    ]

    def __init__(self, parent: ctk.CTk, on_select: Callable[[str], None]):
        super().__init__(parent, fg_color=COLORS["window"])
        self.on_select = on_select

        self.title("Import Hosts")
        self.geometry("460x470")
        self.resizable(False, False)

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.grab_set()

        self._setup_ui()

    def _setup_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            main, text="Import dari mana?", text_color=COLORS["text"], font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 2))
        
        ctk.CTkLabel(
            main,
            text="Pilih sumber data host SSH yang ingin diimpor.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12)
        ).pack(anchor="w", pady=(0, 14))

        self.choice_var = ctk.StringVar(value=self.SOURCES[0][0])

        options_container = ctk.CTkFrame(main, fg_color="transparent")
        options_container.pack(fill="both", expand=True)

        for key, title, desc in self.SOURCES:
            self._build_option_row(options_container, key, title, desc)

        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom", pady=(14, 0))

        ctk.CTkButton(
            btn_frame, 
            text="Cancel", 
            fg_color=COLORS["surface"], 
            border_width=1,
            border_color=COLORS["line"],
            text_color=COLORS["text_secondary"], 
            hover_color=COLORS["surface_hover"],
            command=self._close
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, 
            text="Next", 
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(weight="bold"),
            command=self._confirm
        ).pack(side="right", expand=True, fill="x", padx=(6, 0))

    def _build_option_row(self, parent, key: str, title: str, desc: str):
        row = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8, border_width=1, border_color=COLORS["line"])
        row.pack(fill="x", pady=4)

        radio = ctk.CTkRadioButton(
            row, 
            text="", 
            variable=self.choice_var, 
            value=key,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"]
        )
        radio.pack(side="left", padx=(12, 6), pady=12)

        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True, pady=8, padx=(0, 12))
        
        lbl_title = ctk.CTkLabel(text_col, text=title, text_color=COLORS["text"], font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
        lbl_title.pack(anchor="w", fill="x")
        
        lbl_desc = ctk.CTkLabel(
            text_col, 
            text=desc, 
            text_color=COLORS["muted"], 
            font=ctk.CTkFont(size=11),
            anchor="w", 
            justify="left", 
            wraplength=310
        )
        lbl_desc.pack(anchor="w", fill="x")

        # Bind klik pada seluruh elemen baris
        for widget in (row, text_col, lbl_title, lbl_desc):
            widget.bind("<Button-1>", lambda _e, k=key: self.choice_var.set(k))

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _confirm(self):
        source = self.choice_var.get()
        callback = self.on_select
        parent = self.master

        # Releases grab sebelum destroy agar window selanjutnya bisa mengambil focus
        try:
            self.grab_release()
        except Exception:
            pass

        self.destroy()

        # Eksekusi callback di event loop berikutnya
        if callback:
            parent.after(50, lambda: callback(source))