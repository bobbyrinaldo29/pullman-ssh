from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

import customtkinter as ctk

import host_import

SOURCE_CONFIG = {
    "navicat": {
        "title": "Import from Navicat",
        "instruction": "Pilih file export koneksi Navicat (.ncx). Di Navicat: klik kanan koneksi > Export Connection.",
        "filetypes": [("Navicat Export (*.ncx)", "*.ncx"), ("All Files", "*.*")],
    },
    "dbeaver": {
        "title": "Import from DBeaver",
        "instruction": "Pilih file export project DBeaver (.dbp). Di DBeaver: klik kanan project > Export > 'DBeaver project archive'.",
        "filetypes": [("DBeaver Project (*.dbp)", "*.dbp"), ("All Files", "*.*")],
    },
}


class DbToolImportDialog(ctk.CTkToplevel):
    """Dialog import host SSH dari koneksi yang tersimpan di Navicat atau DBeaver."""

    def __init__(self, parent: ctk.CTk, db_manager: Any, source: str, on_import_callback: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.db = db_manager
        self.source = source
        self.on_import_callback = on_import_callback
        self.candidate_hosts = []

        config = SOURCE_CONFIG[source]
        self.title(config["title"])
        self.geometry("560x600")
        self.resizable(False, False)

        self.transient(parent)
        self.lift()
        self.focus_force()
        self.grab_set()

        self._setup_ui(config)

    def _setup_ui(self, config):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(main, text=config["title"], font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(
            main, text=config["instruction"], text_color="gray", font=ctk.CTkFont(size=12),
            wraplength=500, justify="left"
        ).pack(anchor="w", pady=(0, 16))

        file_frame = ctk.CTkFrame(main)
        file_frame.pack(fill="x", pady=(0, 12))

        picker_row = ctk.CTkFrame(file_frame, fg_color="transparent")
        picker_row.pack(fill="x", padx=14, pady=12)
        picker_row.grid_columnconfigure(0, weight=1)

        self.ent_file = ctk.CTkEntry(picker_row, placeholder_text="Pilih file...")
        self.ent_file.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(picker_row, text="Browse...", width=90, command=self._browse_file).grid(row=0, column=1)

        preview_frame = ctk.CTkFrame(main)
        preview_frame.pack(fill="both", expand=True, pady=(0, 12))

        ctk.CTkLabel(preview_frame, text="Preview Host yang Ditemukan:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))

        self.txt_preview = ctk.CTkTextbox(preview_frame, font=("Courier", 11), wrap="none")
        self.txt_preview.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.txt_preview.insert("end", "Belum ada file dipilih.")
        self.txt_preview.configure(state="disabled")

        dup_frame = ctk.CTkFrame(main, fg_color="transparent")
        dup_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(dup_frame, text="Jika host sudah ada:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 10))
        self.opt_duplicate = ctk.CTkOptionMenu(dup_frame, values=["Skip existing", "Overwrite existing", "Keep both (Append)"], width=180)
        self.opt_duplicate.set("Skip existing")
        self.opt_duplicate.pack(side="left")

        self.lbl_error = ctk.CTkLabel(main, text="", text_color="red", font=ctk.CTkFont(size=11), wraplength=500, justify="left")
        self.lbl_error.pack(anchor="w", pady=(0, 8))

        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        ctk.CTkButton(
            btn_frame, text="Cancel", fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), command=self.destroy
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_import = ctk.CTkButton(btn_frame, text="Import Hosts", state="disabled", command=self._do_import)
        self.btn_import.pack(side="right", expand=True, fill="x", padx=(6, 0))

    def _browse_file(self):
        config = SOURCE_CONFIG[self.source]
        file_path = filedialog.askopenfilename(
            parent=self,
            title=config["title"],
            filetypes=config["filetypes"]
        )
        if not file_path:
            return
        self._load_file(file_path)

    def _load_file(self, file_path: str):
        self.ent_file.delete(0, "end")
        self.ent_file.insert(0, file_path)
        self.lbl_error.configure(text="")

        try:
            if self.source == "navicat":
                hosts, stats = host_import.import_navicat_hosts(file_path)
            else:
                hosts, stats = host_import.import_dbeaver_hosts(file_path)

            self.candidate_hosts = hosts
            self._render_preview(stats)
            self.btn_import.configure(state="normal" if hosts else "disabled")

        except Exception as e:
            self.candidate_hosts = []
            self.lbl_error.configure(text=f"Gagal membaca file: {e}")
            self.btn_import.configure(state="disabled")
            self._render_preview({})

    def _render_preview(self, stats: dict):
        db_count = sum(1 for h in self.candidate_hosts if h.get("db_host"))
        lines = [
            f"Ditemukan {len(self.candidate_hosts)} host SSH yang bisa diimpor ({db_count} dengan info Database).",
            f"Dilewati (tanpa SSH tunnel): {stats.get('skipped_no_ssh', 0)}",
            f"Dilewati (SSH pakai private key, belum didukung untuk import): {stats.get('skipped_key_only', 0)}",
            "-" * 50
        ]
        for h in self.candidate_hosts:
            db_note = f" + DB '{h['db_database_name'] or h['db_host']}'" if h.get("db_host") else ""
            lines.append(f"• {h['label']} ({h['username']}@{h['hostname']}:{h['port']}){db_note} [{h.get('group_name') or 'No Group'}]")

        if not self.candidate_hosts:
            lines.append("")
            lines.append("Tidak ada koneksi dengan SSH Tunnel (password) yang bisa dijadikan Host.")

        self.txt_preview.configure(state="normal")
        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("end", "\n".join(lines))
        self.txt_preview.configure(state="disabled")

    def _do_import(self):
        if not self.candidate_hosts:
            return
        try:
            result = host_import.save_hosts_to_db(self.db, self.candidate_hosts, self.opt_duplicate.get())
        except Exception as e:
            self.lbl_error.configure(text=f"Gagal mengimpor: {e}")
            return

        if self.on_import_callback:
            self.on_import_callback()

        messagebox.showinfo(
            "Import Selesai",
            f"• {result['imported']} host baru ditambahkan\n"
            f"• {result['overwritten']} host ditimpa\n"
            f"• {result['skipped']} host dilewati"
        )
        self.destroy()
