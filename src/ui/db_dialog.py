import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, Callable, Dict, Any
import threading
from db_executor import run_db_query


class DBConnectionDialog(ctk.CTkToplevel):
    """Dialog untuk menambah atau mengedit koneksi database (Navicat-style).
    Didesain responsif dengan pinned bottom bar agar tombol aksi (Save, Cancel, Test)
    selalu terlihat dan tidak terpotong di layar mana pun.
    """

    def __init__(
        self,
        parent: ctk.CTk,
        db_manager: Any,
        connection_data: Optional[Dict[str, Any]] = None,
        on_save_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)

        self.db = db_manager
        self.conn_data = connection_data
        self.on_save_callback = on_save_callback

        is_edit = connection_data is not None
        self.title("Edit Database Connection" if is_edit else "New Database Connection")

        # Hitung ukuran dan posisi agar selalu terpusat & tidak melebihi batas bawah layar
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        dlg_w = 540
        dlg_h = min(540, max(380, screen_h - 130))

        try:
            parent.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = max(10, px + (pw - dlg_w) // 2)
            y = max(10, py + (ph - dlg_h) // 2)
        except Exception:
            x = (screen_w - dlg_w) // 2
            y = (screen_h - dlg_h) // 2

        if y + dlg_h > screen_h - 60:
            y = max(10, screen_h - 60 - dlg_h)

        self.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")
        self.minsize(460, 360)
        self.resizable(True, True)

        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        if is_edit:
            self._load_connection_data()

    def _setup_ui(self):
        # 1. FIXED BOTTOM ACTION BAR (Selalu berada di bagian bawah dan selalu terlihat)
        bottom_bar = ctk.CTkFrame(self, fg_color="#18191D", corner_radius=0, border_width=1, border_color="#32343B")
        bottom_bar.pack(side="bottom", fill="x", padx=0, pady=0)

        # Baris error label
        self.lbl_error = ctk.CTkLabel(bottom_bar, text="", text_color="#FF453A", font=ctk.CTkFont(size=11))
        self.lbl_error.pack(anchor="w", padx=20, pady=(6, 2))

        btn_container = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        btn_container.pack(fill="x", padx=20, pady=(0, 12))

        self.btn_test = ctk.CTkButton(
            btn_container,
            text="⚡ Test Connection",
            height=34,
            fg_color="#18283E",
            hover_color="#223B5D",
            text_color="#60A5FA",
            border_width=1,
            border_color="#254A78",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._test_connection
        )
        self.btn_test.pack(side="left")

        btn_save = ctk.CTkButton(
            btn_container,
            text="Save Connection",
            height=34,
            fg_color="#0A84FF",
            hover_color="#0072E5",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_connection
        )
        btn_save.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(
            btn_container,
            text="Cancel",
            height=34,
            fg_color="transparent",
            border_width=1,
            border_color="#32343B",
            text_color="gray80",
            hover_color="#2A2C33",
            command=self.destroy
        )
        btn_cancel.pack(side="right")

        # 2. TOP HEADER
        top_header = ctk.CTkFrame(self, fg_color="transparent")
        top_header.pack(side="top", fill="x", padx=20, pady=(16, 6))

        title_text = "Edit Database Connection" if self.conn_data else "New Database Connection"
        lbl_title = ctk.CTkLabel(top_header, text=title_text, font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(anchor="w")

        # 3. SCROLLABLE FORM BODY (Mengisi sisa ruang secara fleksibel)
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(side="top", fill="both", expand=True, padx=16, pady=(0, 6))

        # --- FIELD: Connection Name & DB Type ---
        name_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        name_frame.pack(fill="x", pady=(0, 10))
        name_frame.grid_columnconfigure(0, weight=3)
        name_frame.grid_columnconfigure(1, weight=1)

        lbl_name = ctk.CTkLabel(name_frame, text="Connection Name:", font=ctk.CTkFont(size=12))
        lbl_name.grid(row=0, column=0, sticky="w")
        self.ent_name = ctk.CTkEntry(name_frame, placeholder_text="e.g. Master DB Staging")
        self.ent_name.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        lbl_type = ctk.CTkLabel(name_frame, text="Type:", font=ctk.CTkFont(size=12))
        lbl_type.grid(row=0, column=1, sticky="w")
        self.opt_type = ctk.CTkComboBox(name_frame, values=["MYSQL", "MARIADB", "POSTGRESQL"])
        self.opt_type.set("MYSQL")
        self.opt_type.grid(row=1, column=1, sticky="ew")

        # --- FIELD: Group ---
        lbl_group = ctk.CTkLabel(self.scroll_frame, text="Group / Category:", font=ctk.CTkFont(size=12))
        lbl_group.pack(anchor="w")
        self.ent_group = ctk.CTkEntry(self.scroll_frame, placeholder_text="Default")
        self.ent_group.insert(0, "Default")
        self.ent_group.pack(fill="x", pady=(0, 12))

        # --- SECTION: Database Server Settings ---
        lbl_db_sec = ctk.CTkLabel(self.scroll_frame, text="Database Server Settings", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_db_sec.pack(anchor="w", pady=(5, 5))

        db_box = ctk.CTkFrame(self.scroll_frame, fg_color="#1D1E22", corner_radius=10, border_width=1, border_color="#32343B")
        db_box.pack(fill="x", pady=(0, 14), padx=2, ipady=8)

        # Host & Port
        host_frame = ctk.CTkFrame(db_box, fg_color="transparent")
        host_frame.pack(fill="x", padx=12, pady=(6, 6))
        host_frame.grid_columnconfigure(0, weight=3)
        host_frame.grid_columnconfigure(1, weight=1)

        lbl_host = ctk.CTkLabel(host_frame, text="Host / IP:", font=ctk.CTkFont(size=12))
        lbl_host.grid(row=0, column=0, sticky="w")
        self.ent_host = ctk.CTkEntry(host_frame, placeholder_text="localhost or 127.0.0.1")
        self.ent_host.insert(0, "localhost")
        self.ent_host.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        lbl_port = ctk.CTkLabel(host_frame, text="Port:", font=ctk.CTkFont(size=12))
        lbl_port.grid(row=0, column=1, sticky="w")
        self.ent_port = ctk.CTkEntry(host_frame, placeholder_text="3306")
        self.ent_port.insert(0, "3306")
        self.ent_port.grid(row=1, column=1, sticky="ew")

        # Database Name
        lbl_dbname = ctk.CTkLabel(db_box, text="Database Name (Optional):", font=ctk.CTkFont(size=12))
        lbl_dbname.pack(anchor="w", padx=12)
        self.ent_database = ctk.CTkEntry(db_box, placeholder_text="e.g. ecommerce_db")
        self.ent_database.pack(fill="x", padx=12, pady=(2, 6))

        # DB Username & Password
        user_frame = ctk.CTkFrame(db_box, fg_color="transparent")
        user_frame.pack(fill="x", padx=12, pady=(4, 6))
        user_frame.grid_columnconfigure(0, weight=1)
        user_frame.grid_columnconfigure(1, weight=1)

        lbl_user = ctk.CTkLabel(user_frame, text="DB Username:", font=ctk.CTkFont(size=12))
        lbl_user.grid(row=0, column=0, sticky="w")
        self.ent_username = ctk.CTkEntry(user_frame, placeholder_text="root")
        self.ent_username.insert(0, "root")
        self.ent_username.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        lbl_pass = ctk.CTkLabel(user_frame, text="DB Password:", font=ctk.CTkFont(size=12))
        lbl_pass.grid(row=0, column=1, sticky="w")
        self.ent_password = ctk.CTkEntry(user_frame, placeholder_text="Enter password", show="•")
        self.ent_password.grid(row=1, column=1, sticky="ew", padx=(6, 0))

        # --- SECTION: SSH Tunnel Settings ---
        ssh_header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        ssh_header.pack(fill="x", pady=(5, 5))

        self.use_ssh_var = ctk.BooleanVar(value=True)
        self.chk_use_ssh = ctk.CTkCheckBox(
            ssh_header,
            text="Use SSH Tunnel (Navicat SSH Mode)",
            variable=self.use_ssh_var,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_ssh_fields
        )
        self.chk_use_ssh.pack(side="left")

        self.ssh_box = ctk.CTkFrame(self.scroll_frame, fg_color="#1D1E22", corner_radius=10, border_width=1, border_color="#32343B")
        self.ssh_box.pack(fill="x", pady=(0, 15), padx=2, ipady=8)

        # SSH Host & Port
        ssh_host_frame = ctk.CTkFrame(self.ssh_box, fg_color="transparent")
        ssh_host_frame.pack(fill="x", padx=12, pady=(6, 6))
        ssh_host_frame.grid_columnconfigure(0, weight=3)
        ssh_host_frame.grid_columnconfigure(1, weight=1)

        lbl_ssh_host = ctk.CTkLabel(ssh_host_frame, text="SSH Host / IP:", font=ctk.CTkFont(size=12))
        lbl_ssh_host.grid(row=0, column=0, sticky="w")
        self.ent_ssh_host = ctk.CTkEntry(ssh_host_frame, placeholder_text="e.g. 104.234.180.117")
        self.ent_ssh_host.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        lbl_ssh_port = ctk.CTkLabel(ssh_host_frame, text="SSH Port:", font=ctk.CTkFont(size=12))
        lbl_ssh_port.grid(row=0, column=1, sticky="w")
        self.ent_ssh_port = ctk.CTkEntry(ssh_host_frame, placeholder_text="22")
        self.ent_ssh_port.insert(0, "22")
        self.ent_ssh_port.grid(row=1, column=1, sticky="ew")

        # SSH Username & Password
        ssh_auth_frame = ctk.CTkFrame(self.ssh_box, fg_color="transparent")
        ssh_auth_frame.pack(fill="x", padx=12, pady=(4, 6))
        ssh_auth_frame.grid_columnconfigure(0, weight=1)
        ssh_auth_frame.grid_columnconfigure(1, weight=1)

        lbl_ssh_user = ctk.CTkLabel(ssh_auth_frame, text="SSH Username:", font=ctk.CTkFont(size=12))
        lbl_ssh_user.grid(row=0, column=0, sticky="w")
        self.ent_ssh_username = ctk.CTkEntry(ssh_auth_frame, placeholder_text="root")
        self.ent_ssh_username.insert(0, "root")
        self.ent_ssh_username.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        lbl_ssh_pass = ctk.CTkLabel(ssh_auth_frame, text="SSH Password:", font=ctk.CTkFont(size=12))
        lbl_ssh_pass.grid(row=0, column=1, sticky="w")
        self.ent_ssh_password = ctk.CTkEntry(ssh_auth_frame, placeholder_text="SSH password", show="•")
        self.ent_ssh_password.grid(row=1, column=1, sticky="ew", padx=(6, 0))

        # SSH Private Key (Optional)
        lbl_ssh_key = ctk.CTkLabel(self.ssh_box, text="SSH Private Key Path (Optional):", font=ctk.CTkFont(size=12))
        lbl_ssh_key.pack(anchor="w", padx=12)
        self.ent_ssh_key = ctk.CTkEntry(self.ssh_box, placeholder_text="e.g. C:/Users/.../.ssh/id_rsa")
        self.ent_ssh_key.pack(fill="x", padx=12, pady=(2, 6))

        # Bind mousewheel scroll agar bisa di-scroll dengan mulus di mana saja
        self.after(50, lambda: self._bind_mousewheel(self.scroll_frame))

    def _bind_mousewheel(self, widget):
        try:
            canvas = self.scroll_frame._parent_canvas
            def _scroll(event):
                canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")
            widget.bind("<MouseWheel>", _scroll, add="+")
            for child in widget.winfo_children():
                self._bind_mousewheel(child)
        except Exception:
            pass

    def _toggle_ssh_fields(self):
        if self.use_ssh_var.get():
            self.ssh_box.pack(fill="x", pady=(0, 15), padx=2, ipady=8)
        else:
            self.ssh_box.pack_forget()

    def _load_connection_data(self):
        d = self.conn_data
        self.ent_name.insert(0, d.get("name", ""))
        self.opt_type.set(d.get("db_type", "MYSQL"))
        self.ent_group.delete(0, "end")
        self.ent_group.insert(0, d.get("group_name", "Default"))

        self.ent_host.delete(0, "end")
        self.ent_host.insert(0, d.get("host", "localhost"))
        self.ent_port.delete(0, "end")
        self.ent_port.insert(0, str(d.get("port", 3306)))

        if d.get("database_name"):
            self.ent_database.insert(0, d["database_name"])

        self.ent_username.delete(0, "end")
        self.ent_username.insert(0, d.get("username", "root"))
        if d.get("password"):
            self.ent_password.insert(0, d["password"])

        use_ssh = bool(d.get("use_ssh", 1))
        self.use_ssh_var.set(use_ssh)
        self._toggle_ssh_fields()

        if d.get("ssh_host"):
            self.ent_ssh_host.insert(0, d["ssh_host"])
        self.ent_ssh_port.delete(0, "end")
        self.ent_ssh_port.insert(0, str(d.get("ssh_port", 22)))
        if d.get("ssh_username"):
            self.ent_ssh_username.delete(0, "end")
            self.ent_ssh_username.insert(0, d["ssh_username"])
        if d.get("ssh_password"):
            self.ent_ssh_password.insert(0, d["ssh_password"])
        if d.get("ssh_key_filename"):
            self.ent_ssh_key.insert(0, d["ssh_key_filename"])

    def _get_form_dict(self) -> Optional[Dict[str, Any]]:
        name = self.ent_name.get().strip()
        db_type = self.opt_type.get().strip()
        group_name = self.ent_group.get().strip() or "Default"
        host = self.ent_host.get().strip() or "localhost"
        port_str = self.ent_port.get().strip()
        database_name = self.ent_database.get().strip() or None
        username = self.ent_username.get().strip() or "root"
        password = self.ent_password.get()
        use_ssh = self.use_ssh_var.get()
        ssh_host = self.ent_ssh_host.get().strip()
        ssh_port_str = self.ent_ssh_port.get().strip()
        ssh_user = self.ent_ssh_username.get().strip() or "root"
        ssh_pass = self.ent_ssh_password.get()
        ssh_key = self.ent_ssh_key.get().strip() or None

        if not name:
            self.lbl_error.configure(text="Connection name is required.")
            return None

        try:
            port = int(port_str) if port_str else 3306
        except ValueError:
            self.lbl_error.configure(text="Port must be a valid integer.")
            return None

        try:
            ssh_port = int(ssh_port_str) if ssh_port_str else 22
        except ValueError:
            self.lbl_error.configure(text="SSH Port must be a valid integer.")
            return None

        if use_ssh and not ssh_host:
            self.lbl_error.configure(text="SSH Host is required when SSH Tunnel is enabled.")
            return None

        return {
            "name": name,
            "db_type": db_type,
            "group_name": group_name,
            "host": host,
            "port": port,
            "database_name": database_name,
            "username": username,
            "password": password,
            "use_ssh": 1 if use_ssh else 0,
            "ssh_host": ssh_host,
            "ssh_port": ssh_port,
            "ssh_username": ssh_user,
            "ssh_password": ssh_pass,
            "ssh_key_filename": ssh_key,
        }

    def _test_connection(self):
        form_data = self._get_form_dict()
        if not form_data:
            return

        self.btn_test.configure(state="disabled", text="Testing...")
        self.lbl_error.configure(text="")

        def worker():
            res = run_db_query(form_data, "SELECT VERSION();", timeout=10)

            def update():
                self.btn_test.configure(state="normal", text="⚡ Test Connection")
                if res["success"]:
                    messagebox.showinfo(
                        "Connection Successful",
                        f"Koneksi Database Berhasil!\n\nResponse time: {res['elapsed_ms']} ms\nOutput:\n{res['output'].strip()}"
                    )
                else:
                    messagebox.showerror(
                        "Connection Failed",
                        f"Koneksi Gagal!\n\nError:\n{res['error']}"
                    )

            self.after(0, update)

        threading.Thread(target=worker, daemon=True).start()

    def _save_connection(self):
        form_data = self._get_form_dict()
        if not form_data:
            return

        try:
            if self.conn_data and "id" in self.conn_data:
                self.db.update_db_connection(
                    conn_id=self.conn_data["id"],
                    name=form_data["name"],
                    db_type=form_data["db_type"],
                    host=form_data["host"],
                    port=form_data["port"],
                    username=form_data["username"],
                    password=form_data["password"],
                    database_name=form_data["database_name"],
                    use_ssh=bool(form_data["use_ssh"]),
                    ssh_host=form_data["ssh_host"],
                    ssh_port=form_data["ssh_port"],
                    ssh_username=form_data["ssh_username"],
                    ssh_password=form_data["ssh_password"],
                    ssh_key_filename=form_data["ssh_key_filename"],
                    group_name=form_data["group_name"]
                )
            else:
                self.db.add_db_connection(
                    name=form_data["name"],
                    db_type=form_data["db_type"],
                    host=form_data["host"],
                    port=form_data["port"],
                    username=form_data["username"],
                    password=form_data["password"],
                    database_name=form_data["database_name"],
                    use_ssh=bool(form_data["use_ssh"]),
                    ssh_host=form_data["ssh_host"],
                    ssh_port=form_data["ssh_port"],
                    ssh_username=form_data["ssh_username"],
                    ssh_password=form_data["ssh_password"],
                    ssh_key_filename=form_data["ssh_key_filename"],
                    group_name=form_data["group_name"]
                )

            if self.on_save_callback:
                self.on_save_callback()

            self.destroy()
        except Exception as e:
            self.lbl_error.configure(text=f"Failed to save: {str(e)}")
