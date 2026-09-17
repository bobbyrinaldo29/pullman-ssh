from tkinter import filedialog, messagebox
from typing import Any, List
import customtkinter as ctk

from export_service import export_data, save_export_file


class ExportDialog(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, db_manager: Any):
        super().__init__(parent)
        self.db = db_manager

        self.title("Export Connections")
        self.geometry("480x500")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self._setup_ui()

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        lbl_title = ctk.CTkLabel(main_frame, text="Export Connections", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(anchor="w", pady=(0, 6))

        all_hosts = self.db.get_all_hosts()
        lbl_sub = ctk.CTkLabel(
            main_frame, 
            text=f"Total {len(all_hosts)} host(s) will be exported to a JSON file.", 
            text_color="gray", 
            font=ctk.CTkFont(size=12)
        )
        lbl_sub.pack(anchor="w", pady=(0, 16))

        # Checkboxes Container
        opt_frame = ctk.CTkFrame(main_frame)
        opt_frame.pack(fill="x", pady=(0, 16))

        lbl_opt_title = ctk.CTkLabel(opt_frame, text="Security & Credential Options:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_opt_title.pack(anchor="w", padx=16, pady=(12, 8))

        self.var_ssh_pass = ctk.BooleanVar(value=False)
        self.chk_ssh_pass = ctk.CTkCheckBox(
            opt_frame,
            text="Include SSH Passwords",
            variable=self.var_ssh_pass,
            command=self._on_options_changed
        )
        self.chk_ssh_pass.pack(anchor="w", padx=16, pady=(4, 6))

        self.var_git_creds = ctk.BooleanVar(value=False)
        self.chk_git_creds = ctk.CTkCheckBox(
            opt_frame,
            text="Include Git Credentials (Username & Password/Token)",
            variable=self.var_git_creds,
            command=self._on_options_changed
        )
        self.chk_git_creds.pack(anchor="w", padx=16, pady=(0, 12))

        # Passphrase Section Container
        self.pass_frame = ctk.CTkFrame(main_frame)
        self.pass_frame.pack(fill="x", pady=(0, 12))

        self.lbl_pass_title = ctk.CTkLabel(
            self.pass_frame, 
            text="Encryption Passphrase (Required for Credentials):", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_pass_title.pack(anchor="w", padx=16, pady=(12, 6))

        self.ent_pass = ctk.CTkEntry(self.pass_frame, placeholder_text="Enter export passphrase", show="•")
        self.ent_pass.pack(fill="x", padx=16, pady=(0, 8))

        self.ent_confirm = ctk.CTkEntry(self.pass_frame, placeholder_text="Confirm export passphrase", show="•")
        self.ent_confirm.pack(fill="x", padx=16, pady=(0, 12))

        # Info Note
        self.lbl_note = ctk.CTkLabel(
            main_frame,
            text="Connections will be exported without passwords or tokens.",
            text_color="gray",
            font=ctk.CTkFont(size=11),
            wraplength=430,
            justify="left"
        )
        self.lbl_note.pack(anchor="w", pady=(0, 10))

        # Error Label
        self.lbl_error = ctk.CTkLabel(main_frame, text="", text_color="red", font=ctk.CTkFont(size=11))
        self.lbl_error.pack(anchor="w", pady=(0, 10))

        # Action Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.destroy
        )
        btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 6))

        btn_export = ctk.CTkButton(btn_frame, text="Export to File...", command=self._do_export)
        btn_export.pack(side="right", expand=True, fill="x", padx=(6, 0))

        # Initial view update
        self._on_options_changed()

    def _on_options_changed(self):
        """Aktifkan atau nonaktifkan field passphrase tergantung apakah kredensial dipilih."""
        need_encryption = self.var_ssh_pass.get() or self.var_git_creds.get()

        if need_encryption:
            self.pass_frame.pack(fill="x", pady=(0, 12))
            self.lbl_note.configure(
                text="The exported file will be strongly encrypted (AES-256 Fernet + PBKDF2). You will need this passphrase to import.",
                text_color="#60A5FA"
            )
        else:
            self.pass_frame.pack_forget()
            self.lbl_note.configure(
                text="Connections will be exported without sensitive passwords or tokens (plain JSON).",
                text_color="gray"
            )
        self.lbl_error.configure(text="")

    def _do_export(self):
        self.lbl_error.configure(text="")
        inc_ssh = self.var_ssh_pass.get()
        inc_git = self.var_git_creds.get()
        need_encryption = inc_ssh or inc_git

        passphrase = None
        if need_encryption:
            passphrase = self.ent_pass.get()
            confirm = self.ent_confirm.get()

            if not passphrase:
                self.lbl_error.configure(text="Please enter an export passphrase.")
                return

            if passphrase != confirm:
                self.lbl_error.configure(text="Passphrase and confirmation do not match.")
                return

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Export File",
            defaultextension=".json",
            filetypes=[("Terbius Export (*.json)", "*.json"), ("All Files (*.*)", "*.*")]
        )

        if not file_path:
            return

        try:
            hosts = self.db.get_all_hosts()
            groups = self.db.get_groups()

            export_dict = export_data(
                hosts=hosts,
                groups=groups,
                include_ssh_pass=inc_ssh,
                include_git_creds=inc_git,
                passphrase=passphrase
            )

            save_export_file(file_path, export_dict)
            messagebox.showinfo("Export Successful", f"Successfully exported {len(hosts)} connection(s) to:\n{file_path}")
            self.destroy()

        except Exception as e:
            self.lbl_error.configure(text=f"Export failed: {str(e)}")
