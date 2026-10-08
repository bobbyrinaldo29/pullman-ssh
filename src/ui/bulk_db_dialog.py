from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk
from tkinter import messagebox

from theme import COLORS
from icons import get_icon


class BulkDbDialog(ctk.CTkToplevel):
    """Dialog untuk memperbarui properti beberapa koneksi DB Blast secara bersamaan."""

    DEFAULT_PORTS = {
        "MYSQL": "3306",
        "POSTGRESQL": "5432",
        "SQLSERVER": "1433",
        "SQLITE": "",
    }

    def __init__(
        self,
        parent: ctk.CTk,
        db_manager: Any,
        conn_ids: List[int],
        on_save_callback: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent, fg_color=COLORS["window"])

        self.db = db_manager
        self.conn_ids = conn_ids
        self.on_save_callback = on_save_callback

        self.title(f"Bulk Edit ({len(conn_ids)} DB Connections)")

        # Ukuran & Posisi
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        dlg_w = 540
        dlg_h = min(600, max(420, screen_h - 120))

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

        # Cache Groups
        self.groups = self.db.get_groups()

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
            text=f" Apply Changes ({len(self.conn_ids)} DBs)",
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
            text=f"Bulk Edit ({len(self.conn_ids)} DB Connections)",
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
        grp_card = self._create_field_card(scroll, "Group Database", self.chk_group_var, self._toggle_group)
        
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

        # --- FIELD: DATABASE ENGINE / TYPE ---
        self.chk_type_var = ctk.BooleanVar(value=False)
        type_card = self._create_field_card(scroll, "Database Engine / Type", self.chk_type_var, self._toggle_type)

        self.opt_type = ctk.CTkOptionMenu(
            type_card,
            values=["MySQL", "PostgreSQL", "SQL Server", "SQLite"],
            height=32,
            fg_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            button_color=COLORS["surface_active"],
            state="disabled",
            command=self._on_type_changed
        )
        self.opt_type.pack(fill="x", padx=12, pady=(0, 10))
        self.opt_type.set("MySQL")

        # --- FIELD: HOST & PORT ---
        self.chk_host_port_var = ctk.BooleanVar(value=False)
        host_card = self._create_field_card(scroll, "Host / IP & Port", self.chk_host_port_var, self._toggle_host_port)

        row_hp = ctk.CTkFrame(host_card, fg_color="transparent")
        row_hp.pack(fill="x", padx=12, pady=(0, 10))
        row_hp.grid_columnconfigure(0, weight=3)
        row_hp.grid_columnconfigure(1, weight=1)

        self.ent_host = ctk.CTkEntry(
            row_hp,
            placeholder_text="Host / IP (misal: 127.0.0.1, localhost)",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_host.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.ent_port = ctk.CTkEntry(
            row_hp,
            placeholder_text="Port (3306)",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_port.grid(row=0, column=1, sticky="ew")

        # --- FIELD: AUTHENTICATION (USERNAME & PASSWORD) ---
        self.chk_auth_var = ctk.BooleanVar(value=False)
        auth_card = self._create_field_card(scroll, "Database Credentials (User & Password)", self.chk_auth_var, self._toggle_auth)

        row_auth = ctk.CTkFrame(auth_card, fg_color="transparent")
        row_auth.pack(fill="x", padx=12, pady=(0, 10))
        row_auth.grid_columnconfigure(0, weight=1)
        row_auth.grid_columnconfigure(1, weight=1)

        self.ent_user = ctk.CTkEntry(
            row_auth,
            placeholder_text="Username (misal: root, dbuser)",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_user.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.ent_pass = ctk.CTkEntry(
            row_auth,
            placeholder_text="Password Baru (Kosongkan jika no pass)",
            show="•",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_pass.grid(row=0, column=1, sticky="ew")

        # --- FIELD: DATABASE NAME ---
        self.chk_dbname_var = ctk.BooleanVar(value=False)
        dbname_card = self._create_field_card(scroll, "Database Name", self.chk_dbname_var, self._toggle_dbname)

        self.ent_dbname = ctk.CTkEntry(
            dbname_card,
            placeholder_text="Nama Database Default (misal: production_db)",
            height=32,
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text"],
            state="disabled"
        )
        self.ent_dbname.pack(fill="x", padx=12, pady=(0, 10))

    def _create_field_card(self, parent: Any, label_text: str, chk_var: ctk.BooleanVar, toggle_fn: Callable) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["surface"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"]
        )
        card.pack(fill="x", pady=4)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 6))

        chk = ctk.CTkCheckBox(
            header,
            text=label_text,
            variable=chk_var,
            command=toggle_fn,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12, weight="bold")
        )
        chk.pack(side="left")

        return card

    # --- TOGGLE HANDLERS ---
    def _toggle_group(self):
        state = "normal" if self.chk_group_var.get() else "disabled"
        self.opt_group.configure(state=state)

    def _toggle_type(self):
        state = "normal" if self.chk_type_var.get() else "disabled"
        self.opt_type.configure(state=state)

    def _on_type_changed(self, chosen: str):
        type_key = chosen.upper().replace(" ", "")
        default_port = self.DEFAULT_PORTS.get(type_key, "3306")
        if self.chk_host_port_var.get() and not self.ent_port.get().strip():
            self.ent_port.delete(0, "end")
            self.ent_port.insert(0, default_port)

    def _toggle_host_port(self):
        state = "normal" if self.chk_host_port_var.get() else "disabled"
        self.ent_host.configure(state=state)
        self.ent_port.configure(state=state)
        if state == "normal" and not self.ent_port.get().strip():
            self.ent_port.insert(0, "3306")

    def _toggle_auth(self):
        state = "normal" if self.chk_auth_var.get() else "disabled"
        self.ent_user.configure(state=state)
        self.ent_pass.configure(state=state)

    def _toggle_dbname(self):
        state = "normal" if self.chk_dbname_var.get() else "disabled"
        self.ent_dbname.configure(state=state)

    # --- APPLY UPDATE ---
    def _apply_bulk_update(self):
        self.lbl_error.configure(text="")
        updates: Dict[str, Any] = {}

        has_any = (
            self.chk_group_var.get() or
            self.chk_type_var.get() or
            self.chk_host_port_var.get() or
            self.chk_auth_var.get() or
            self.chk_dbname_var.get()
        )

        if not has_any:
            self.lbl_error.configure(text="Pilih setidaknya satu opsi yang ingin diperbarui.")
            return

        # 1. Group
        if self.chk_group_var.get():
            selected_grp = self.opt_group.get()
            if selected_grp == "(Tanpa Group)":
                updates["group_id"] = None
            else:
                match = next((g for g in self.groups if g["name"] == selected_grp), None)
                updates["group_id"] = match["id"] if match else None

        # 2. Database Type
        if self.chk_type_var.get():
            updates["db_type"] = self.opt_type.get().upper().replace(" ", "")

        # 3. Host & Port
        if self.chk_host_port_var.get():
            host_val = self.ent_host.get().strip()
            port_val = self.ent_port.get().strip()

            if host_val:
                updates["db_host"] = host_val
            if port_val:
                if not port_val.isdigit() or not (1 <= int(port_val) <= 65535):
                    self.lbl_error.configure(text="Port harus berupa angka antara 1 dan 65535.")
                    return
                updates["db_port"] = int(port_val)

        # 4. Authentication
        if self.chk_auth_var.get():
            user_val = self.ent_user.get().strip()
            pass_val = self.ent_pass.get()
            if user_val:
                updates["db_username"] = user_val
            updates["db_password"] = pass_val

        # 5. Database Name
        if self.chk_dbname_var.get():
            updates["db_database_name"] = self.ent_dbname.get().strip()

        # Eksekusi Update
        try:
            affected = self.db.bulk_update_db_connections(self.conn_ids, updates)
            messagebox.showinfo(
                "Bulk Edit Sukses",
                f"Berhasil memperbarui {affected} koneksi database."
            )
            if self.on_save_callback:
                self.on_save_callback()
            self.destroy()
        except Exception as e:
            self.lbl_error.configure(text=f"Gagal memperbarui: {str(e)}")
