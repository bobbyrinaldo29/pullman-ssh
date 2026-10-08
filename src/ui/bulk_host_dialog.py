from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk
from tkinter import messagebox

from theme import COLORS
from icons import get_icon


class BulkHostDialog(ctk.CTkToplevel):
    """Dialog untuk memperbarui properti beberapa server SSH (Bulk Edit) secara bersamaan."""

    def __init__(
        self,
        parent: ctk.CTk,
        db_manager: Any,
        host_ids: List[int],
        on_save_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent, fg_color=COLORS["window"])

        self.db = db_manager
        self.host_ids = host_ids
        self.on_save_callback = on_save_callback

        self.title(f"Bulk Edit ({len(host_ids)} Hosts)")

        # Ukuran & Posisi
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        dlg_w = 540
        dlg_h = min(620, max(420, screen_h - 120))

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

        self.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")
        self.minsize(480, 400)
        self.resizable(True, True)

        self.transient(parent)
        self.grab_set()

        # Cache Groups & SSH Keys
        self.groups = self.db.get_groups()
        self.ssh_keys = self.db.get_all_ssh_keys() if hasattr(self.db, 'get_all_ssh_keys') else []

        self._setup_ui()

    def _setup_ui(self):
        # 1. FIXED BOTTOM ACTION BAR
        bottom_bar = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, border_width=1, border_color=COLORS["line"])
        bottom_bar.pack(side="bottom", fill="x")

        self.lbl_error = ctk.CTkLabel(bottom_bar, text="", text_color=COLORS["danger"], font=ctk.CTkFont(size=11))
        self.lbl_error.pack(anchor="w", padx=20, pady=(6, 2))

        btn_frame = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            height=34,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["line"],
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["surface_hover"],
            command=self.destroy
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btn_frame,
            text=f" Apply Changes ({len(self.host_ids)} Hosts)",
            image=get_icon("check", (14, 14), "#FFFFFF"),
            compound="left",
            height=34,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(weight="bold"),
            command=self._apply_bulk_update
        ).pack(side="right", expand=True, fill="x", padx=(6, 0))

        # 2. TOP HEADER
        top_header = ctk.CTkFrame(self, fg_color="transparent")
        top_header.pack(side="top", fill="x", padx=20, pady=(16, 6))

        ctk.CTkLabel(
            top_header,
            text=f"Bulk Edit ({len(self.host_ids)} Hosts)",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            top_header,
            text="Centang opsi yang ingin Anda perbarui secara massal. Field yang tidak dicentang tidak akan diubah.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=12),
            wraplength=480,
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # 3. SCROLLABLE FORM
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(6, 10))

        # --- FIELD: GROUP ---
        self.chk_group_var = ctk.BooleanVar(value=False)
        grp_card = self._create_field_card(scroll, "Group Server", self.chk_group_var, self._toggle_group)
        
        grp_names = ["(Tanpa Group)"] + [g["name"] for g in self.groups]
        self.opt_group = ctk.CTkOptionMenu(
            grp_card,
            values=grp_names,
            height=32,
            fg_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            button_color=COLORS["surface_active"],
            state="disabled"
        )
        self.opt_group.pack(fill="x", padx=12, pady=(0, 10))
        self.opt_group.set(grp_names[0])

        # --- FIELD: GIT BRANCH ---
        self.chk_branch_var = ctk.BooleanVar(value=False)
        branch_card = self._create_field_card(scroll, "Git Branch", self.chk_branch_var, self._toggle_branch)
        
        self.ent_branch = ctk.CTkEntry(
            branch_card,
            placeholder_text="Contoh: production, main, release/v2...",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_branch.pack(fill="x", padx=12, pady=(0, 10))

        # --- FIELD: REPO PATH ---
        self.chk_repo_var = ctk.BooleanVar(value=False)
        repo_card = self._create_field_card(scroll, "Repository Path", self.chk_repo_var, self._toggle_repo)
        
        self.ent_repo = ctk.CTkEntry(
            repo_card,
            placeholder_text="Contoh: /var/www/html/my-app",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_repo.pack(fill="x", padx=12, pady=(0, 10))

        # --- FIELD: SSH USERNAME & PORT ---
        self.chk_user_port_var = ctk.BooleanVar(value=False)
        user_card = self._create_field_card(scroll, "SSH Username & Port", self.chk_user_port_var, self._toggle_user_port)
        
        row_up = ctk.CTkFrame(user_card, fg_color="transparent")
        row_up.pack(fill="x", padx=12, pady=(0, 10))
        row_up.grid_columnconfigure(0, weight=3)
        row_up.grid_columnconfigure(1, weight=1)

        self.ent_user = ctk.CTkEntry(
            row_up,
            placeholder_text="Username (misal: root, ubuntu)",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_user.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.ent_port = ctk.CTkEntry(
            row_up,
            placeholder_text="Port (22)",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_port.grid(row=0, column=1, sticky="ew")

        # --- FIELD: SSH AUTHENTICATION ---
        self.chk_auth_var = ctk.BooleanVar(value=False)
        auth_card = self._create_field_card(scroll, "SSH Authentication (Password / Key)", self.chk_auth_var, self._toggle_auth)
        
        self.auth_mode_var = ctk.StringVar(value="password")
        self.seg_auth = ctk.CTkSegmentedButton(
            auth_card,
            values=["Password", "SSH Key"],
            variable=self.auth_mode_var,
            command=self._on_auth_mode_changed,
            state="disabled"
        )
        self.seg_auth.pack(fill="x", padx=12, pady=(0, 8))

        self.ent_ssh_pass = ctk.CTkEntry(
            auth_card,
            placeholder_text="Masukkan password SSH baru...",
            show="•",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_ssh_pass.pack(fill="x", padx=12, pady=(0, 10))

        key_titles = [f"{k.get('title', 'Key #' + str(k.get('id')))}" for k in self.ssh_keys] or ["(No SSH Keys saved)"]
        self.opt_ssh_key = ctk.CTkOptionMenu(
            auth_card,
            values=key_titles,
            height=32,
            fg_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            state="disabled"
        )

        # --- FIELD: GIT CREDENTIALS ---
        self.chk_git_cred_var = ctk.BooleanVar(value=False)
        git_card = self._create_field_card(scroll, "Git Credential Override", self.chk_git_cred_var, self._toggle_git_cred)
        
        self.ent_git_user = ctk.CTkEntry(
            git_card,
            placeholder_text="Git Username / Email",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_git_user.pack(fill="x", padx=12, pady=(0, 6))

        self.ent_git_token = ctk.CTkEntry(
            git_card,
            placeholder_text="Git Personal Access Token / Password",
            show="•",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_git_token.pack(fill="x", padx=12, pady=(0, 10))

    def _create_field_card(self, parent, title: str, var: ctk.BooleanVar, command: Callable) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8, border_width=1, border_color=COLORS["line"])
        card.pack(fill="x", pady=5)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 6))

        chk = ctk.CTkCheckBox(
            header,
            text=f" Update {title}",
            variable=var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            checkbox_width=17,
            checkbox_height=17,
            command=command
        )
        chk.pack(side="left")
        return card

    # Toggles
    def _toggle_group(self):
        st = "normal" if self.chk_group_var.get() else "disabled"
        self.opt_group.configure(state=st)

    def _toggle_branch(self):
        st = "normal" if self.chk_branch_var.get() else "disabled"
        self.ent_branch.configure(state=st)

    def _toggle_repo(self):
        st = "normal" if self.chk_repo_var.get() else "disabled"
        self.ent_repo.configure(state=st)

    def _toggle_user_port(self):
        st = "normal" if self.chk_user_port_var.get() else "disabled"
        self.ent_user.configure(state=st)
        self.ent_port.configure(state=st)

    def _toggle_auth(self):
        st = "normal" if self.chk_auth_var.get() else "disabled"
        self.seg_auth.configure(state=st)
        self._on_auth_mode_changed(self.auth_mode_var.get())

    def _on_auth_mode_changed(self, mode: str):
        is_active = self.chk_auth_var.get()
        if not is_active:
            self.ent_ssh_pass.configure(state="disabled")
            if self.opt_ssh_key.winfo_ismapped():
                self.opt_ssh_key.pack_forget()
                self.ent_ssh_pass.pack(fill="x", padx=12, pady=(0, 10))
            return

        if mode == "Password":
            if self.opt_ssh_key.winfo_ismapped():
                self.opt_ssh_key.pack_forget()
            self.ent_ssh_pass.pack(fill="x", padx=12, pady=(0, 10))
            self.ent_ssh_pass.configure(state="normal")
        else:
            if self.ent_ssh_pass.winfo_ismapped():
                self.ent_ssh_pass.pack_forget()
            self.opt_ssh_key.pack(fill="x", padx=12, pady=(0, 10))
            self.opt_ssh_key.configure(state="normal")

    def _toggle_git_cred(self):
        st = "normal" if self.chk_git_cred_var.get() else "disabled"
        self.ent_git_user.configure(state=st)
        self.ent_git_token.configure(state=st)

    # Apply
    def _apply_bulk_update(self):
        self.lbl_error.configure(text="")
        updates: Dict[str, Any] = {}

        if self.chk_group_var.get():
            sel_grp = self.opt_group.get()
            if sel_grp == "(Tanpa Group)":
                updates["group_id"] = None
            else:
                grp_obj = next((g for g in self.groups if g["name"] == sel_grp), None)
                updates["group_id"] = grp_obj["id"] if grp_obj else None

        if self.chk_branch_var.get():
            branch = self.ent_branch.get().strip()
            updates["git_branch"] = branch if branch else None

        if self.chk_repo_var.get():
            repo = self.ent_repo.get().strip()
            if not repo:
                self.lbl_error.configure(text="Repo Path tidak boleh kosong jika dicentang.")
                return
            updates["repo_path"] = repo

        if self.chk_user_port_var.get():
            u = self.ent_user.get().strip()
            p = self.ent_port.get().strip()
            if u:
                updates["username"] = u
            if p:
                try:
                    updates["port"] = int(p)
                except ValueError:
                    self.lbl_error.configure(text="Port harus berupa angka (contoh: 22).")
                    return

        if self.chk_auth_var.get():
            auth_mode = self.auth_mode_var.get()
            if auth_mode == "Password":
                pwd = self.ent_ssh_pass.get()
                updates["auth_type"] = "password"
                updates["password"] = pwd
            else:
                updates["auth_type"] = "key"
                sel_key_title = self.opt_ssh_key.get()
                key_obj = next((k for k in self.ssh_keys if k.get("title") == sel_key_title), None)
                updates["key_id"] = key_obj["id"] if key_obj else None

        if self.chk_git_cred_var.get():
            gu = self.ent_git_user.get().strip()
            gt = self.ent_git_token.get().strip()
            updates["git_user"] = gu if gu else None
            updates["git_pass"] = gt if gt else None

        if not updates:
            self.lbl_error.configure(text="Pilih minimal 1 opsi untuk diperbarui.")
            return

        try:
            count = self.db.bulk_update_hosts(self.host_ids, updates)
            if self.on_save_callback:
                self.on_save_callback()
            messagebox.showinfo("Bulk Edit Berhasil", f"Berhasil memperbarui {count} host secara massal.")
            self.destroy()
        except Exception as e:
            self.lbl_error.configure(text=f"Gagal memperbarui: {str(e)}")
