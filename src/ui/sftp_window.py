import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from theme import COLORS, get_color, apply_treeview_styles
from icons import get_icon, get_tk_image
from sftp_service import SFTPService
from ui.file_editor_dialog import FileEditorDialog
from terminal_launcher import launch_ssh_terminal


class SFTPWindow(ctk.CTkToplevel):
    """Jendela Built-in SFTP File Manager (bergaya FileZilla / WinSCP) untuk manajemen file remote."""

    def __init__(self, parent: Any, host: Dict[str, Any]):
        super().__init__(parent)
        self.app = parent
        
        # Ensure credentials are fully decrypted
        if hasattr(parent, "db") and host and host.get("id"):
            decrypted = parent.db.get_host_by_id(host["id"])
            self.host = decrypted or host
        else:
            self.host = host
        
        self.current_path = self.host.get("repo_path") or "/var/www/html"
        self._history_stack: List[str] = []
        self._items: List[Dict[str, Any]] = []
        self._is_loading = False

        label = host.get("label") or host.get("hostname")
        self.title(f"SFTP File Manager - {label} ({host.get('username')}@{host.get('hostname')})")
        self.geometry("980x640")
        self.minsize(780, 480)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_toolbar()
        self._build_file_table()
        self._build_status_bar()
        self._create_context_menu()

        # Muat isi folder awal
        self._navigate_to(self.current_path)

    def _build_header(self):
        """Header Navigasi & Breadcrumb Bar."""
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=52, corner_radius=0, border_width=1, border_color=COLORS["line"])
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(3, weight=1)

        # Nav Buttons (Up, Home, Repo Path, Refresh)
        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.grid(row=0, column=0, padx=(12, 6), pady=8)

        self.btn_up = ctk.CTkButton(
            btn_box, text="", image=get_icon("arrow-up", (14, 14), COLORS["text"]),
            width=32, height=32, corner_radius=6,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._go_up_dir
        )
        self.btn_up.pack(side="left", padx=2)

        self.btn_home = ctk.CTkButton(
            btn_box, text="", image=get_icon("house", (14, 14), COLORS["text"]),
            width=32, height=32, corner_radius=6,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._go_home_dir
        )
        self.btn_home.pack(side="left", padx=2)

        repo = self.host.get("repo_path") or "/var/www/html"
        self.btn_repo = ctk.CTkButton(
            btn_box, text=" Repo", image=get_icon("rocket", (13, 13), COLORS["accent_text"]),
            width=70, height=32, corner_radius=6,
            fg_color=COLORS["accent_subtle"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["accent_text"], font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._navigate_to(repo)
        )
        self.btn_repo.pack(side="left", padx=(2, 3))

        self.btn_terminal = ctk.CTkButton(
            btn_box, text=" SSH", image=get_icon("terminal", (13, 13), COLORS["accent_text"]),
            width=65, height=32, corner_radius=6,
            fg_color=COLORS["accent_subtle"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["accent_text"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self._open_terminal_here
        )
        self.btn_terminal.pack(side="left", padx=(0, 6))

        # Path Entry & Go Button
        lbl_loc = ctk.CTkLabel(header, text="Remote Path:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["muted"])
        lbl_loc.grid(row=0, column=2, padx=(4, 6))

        self.path_var = ctk.StringVar(value=self.current_path)
        self.ent_path = ctk.CTkEntry(
            header,
            textvariable=self.path_var,
            height=32,
            corner_radius=6,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["line"],
            font=ctk.CTkFont(size=12)
        )
        self.ent_path.grid(row=0, column=3, sticky="ew", padx=(0, 6), pady=8)
        self.ent_path.bind("<Return>", lambda e: self._navigate_to(self.path_var.get()))

        self.btn_go = ctk.CTkButton(
            header, text="Go", width=46, height=32, corner_radius=6,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._navigate_to(self.path_var.get())
        )
        self.btn_go.grid(row=0, column=4, padx=(0, 8), pady=8)

        self.btn_refresh = ctk.CTkButton(
            header, text="", image=get_icon("refresh-cw", (14, 14), COLORS["text"]),
            width=32, height=32, corner_radius=6,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["line"],
            command=self._refresh_current_dir
        )
        self.btn_refresh.grid(row=0, column=5, padx=(0, 14), pady=8)

    def _build_toolbar(self):
        """Action Toolbar untuk operasi File & Direktori."""
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=40, corner_radius=0, border_width=1, border_color=COLORS["line"])
        toolbar.grid(row=1, column=0, sticky="ew")

        left_tools = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_tools.pack(side="left", padx=12, pady=5)

        self.btn_upload = ctk.CTkButton(
            left_tools, text=" Upload File", image=get_icon("upload", (13, 13), "#FFFFFF"),
            height=28, corner_radius=6,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._prompt_upload_file
        )
        self.btn_upload.pack(side="left", padx=(0, 6))

        self.btn_download = ctk.CTkButton(
            left_tools, text=" Download", image=get_icon("download", (13, 13), COLORS["text"]),
            height=28, corner_radius=6,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._download_selected
        )
        self.btn_download.pack(side="left", padx=(0, 6))

        self.btn_new_file = ctk.CTkButton(
            left_tools, text=" New File", image=get_icon("file-plus", (13, 13), COLORS["text_secondary"]),
            height=28, corner_radius=6,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._prompt_new_file
        )
        self.btn_new_file.pack(side="left", padx=(0, 6))

        self.btn_new_folder = ctk.CTkButton(
            left_tools, text=" New Folder", image=get_icon("folder-plus", (13, 13), COLORS["text_secondary"]),
            height=28, corner_radius=6,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._prompt_new_folder
        )
        self.btn_new_folder.pack(side="left", padx=(0, 6))

        self.btn_edit = ctk.CTkButton(
            left_tools, text=" Edit File", image=get_icon("pencil", (13, 13), COLORS["text_secondary"]),
            height=28, corner_radius=6,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._edit_selected_file
        )
        self.btn_edit.pack(side="left", padx=(0, 6))

        self.btn_delete = ctk.CTkButton(
            left_tools, text=" Delete", image=get_icon("trash", (13, 13), COLORS["danger_text"]),
            height=28, corner_radius=6,
            fg_color=COLORS["danger_subtle"], hover_color=COLORS["danger_hover"],
            text_color=COLORS["danger_text"], border_width=1, border_color=COLORS["danger_border"],
            font=ctk.CTkFont(size=11),
            command=self._delete_selected
        )
        self.btn_delete.pack(side="left", padx=(0, 6))

        self.btn_term_toolbar = ctk.CTkButton(
            left_tools, text=" Terminal", image=get_icon("terminal", (13, 13), COLORS["text_secondary"]),
            height=28, corner_radius=6,
            fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
            text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["line"],
            font=ctk.CTkFont(size=11),
            command=self._open_terminal_here
        )
        self.btn_term_toolbar.pack(side="left")

    def _build_file_table(self):
        """Tabel Explorer File & Direktori berbasis TTK Treeview."""
        table_container = ctk.CTkFrame(self, fg_color=COLORS["input_bg"], corner_radius=0)
        table_container.grid(row=2, column=0, sticky="nsew")
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        apply_treeview_styles()

        self.tree = ttk.Treeview(
            table_container,
            columns=("size", "type", "permissions", "mtime"),
            show="tree headings",
            style="Pullman.Treeview",
            selectmode="extended"
        )

        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("type", text="Type", anchor="center")
        self.tree.heading("permissions", text="Permissions", anchor="center")
        self.tree.heading("mtime", text="Date Modified", anchor="w")

        self.tree.column("#0", width=380, minwidth=150, anchor="w")
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("type", width=90, anchor="center")
        self.tree.column("permissions", width=120, anchor="center")
        self.tree.column("mtime", width=160, anchor="w")

        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<Double-1>", self._on_item_double_click)
        self.tree.bind("<Return>", lambda e: self._open_focused_item())
        self.tree.bind("<Button-2>", self._show_context_menu)
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _build_status_bar(self):
        """Status Bar di bagian bawah."""
        status_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=28, corner_radius=0, border_width=1, border_color=COLORS["line"])
        status_bar.grid(row=3, column=0, sticky="ew")

        self.lbl_status_msg = ctk.CTkLabel(
            status_bar,
            text=f"Connected: {self.host.get('username')}@{self.host.get('hostname')}:{self.host.get('port', 22)}",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        )
        self.lbl_status_msg.pack(side="left", padx=14, pady=3)

        self.lbl_stats = ctk.CTkLabel(
            status_bar,
            text="0 items",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"]
        )
        self.lbl_stats.pack(side="right", padx=14, pady=3)

    def _create_context_menu(self):
        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            bg=get_color("surface"),
            fg=get_color("text"),
            activebackground=get_color("accent"),
            activeforeground="#FFFFFF",
            bd=1
        )

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
        
        sel = self.tree.selection()
        item_data = self._get_item_by_id(sel[0]) if sel else None

        self.context_menu.delete(0, "end")

        if item_data:
            if item_data["is_dir"]:
                self.context_menu.add_command(
                    label="  Open Terminal in Here (SSH)",
                    image=get_tk_image("terminal", (14, 14), COLORS["accent_text"]),
                    compound="left",
                    command=lambda p=item_data["path"]: self._open_terminal_at(p)
                )
            else:
                self.context_menu.add_command(
                    label="  Edit / View File",
                    image=get_tk_image("pencil", (14, 14), COLORS["text"]),
                    compound="left",
                    command=lambda: self._edit_selected_file(as_sudo=False)
                )
                self.context_menu.add_command(
                    label="  Edit as sudo...",
                    image=get_tk_image("shield", (14, 14), COLORS["danger_text"]),
                    compound="left",
                    command=lambda: self._edit_selected_file(as_sudo=True)
                )
                self.context_menu.add_command(
                    label="  Open Terminal in Folder (SSH)",
                    image=get_tk_image("terminal", (14, 14), COLORS["accent_text"]),
                    compound="left",
                    command=lambda p=os.path.dirname(item_data["path"]): self._open_terminal_at(p)
                )
            self.context_menu.add_command(
                label="  Download...",
                image=get_tk_image("download", (14, 14), COLORS["text"]),
                compound="left",
                command=self._download_selected
            )
            self.context_menu.add_command(
                label="  Rename...",
                image=get_tk_image("pencil", (14, 14), COLORS["text_secondary"]),
                compound="left",
                command=self._prompt_rename
            )
            self.context_menu.add_command(
                label="  Delete",
                image=get_tk_image("trash", (14, 14), COLORS["danger_text"]),
                compound="left",
                command=self._delete_selected
            )
            self.context_menu.add_separator()
            self.context_menu.add_command(
                label="  Copy Remote Path",
                image=get_tk_image("copy", (14, 14), COLORS["text_secondary"]),
                compound="left",
                command=lambda: self._copy_path_to_clipboard(item_data["path"])
            )
            self.context_menu.add_separator()

        # General directory actions
        self.context_menu.add_command(
            label="  Open Terminal in Here (SSH)",
            image=get_tk_image("terminal", (14, 14), COLORS["accent_text"]),
            compound="left",
            command=self._open_terminal_here
        )
        self.context_menu.add_command(
            label="  Upload File Here...",
            image=get_tk_image("upload", (14, 14), COLORS["accent_text"]),
            compound="left",
            command=self._prompt_upload_file
        )
        self.context_menu.add_command(
            label="  New File...",
            image=get_tk_image("file-plus", (14, 14), COLORS["text"]),
            compound="left",
            command=self._prompt_new_file
        )
        self.context_menu.add_command(
            label="  New Folder...",
            image=get_tk_image("folder-plus", (14, 14), COLORS["text"]),
            compound="left",
            command=self._prompt_new_folder
        )
        self.context_menu.add_command(
            label="  Refresh",
            image=get_tk_image("refresh-cw", (14, 14), COLORS["muted"]),
            compound="left",
            command=self._refresh_current_dir
        )

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    # =========================================================================
    # NAVIGATION & DIRECTORY SCAN
    # =========================================================================

    def _navigate_to(self, remote_path: str):
        if self._is_loading:
            return
        self._is_loading = True
        self.lbl_status_msg.configure(text=f"Loading directory: {remote_path}...", text_color=COLORS["accent_text"])

        def worker():
            full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
            res = SFTPService.list_dir(full_host, remote_path)

            def on_done():
                self._is_loading = False
                if res["success"]:
                    self.current_path = res["current_path"]
                    self.path_var.set(self.current_path)
                    self._items = res["items"]
                    self._populate_table()
                    self.lbl_status_msg.configure(
                        text=f"Connected: {self.host.get('username')}@{self.host.get('hostname')}",
                        text_color=COLORS["text_secondary"]
                    )
                else:
                    self.lbl_status_msg.configure(text=f"Error: {res['error']}", text_color=COLORS["danger"])
                    messagebox.showerror("SFTP Error", f"Gagal membuka direktori '{remote_path}':\n\n{res['error']}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_current_dir(self):
        self._navigate_to(self.current_path)

    def _go_up_dir(self):
        p = Path(self.current_path).parent.as_posix()
        if p and p != self.current_path:
            self._navigate_to(p)

    def _go_home_dir(self):
        user = self.host.get("username", "root")
        home = "/root" if user == "root" else f"/home/{user}"
        self._navigate_to(home)

    def _populate_table(self):
        self.tree.delete(*self.tree.get_children())
        folders_count = 0
        files_count = 0
        total_size = 0

        for idx, item in enumerate(self._items):
            item_id = str(idx)
            is_dir = item["is_dir"]
            icon = get_tk_image("folder" if is_dir else "file", (14, 14), COLORS["accent"] if is_dir else COLORS["text_secondary"])
            
            if is_dir:
                folders_count += 1
                type_str = "Folder"
            else:
                files_count += 1
                type_str = item["ext"].upper().lstrip(".") or "File"
                total_size += item["size_bytes"]

            self.tree.insert(
                "", "end",
                iid=item_id,
                text=f"  {item['name']}",
                image=icon,
                values=(
                    item["size_str"],
                    type_str,
                    item["permissions"],
                    item["mtime_str"]
                )
            )

        from sftp_service import _format_size
        self.lbl_stats.configure(text=f"{folders_count} folders, {files_count} files ({_format_size(total_size)})")

    def _get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        try:
            idx = int(item_id)
            if 0 <= idx < len(self._items):
                return self._items[idx]
        except Exception:
            pass
        return None

    def _on_item_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        item_data = self._get_item_by_id(item_id)
        if not item_data:
            return

        if item_data["is_dir"]:
            self._navigate_to(item_data["path"])
        else:
            self._open_file_in_editor(item_data["path"])

    def _open_focused_item(self):
        sel = self.tree.selection()
        if sel:
            item_data = self._get_item_by_id(sel[0])
            if item_data:
                if item_data["is_dir"]:
                    self._navigate_to(item_data["path"])
                else:
                    self._open_file_in_editor(item_data["path"])

    # =========================================================================
    # FILE OPERATIONS (UPLOAD, DOWNLOAD, EDIT, NEW, DELETE)
    # =========================================================================

    def _open_file_in_editor(self, remote_file_path: str, as_sudo: bool = False):
        full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
        FileEditorDialog(
            parent=self,
            host=full_host,
            remote_file_path=remote_file_path,
            as_sudo=as_sudo,
            on_saved_callback=self._refresh_current_dir
        )

    def _edit_selected_file(self, as_sudo: bool = False):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Peringatan", "Pilih file yang ingin diedit.", parent=self)
            return
        item = self._get_item_by_id(sel[0])
        if item:
            if item["is_dir"]:
                messagebox.showinfo("Info", "Item yang dipilih adalah folder. Dobel klik untuk membukanya.", parent=self)
                return
            self._open_file_in_editor(item["path"], as_sudo=as_sudo)

    def _download_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Peringatan", "Pilih file yang ingin diunduh.", parent=self)
            return
        item = self._get_item_by_id(sel[0])
        if not item:
            return

        filename = item["name"]
        local_path = filedialog.asksaveasfilename(
            parent=self,
            initialfile=filename,
            title=f"Save '{filename}' to..."
        )
        if not local_path:
            return

        self.lbl_status_msg.configure(text=f"Downloading '{filename}'...", text_color=COLORS["accent_text"])

        def worker():
            full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
            ok, err = SFTPService.download_file(full_host, item["path"], local_path)

            def on_done():
                if ok:
                    self.lbl_status_msg.configure(text=f"Downloaded '{filename}' successfully ✓", text_color=COLORS["success_text"])
                    messagebox.showinfo("Download Selesai", f"File '{filename}' berhasil diunduh ke:\n{local_path}", parent=self)
                else:
                    self.lbl_status_msg.configure(text=f"Download failed: {err}", text_color=COLORS["danger"])
                    messagebox.showerror("Download Error", f"Gagal mengunduh file:\n\n{err}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_upload_file(self):
        local_files = filedialog.askopenfilenames(
            parent=self,
            title="Pilih File untuk Di-upload"
        )
        if not local_files:
            return

        total = len(local_files)
        self.lbl_status_msg.configure(text=f"Uploading {total} file(s)...", text_color=COLORS["accent_text"])

        def worker():
            full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
            failed = []
            for lf in local_files:
                fname = Path(lf).name
                remote_dest = f"{self.current_path.rstrip('/')}/{fname}"
                ok, err = SFTPService.upload_file(full_host, lf, remote_dest)
                if not ok:
                    failed.append((fname, err))

            def on_done():
                self._refresh_current_dir()
                if not failed:
                    self.lbl_status_msg.configure(text=f"Upload {total} file(s) selesai ✓", text_color=COLORS["success_text"])
                    messagebox.showinfo("Upload Berhasil", f"{total} file berhasil di-upload ke {self.current_path}.", parent=self)
                else:
                    self.lbl_status_msg.configure(text=f"Upload selesai ({len(failed)} gagal)", text_color=COLORS["danger"])
                    messagebox.showwarning("Upload Warning", f"{len(failed)} file gagal di-upload:\n" + "\n".join(f"{f}: {e}" for f, e in failed), parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_new_folder(self):
        dialog = ctk.CTkInputDialog(
            title="Buat Folder Baru",
            text="Masukkan nama folder baru:"
        )
        folder_name = dialog.get_input()
        if not folder_name or not folder_name.strip():
            return

        folder_name = folder_name.strip()
        remote_dest = f"{self.current_path.rstrip('/')}/{folder_name}"
        self.lbl_status_msg.configure(text=f"Creating folder '{folder_name}'...", text_color=COLORS["accent_text"])

        def worker():
            full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
            ok, err = SFTPService.create_dir(full_host, remote_dest)

            def on_done():
                if ok:
                    self._refresh_current_dir()
                    self.lbl_status_msg.configure(text=f"Folder '{folder_name}' dibuat ✓", text_color=COLORS["success_text"])
                else:
                    self.lbl_status_msg.configure(text=f"Failed to create folder: {err}", text_color=COLORS["danger"])
                    messagebox.showerror("Error", f"Gagal membuat folder:\n\n{err}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_new_file(self):
        dialog = ctk.CTkInputDialog(
            title="Buat File Baru",
            text="Masukkan nama file baru (contoh: index.php, .env):"
        )
        file_name = dialog.get_input()
        if not file_name or not file_name.strip():
            return

        file_name = file_name.strip()
        remote_dest = f"{self.current_path.rstrip('/')}/{file_name}"
        self.lbl_status_msg.configure(text=f"Creating file '{file_name}'...", text_color=COLORS["accent_text"])

        def worker():
            full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
            ok, err = SFTPService.create_file(full_host, remote_dest, "")

            def on_done():
                if ok:
                    self._refresh_current_dir()
                    self.lbl_status_msg.configure(text=f"File '{file_name}' dibuat ✓", text_color=COLORS["success_text"])
                    # Buka langsung di editor
                    self._open_file_in_editor(remote_dest)
                else:
                    self.lbl_status_msg.configure(text=f"Failed to create file: {err}", text_color=COLORS["danger"])
                    messagebox.showerror("Error", f"Gagal membuat file:\n\n{err}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _prompt_rename(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = self._get_item_by_id(sel[0])
        if not item:
            return

        old_name = item["name"]
        dialog = ctk.CTkInputDialog(
            title=f"Rename '{old_name}'",
            text=f"Masukkan nama baru untuk '{old_name}':"
        )
        new_name = dialog.get_input()
        if not new_name or not new_name.strip() or new_name.strip() == old_name:
            return

        new_name = new_name.strip()
        new_path = f"{self.current_path.rstrip('/')}/{new_name}"

        def worker():
            full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
            ok, err = SFTPService.rename(full_host, item["path"], new_path)

            def on_done():
                if ok:
                    self._refresh_current_dir()
                    self.lbl_status_msg.configure(text=f"Renamed to '{new_name}' ✓", text_color=COLORS["success_text"])
                else:
                    self.lbl_status_msg.configure(text=f"Rename failed: {err}", text_color=COLORS["danger"])
                    messagebox.showerror("Rename Error", f"Gagal mengubah nama:\n\n{err}", parent=self)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Peringatan", "Pilih file/folder yang ingin dihapus.", parent=self)
            return

        items = [self._get_item_by_id(s) for s in sel]
        items = [i for i in items if i]
        if not items:
            return

        names_str = ", ".join(f"'{i['name']}'" for i in items[:3])
        if len(items) > 3:
            names_str += f" dan {len(items)-3} item lainnya"

        confirm = messagebox.askyesno(
            "Konfirmasi Hapus",
            f"Apakah Anda yakin ingin menghapus {names_str} dari server?\n\nTindakan ini tidak dapat dibatalkan!",
            parent=self
        )
        if not confirm:
            return

        self.lbl_status_msg.configure(text=f"Deleting {len(items)} item(s)...", text_color=COLORS["danger"])

        def worker():
            full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
            for i in items:
                SFTPService.delete_item(full_host, i["path"], is_dir=i["is_dir"])

            def on_done():
                self._refresh_current_dir()
                self.lbl_status_msg.configure(text=f"Deleted {len(items)} item(s) ✓", text_color=COLORS["success_text"])

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _copy_path_to_clipboard(self, path_str: str):
        try:
            self.clipboard_clear()
            self.clipboard_append(path_str)
            self.lbl_status_msg.configure(text=f"Path copied: {path_str}", text_color=COLORS["success_text"])
        except Exception:
            pass

    def _open_terminal_here(self):
        """Membuka sesi SSH terminal pada direktori yang sedang aktif."""
        self._open_terminal_at(self.current_path)

    def _open_terminal_at(self, target_path: str):
        """Membuka sesi SSH terminal pada direktori tertentu."""
        full_host = self.app.db.get_host_by_id(self.host["id"]) or self.host
        res = launch_ssh_terminal(host=dict(full_host), initial_dir=target_path, app=self.app)
        if res.get("success"):
            self.lbl_status_msg.configure(text=f"Terminal opened: {target_path}", text_color=COLORS["success_text"])
        else:
            messagebox.showerror("Terminal Error", res.get("error", "Gagal membuka terminal"), parent=self)
