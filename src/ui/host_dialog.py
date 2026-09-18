import customtkinter as ctk
from typing import Optional, Callable, Dict, Any


class HostDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        db_manager: Any,
        host_data: Optional[Dict[str, Any]] = None,
        on_save_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent)

        self.db = db_manager
        self.host_data = host_data
        self.on_save_callback = on_save_callback

        # Set judul modal (Edit / Add)
        is_edit = host_data is not None
        self.title("Edit Host" if is_edit else "Add New Host")

        # Hitung ukuran dan posisi agar selalu terpusat & tidak melebihi batas bawah layar
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        dlg_w = 520
        dlg_h = min(560, max(380, screen_h - 130))

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

        # Agar modal selalu di depan
        self.transient(parent)
        self.grab_set()

        # Data Cache
        self.groups = self.db.get_groups()
        self.ssh_keys = self.db.get_all_ssh_keys() if hasattr(self.db, 'get_all_ssh_keys') else []

        self._setup_ui()
        if is_edit:
            self._load_host_data()

    def _setup_ui(self):
        # 1. FIXED BOTTOM ACTION BAR
        bottom_bar = ctk.CTkFrame(self, fg_color="#18191D", corner_radius=0, border_width=1, border_color="#32343B")
        bottom_bar.pack(side="bottom", fill="x", padx=0, pady=0)

        # Label Error
        self.lbl_error = ctk.CTkLabel(bottom_bar, text="", text_color="#FF453A", font=ctk.CTkFont(size=11))
        self.lbl_error.pack(anchor="w", padx=20, pady=(6, 2))

        btn_frame = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 12))

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            height=34,
            fg_color="transparent",
            border_width=1,
            border_color="#32343B",
            text_color="gray80",
            hover_color="#2A2C33",
            command=self.destroy
        )
        btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 5))

        btn_save = ctk.CTkButton(
            btn_frame,
            text="Save Host",
            height=34,
            fg_color="#0A84FF",
            hover_color="#0072E5",
            font=ctk.CTkFont(weight="bold"),
            command=self._save_host
        )
        btn_save.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # 2. TOP HEADER
        top_header = ctk.CTkFrame(self, fg_color="transparent")
        top_header.pack(side="top", fill="x", padx=20, pady=(16, 6))

        title_text = "Edit Host Configuration" if self.host_data else "New Host Configuration"
        lbl_title = ctk.CTkLabel(top_header, text=title_text, font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(anchor="w")

        # 3. SCROLLABLE FORM BODY
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(side="top", fill="both", expand=True, padx=16, pady=(0, 6))

        # --- FIELD: Label / Host Name ---
        lbl_label = ctk.CTkLabel(self.scroll_frame, text="Label / Name:", font=ctk.CTkFont(size=12))
        lbl_label.pack(anchor="w")
        self.ent_label = ctk.CTkEntry(self.scroll_frame, placeholder_text="e.g. Production Web Server")
        self.ent_label.pack(fill="x", pady=(0, 10))

        # --- FIELD: Group Selection ---
        lbl_group = ctk.CTkLabel(self.scroll_frame, text="Group:", font=ctk.CTkFont(size=12))
        lbl_group.pack(anchor="w")

        grp_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        grp_frame.pack(fill="x", pady=(0, 10))
        grp_frame.grid_columnconfigure(0, weight=1)
        grp_frame.grid_columnconfigure(1, weight=0)

        group_names = ["None"] + [g["name"] for g in self.groups]
        self.opt_group = ctk.CTkComboBox(grp_frame, values=group_names)
        self.opt_group.set("None")
        self.opt_group.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        btn_add_group = ctk.CTkButton(
            grp_frame,
            text="+ Group",
            width=70,
            command=self._create_new_group_prompt
        )
        btn_add_group.grid(row=0, column=1, sticky="e")

        # --- FIELD: Hostname / IP & Port (2 Kolom) ---
        net_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        net_frame.pack(fill="x", pady=(0, 10))
        net_frame.grid_columnconfigure(0, weight=3)
        net_frame.grid_columnconfigure(1, weight=1)

        lbl_host = ctk.CTkLabel(net_frame, text="IP / Hostname:", font=ctk.CTkFont(size=12))
        lbl_host.grid(row=0, column=0, sticky="w")
        self.ent_hostname = ctk.CTkEntry(net_frame, placeholder_text="192.168.1.100 or example.com")
        self.ent_hostname.grid(row=1, column=0, sticky="ew", padx=(0, 5))

        lbl_port = ctk.CTkLabel(net_frame, text="Port:", font=ctk.CTkFont(size=12))
        lbl_port.grid(row=0, column=1, sticky="w")
        self.ent_port = ctk.CTkEntry(net_frame, placeholder_text="22")
        self.ent_port.insert(0, "22")
        self.ent_port.grid(row=1, column=1, sticky="ew")

        # --- FIELD: Username ---
        lbl_user = ctk.CTkLabel(self.scroll_frame, text="Username:", font=ctk.CTkFont(size=12))
        lbl_user.pack(anchor="w")
        self.ent_username = ctk.CTkEntry(self.scroll_frame, placeholder_text="e.g. root, ubuntu, or admin")
        self.ent_username.pack(fill="x", pady=(0, 10))

        # --- FIELD: Target Repo Path ---
        lbl_repo = ctk.CTkLabel(self.scroll_frame, text="Repository Path:", font=ctk.CTkFont(size=12))
        lbl_repo.pack(anchor="w")
        self.ent_repo_path = ctk.CTkEntry(self.scroll_frame, placeholder_text="/var/www/html")
        self.ent_repo_path.insert(0, "/var/www/html")
        self.ent_repo_path.pack(fill="x", pady=(0, 10))

        # --- FIELD: Authentication Method ---
        lbl_auth = ctk.CTkLabel(self.scroll_frame, text="Authentication Method:", font=ctk.CTkFont(size=12))
        lbl_auth.pack(anchor="w")
        self.seg_auth = ctk.CTkSegmentedButton(
            self.scroll_frame,
            values=["Password", "SSH Key"],
            command=self._on_auth_type_changed
        )
        self.seg_auth.set("Password")
        self.seg_auth.pack(fill="x", pady=(0, 10))

        # Frame Kontainer untuk input Auth (Password / Key)
        self.auth_frame = ctk.CTkFrame(self.scroll_frame)
        self.auth_frame.pack(fill="x", pady=(0, 10))

        # Sub-View: Password Input
        self.ent_password = ctk.CTkEntry(self.auth_frame, placeholder_text="Enter SSH password", show="•")
        self.ent_password.pack(fill="x", padx=10, pady=10)

        # Sub-View: SSH Key Option Menu (Awalnya tersembunyi)
        key_titles = ["Select SSH Key"] + [k["title"] for k in self.ssh_keys]
        self.opt_key = ctk.CTkOptionMenu(self.auth_frame, values=key_titles)

        # --- SECTION: Git Credentials ---
        lbl_git_sec = ctk.CTkLabel(self.scroll_frame, text="Git Credentials (Optional)", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_git_sec.pack(anchor="w", pady=(10, 5))

        git_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        git_frame.pack(fill="x", pady=(0, 10))
        git_frame.grid_columnconfigure(0, weight=1)
        git_frame.grid_columnconfigure(1, weight=1)

        self.ent_git_user = ctk.CTkEntry(git_frame, placeholder_text="Git Username / Email")
        self.ent_git_user.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.ent_git_pass = ctk.CTkEntry(git_frame, placeholder_text="Git Password / PAT", show="•")
        self.ent_git_pass.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # --- FIELD: Git Branch ---
        lbl_branch = ctk.CTkLabel(self.scroll_frame, text="Git Branch (Optional):", font=ctk.CTkFont(size=12))
        lbl_branch.pack(anchor="w", pady=(5, 0))
        self.ent_git_branch = ctk.CTkEntry(self.scroll_frame, placeholder_text="e.g. main, master, or production")
        self.ent_git_branch.pack(fill="x", pady=(0, 10))

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

    def _create_new_group_prompt(self):
        """Membuka dialog input untuk membuat group baru dan langsung memilihnya."""
        dialog = ctk.CTkInputDialog(text="Enter new group name:", title="New Group")
        group_name = dialog.get_input()
        if group_name and group_name.strip():
            clean_name = group_name.strip()
            self.db.add_group(clean_name)
            self.groups = self.db.get_groups()
            new_values = ["None"] + [g["name"] for g in self.groups]
            self.opt_group.configure(values=new_values)
            self.opt_group.set(clean_name)

    def _on_auth_type_changed(self, value: str):
        """Mengubah field masukan berdasarkan metode autentikasi yang dipilih."""
        if value == "Password":
            self.opt_key.pack_forget()
            self.ent_password.pack(fill="x", padx=10, pady=10)
        else:
            self.ent_password.pack_forget()
            self.opt_key.pack(fill="x", padx=10, pady=10)

    def _load_host_data(self):
        """Isi field form saat dalam mode Edit."""
        data = self.host_data
        self.ent_label.insert(0, data.get("label", ""))
        self.ent_hostname.insert(0, data.get("hostname", ""))
        self.ent_port.delete(0, "end")
        self.ent_port.insert(0, str(data.get("port", 22)))
        self.ent_username.insert(0, data.get("username", ""))

        # Load Repo Path
        if data.get("repo_path"):
            self.ent_repo_path.delete(0, "end")
            self.ent_repo_path.insert(0, data["repo_path"])

        # Load Git Credentials & Branch
        if data.get("git_user"):
            self.ent_git_user.insert(0, data["git_user"])
        if data.get("git_pass"):
            self.ent_git_pass.insert(0, data["git_pass"])
        if data.get("git_branch"):
            self.ent_git_branch.insert(0, data["git_branch"])

        # Load Group
        if data.get("group_name"):
            self.opt_group.set(data["group_name"])

        # Load Auth Type
        auth_type = "Password" if data.get("auth_type") == "password" else "SSH Key"
        self.seg_auth.set(auth_type)
        self._on_auth_type_changed(auth_type)

        if auth_type == "Password" and data.get("password"):
            self.ent_password.insert(0, data["password"])
        elif auth_type == "SSH Key" and data.get("key_title"):
            self.opt_key.set(data["key_title"])

    def _save_host(self):
        """Validasi dan simpan data ke SQLite."""
        label = self.ent_label.get().strip()
        hostname = self.ent_hostname.get().strip()
        port_str = self.ent_port.get().strip()
        username = self.ent_username.get().strip()
        repo_path = self.ent_repo_path.get().strip() or "/var/www/html"
        git_user = self.ent_git_user.get().strip() or None
        git_pass = self.ent_git_pass.get().strip() or None
        git_branch = self.ent_git_branch.get().strip() or None
        auth_type_ui = self.seg_auth.get()

        # Validasi Sederhana
        if not label or not hostname or not username or not port_str:
            self.lbl_error.configure(text="Please fill in all required fields.")
            return

        try:
            port = int(port_str)
        except ValueError:
            self.lbl_error.configure(text="Port must be a valid number.")
            return

        # Ambil Group ID
        selected_group_name = self.opt_group.get()
        group_id = None
        if selected_group_name != "None":
            for g in self.groups:
                if g["name"] == selected_group_name:
                    group_id = g["id"]
                    break

        # Ambil Auth Data
        if auth_type_ui == "Password":
            auth_type = "password"
            password = self.ent_password.get()
            key_id = None
        else:
            auth_type = "key"
            password = None
            selected_key_title = self.opt_key.get()
            key_id = None
            for k in self.ssh_keys:
                if k["title"] == selected_key_title:
                    key_id = k["id"]
                    break

        if self.host_data:
            # Mode UPDATE
            self.db.update_host(
                host_id=self.host_data["id"],
                label=label,
                hostname=hostname,
                port=port,
                username=username,
                auth_type=auth_type,
                password=password,
                key_id=key_id,
                repo_path=repo_path,
                git_user=git_user,
                git_pass=git_pass,
                git_branch=git_branch,
                group_id=group_id
            )
        else:
            # Mode INSERT
            self.db.add_host(
                label=label,
                hostname=hostname,
                port=port,
                username=username,
                auth_type=auth_type,
                password=password,
                key_id=key_id,
                repo_path=repo_path,
                git_user=git_user,
                git_pass=git_pass,
                git_branch=git_branch,
                group_id=group_id
            )

        if self.on_save_callback:
            self.on_save_callback()

        self.destroy()