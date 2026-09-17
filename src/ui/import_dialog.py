import os
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk

from export_service import inspect_export_file, load_export_file


class ImportDialog(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, db_manager: Any, on_import_callback: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.db = db_manager
        self.on_import_callback = on_import_callback

        self.selected_file: Optional[str] = None
        self.is_encrypted: bool = False
        self.parsed_payload: Optional[Dict[str, Any]] = None

        self.title("Import Connections")
        self.geometry("520x620")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self._setup_ui()

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=24, pady=24)

        # Header
        lbl_title = ctk.CTkLabel(main_frame, text="Import Connections", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(anchor="w", pady=(0, 6))

        lbl_sub = ctk.CTkLabel(
            main_frame,
            text="Select a Terbius JSON export file to import hosts and groups.",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        lbl_sub.pack(anchor="w", pady=(0, 16))

        # File Selection Frame
        file_frame = ctk.CTkFrame(main_frame)
        file_frame.pack(fill="x", pady=(0, 12))

        lbl_file = ctk.CTkLabel(file_frame, text="Export File:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_file.pack(anchor="w", padx=14, pady=(10, 4))

        picker_row = ctk.CTkFrame(file_frame, fg_color="transparent")
        picker_row.pack(fill="x", padx=14, pady=(0, 12))
        picker_row.grid_columnconfigure(0, weight=1)
        picker_row.grid_columnconfigure(1, weight=0)

        self.ent_file = ctk.CTkEntry(picker_row, placeholder_text="Choose a .json export file...")
        self.ent_file.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        btn_browse = ctk.CTkButton(picker_row, text="Browse...", width=80, command=self._browse_file)
        btn_browse.grid(row=0, column=1, sticky="e")

        # Passphrase Section (Hidden until encrypted file selected)
        self.pass_frame = ctk.CTkFrame(main_frame)
        
        self.lbl_pass = ctk.CTkLabel(
            self.pass_frame,
            text="This file is encrypted. Enter Decryption Passphrase:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#60A5FA"
        )
        self.lbl_pass.pack(anchor="w", padx=14, pady=(10, 4))

        pass_row = ctk.CTkFrame(self.pass_frame, fg_color="transparent")
        pass_row.pack(fill="x", padx=14, pady=(0, 12))
        pass_row.grid_columnconfigure(0, weight=1)
        pass_row.grid_columnconfigure(1, weight=0)

        self.ent_passphrase = ctk.CTkEntry(pass_row, placeholder_text="Enter passphrase", show="•")
        self.ent_passphrase.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        btn_unlock = ctk.CTkButton(pass_row, text="Unlock / Load", width=100, command=self._load_and_preview)
        btn_unlock.grid(row=0, column=1, sticky="e")

        # Preview Section
        self.preview_frame = ctk.CTkFrame(main_frame)
        self.preview_frame.pack(fill="both", expand=True, pady=(0, 12))

        self.lbl_preview_title = ctk.CTkLabel(
            self.preview_frame,
            text="Preview Data:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_preview_title.pack(anchor="w", padx=14, pady=(10, 4))

        self.txt_preview = ctk.CTkTextbox(self.preview_frame, font=("Courier", 11), wrap="none", height=120)
        self.txt_preview.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.txt_preview.insert("end", "No file loaded yet.")
        self.txt_preview.configure(state="disabled")

        # Duplicate Handling Frame
        dup_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        dup_frame.pack(fill="x", pady=(0, 10))

        lbl_dup = ctk.CTkLabel(dup_frame, text="If host already exists:", font=ctk.CTkFont(size=12))
        lbl_dup.pack(side="left", padx=(0, 10))

        self.opt_duplicate = ctk.CTkOptionMenu(
            dup_frame,
            values=["Skip existing", "Overwrite existing", "Keep both (Append)"],
            width=180
        )
        self.opt_duplicate.set("Skip existing")
        self.opt_duplicate.pack(side="left")

        # Error Label
        self.lbl_error = ctk.CTkLabel(main_frame, text="", text_color="red", font=ctk.CTkFont(size=11))
        self.lbl_error.pack(anchor="w", pady=(0, 8))

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

        self.btn_import = ctk.CTkButton(
            btn_frame,
            text="Import Connections",
            state="disabled",
            command=self._do_import
        )
        self.btn_import.pack(side="right", expand=True, fill="x", padx=(6, 0))

    def _browse_file(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Select Terbius Export File",
            filetypes=[("Terbius Export (*.json)", "*.json"), ("All Files (*.*)", "*.*")]
        )
        if not file_path:
            return

        self.selected_file = file_path
        self.ent_file.delete(0, "end")
        self.ent_file.insert(0, file_path)
        self.lbl_error.configure(text="")

        try:
            info = inspect_export_file(file_path)
            self.is_encrypted = info.get("encrypted", False)

            if self.is_encrypted:
                self.pass_frame.pack(fill="x", pady=(0, 12), after=self.ent_file.master.master)
                self.btn_import.configure(state="disabled")
                self._update_preview_text("File is encrypted. Please enter passphrase and click 'Unlock / Load'.")
            else:
                self.pass_frame.pack_forget()
                self._load_and_preview()

        except Exception as e:
            self.lbl_error.configure(text=f"Invalid file: {str(e)}")
            self.btn_import.configure(state="disabled")

    def _update_preview_text(self, text: str):
        self.txt_preview.configure(state="normal")
        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("end", text)
        self.txt_preview.configure(state="disabled")

    def _load_and_preview(self):
        self.lbl_error.configure(text="")
        if not self.selected_file:
            self.lbl_error.configure(text="Please select a file first.")
            return

        passphrase = self.ent_passphrase.get().strip() if self.is_encrypted else None

        try:
            payload, is_enc = load_export_file(self.selected_file, passphrase=passphrase)
            self.parsed_payload = payload

            hosts = payload.get("hosts", [])
            groups = payload.get("groups", [])

            lines = [
                f"Status: Successfully loaded ({'Encrypted' if is_enc else 'Plain'})",
                f"Groups: {len(groups)} found ({', '.join(groups) if groups else 'None'})",
                f"Hosts: {len(hosts)} found",
                "-" * 45
            ]

            for h in hosts:
                has_pass = "✓ Has Password" if h.get("password") else "- No Password"
                has_git = "✓ Has Git Creds" if (h.get("git_user") or h.get("git_pass")) else "- No Git Creds"
                lines.append(f"• {h['label']} ({h['username']}@{h['hostname']}:{h.get('port', 22)}) [{h.get('group_name') or 'No Group'}] [{has_pass}] [{has_git}]")

            self._update_preview_text("\n".join(lines))
            self.btn_import.configure(state="normal")

        except Exception as e:
            self.lbl_error.configure(text=str(e))
            self.btn_import.configure(state="disabled")

    def _do_import(self):
        if not self.parsed_payload:
            self.lbl_error.configure(text="No data loaded to import.")
            return

        dup_action = self.opt_duplicate.get()
        hosts = self.parsed_payload.get("hosts", [])
        groups = self.parsed_payload.get("groups", [])

        try:
            # 1. Pastikan groups tersimpan di database
            group_name_to_id = {}
            for g_name in groups:
                if g_name and g_name.strip():
                    gid = self.db.add_group(g_name.strip())
                    group_name_to_id[g_name.strip().lower()] = gid

            # Dapatkan seluruh host yang sudah ada untuk cek duplikasi
            existing_hosts = {h["label"].lower(): h for h in self.db.get_all_hosts()}

            imported_count = 0
            skipped_count = 0
            overwritten_count = 0

            for h in hosts:
                label = h["label"].strip()
                existing = existing_hosts.get(label.lower())

                # Tentukan group ID
                group_id = None
                gname = h.get("group_name")
                if gname:
                    gclean = gname.strip()
                    if gclean.lower() in group_name_to_id:
                        group_id = group_name_to_id[gclean.lower()]
                    else:
                        group_id = self.db.add_group(gclean)
                        group_name_to_id[gclean.lower()] = group_id

                if existing:
                    if dup_action == "Skip existing":
                        skipped_count += 1
                        continue
                    elif dup_action == "Overwrite existing":
                        self.db.update_host(
                            host_id=existing["id"],
                            label=label,
                            hostname=h["hostname"],
                            port=int(h.get("port", 22)),
                            username=h["username"],
                            auth_type=h.get("auth_type", "password"),
                            password=h.get("password"),
                            repo_path=h.get("repo_path", "/var/www/html"),
                            git_branch=h.get("git_branch"),
                            git_user=h.get("git_user"),
                            git_pass=h.get("git_pass"),
                            key_id=existing.get("key_id"),
                            group_id=group_id
                        )
                        overwritten_count += 1
                        continue
                    elif dup_action == "Keep both (Append)":
                        label = f"{label} (Imported)"

                # Tambah host baru
                self.db.add_host(
                    label=label,
                    hostname=h["hostname"],
                    port=int(h.get("port", 22)),
                    username=h["username"],
                    auth_type=h.get("auth_type", "password"),
                    password=h.get("password"),
                    repo_path=h.get("repo_path", "/var/www/html"),
                    git_branch=h.get("git_branch"),
                    git_user=h.get("git_user"),
                    git_pass=h.get("git_pass"),
                    group_id=group_id
                )
                imported_count += 1

            if self.on_import_callback:
                self.on_import_callback()

            summary_msg = f"Import finished:\n• {imported_count} new host(s) added\n• {overwritten_count} host(s) overwritten\n• {skipped_count} host(s) skipped"
            messagebox.showinfo("Import Successful", summary_msg)
            self.destroy()

        except Exception as e:
            self.lbl_error.configure(text=f"Failed to import: {str(e)}")
