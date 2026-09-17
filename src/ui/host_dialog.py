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
        self.geometry("520x820")
        self.resizable(False, False)

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
        # Container utama dengan padding
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        title_text = "Edit Host Configuration" if self.host_data else "New Host Configuration"
        lbl_title = ctk.CTkLabel(main_frame, text=title_text, font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(anchor="w", pady=(0, 15))

        # --- FIELD: Label / Host Name ---
        lbl_label = ctk.CTkLabel(main_frame, text="Label / Name:", font=ctk.CTkFont(size=12))
        lbl_label.pack(anchor="w")
        self.ent_label = ctk.CTkEntry(main_frame, placeholder_text="e.g. Production Web Server")
        self.ent_label.pack(fill="x", pady=(0, 10))

        # --- FIELD: Group Selection ---
        lbl_group = ctk.CTkLabel(main_frame, text="Group:", font=ctk.CTkFont(size=12))
        lbl_group.pack(anchor="w")

        grp_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
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
        net_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
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
        lbl_user = ctk.CTkLabel(main_frame, text="Username:", font=ctk.CTkFont(size=12))
        lbl_user.pack(anchor="w")
        self.ent_username = ctk.CTkEntry(main_frame, placeholder_text="e.g. root, ubuntu, or admin")
        self.ent_username.pack(fill="x", pady=(0, 10))

        # --- FIELD: Target Repo Path ---
        lbl_repo = ctk.CTkLabel(main_frame, text="Repository Path:", font=ctk.CTkFont(size=12))
        lbl_repo.pack(anchor="w")
        self.ent_repo_path = ctk.CTkEntry(main_frame, placeholder_text="/var/www/html")
        self.ent_repo_path.insert(0, "/var/www/html")
        self.ent_repo_path.pack(fill="x", pady=(0, 10))

        # --- FIELD: Authentication Method ---
        lbl_auth = ctk.CTkLabel(main_frame, text="Authentication Method:", font=ctk.CTkFont(size=12))
        lbl_auth.pack(anchor="w")
        self.seg_auth = ctk.CTkSegmentedButton(
            main_frame,
            values=["Password", "SSH Key"],
            command=self._on_auth_type_changed
        )
        self.seg_auth.set("Password")
        self.seg_auth.pack(fill="x", pady=(0, 10))

        # Frame Kontainer untuk input Auth (Password / Key)
        self.auth_frame = ctk.CTkFrame(main_frame)
        self.auth_frame.pack(fill="x", pady=(0, 10))

        # Sub-View: Password Input
        self.ent_password = ctk.CTkEntry(self.auth_frame, placeholder_text="Enter SSH password", show="•")
        self.ent_password.pack(fill="x", padx=10, pady=10)

        # Sub-View: SSH Key Option Menu (Awalnya tersembunyi)
        key_titles = ["Select SSH Key"] + [k["title"] for k in self.ssh_keys]
        self.opt_key = ctk.CTkOptionMenu(self.auth_frame, values=key_titles)

        # --- SECTION: Git Credentials ---
        lbl_git_sec = ctk.CTkLabel(main_frame, text="Git Credentials (Optional)", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_git_sec.pack(anchor="w", pady=(10, 5))

        git_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        git_frame.pack(fill="x", pady=(0, 10))
        git_frame.grid_columnconfigure(0, weight=1)
        git_frame.grid_columnconfigure(1, weight=1)

        self.ent_git_user = ctk.CTkEntry(git_frame, placeholder_text="Git Username / Email")
        self.ent_git_user.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.ent_git_pass = ctk.CTkEntry(git_frame, placeholder_text="Git Password / PAT", show="•")
        self.ent_git_pass.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # --- FIELD: Git Branch ---
        lbl_branch = ctk.CTkLabel(main_frame, text="Git Branch (Optional):", font=ctk.CTkFont(size=12))
        lbl_branch.pack(anchor="w", pady=(5, 0))
        self.ent_git_branch = ctk.CTkEntry(main_frame, placeholder_text="e.g. main, master, or production")
        self.ent_git_branch.pack(fill="x", pady=(0, 10))

        # Label Error
        self.lbl_error = ctk.CTkLabel(main_frame, text="", text_color="red", font=ctk.CTkFont(size=11))
        self.lbl_error.pack(anchor="w", pady=(0, 5))

        # --- ACTION BUTTONS ---
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
        btn_cancel.pack(side="left", expand=True, fill="x", padx=(0, 5))

        btn_save = ctk.CTkButton(btn_frame, text="Save Host", command=self._save_host)
        btn_save.pack(side="right", expand=True, fill="x", padx=(5, 0))

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
        selected_group = self.opt_group.get().strip()
        group_id = None
        if selected_group and selected_group != "None":
            matched = next((g for g in self.groups if g["name"].lower() == selected_group.lower()), None)
            if matched:
                group_id = matched["id"]
            else:
                group_id = self.db.add_group(selected_group)
                self.groups = self.db.get_groups()

        # Ambil Auth Data
        auth_type = "password" if auth_type_ui == "Password" else "key"
        password = None
        key_id = None

        if auth_type == "password":
            password = self.ent_password.get()
        else:
            selected_key_title = self.opt_key.get()
            if selected_key_title == "Select SSH Key":
                self.lbl_error.configure(text="Please select an SSH Key.")
                return
            for k in self.ssh_keys:
                if k["title"] == selected_key_title:
                    key_id = k["id"]
                    break

        # Simpan ke Database
        if self.host_data and "id" in self.host_data:
            if hasattr(self.db, 'update_host'):
                self.db.update_host(
                    host_id=self.host_data["id"],
                    label=label,
                    hostname=hostname,
                    username=username,
                    port=port,
                    auth_type=auth_type,
                    password=password,
                    repo_path=repo_path,
                    git_branch=git_branch,
                    git_user=git_user,
                    git_pass=git_pass,
                    key_id=key_id,
                    group_id=group_id
                )
        else:
            self.db.add_host(
                label=label,
                hostname=hostname,
                username=username,
                port=port,
                auth_type=auth_type,
                password=password,
                repo_path=repo_path,
                git_branch=git_branch,
                git_user=git_user,
                git_pass=git_pass,
                key_id=key_id,
                group_id=group_id
            )

        if self.on_save_callback:
            self.on_save_callback()

        self.destroy()