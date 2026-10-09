import sys
from typing import Any, Optional
import customtkinter as ctk


class HorizontalScrollableTabBar(ctk.CTkScrollableFrame):
    """Custom horizontal scrollable tab bar dengan dukungan penuh trackpad macOS (swipe 2 jari kiri/kanan & atas/bawah) serta mouse wheel."""

    def __init__(self, master: Any, **kwargs):
        kwargs["orientation"] = "horizontal"
        super().__init__(master, **kwargs)

        self._delta_accumulator = 0.0

        # Sembunyikan scrollbar visual agar tampilan tab strip bersih dan minimalis seperti browser
        if hasattr(self, "_scrollbar"):
            self._scrollbar.grid_remove()

        # Atur scroll increment untuk kelancaran scrolling di macOS/Windows/Linux
        self._set_scroll_increments()

        # Bind all global scroll events (termasuk <Shift-MouseWheel> untuk horizontal swipe trackpad di macOS)
        try:
            self.bind_all("<Shift-MouseWheel>", self._mouse_wheel_all, add=True)
            self.bind_all("<Option-MouseWheel>", self._mouse_wheel_all, add=True)
            self.bind_all("<Command-MouseWheel>", self._mouse_wheel_all, add=True)
            if "linux" in sys.platform:
                self.bind_all("<Shift-Button-4>", self._mouse_wheel_all, add=True)
                self.bind_all("<Shift-Button-5>", self._mouse_wheel_all, add=True)
                self.bind_all("<Button-6>", self._mouse_wheel_all, add=True)
                self.bind_all("<Button-7>", self._mouse_wheel_all, add=True)
        except Exception:
            pass

        # Bind langsung ke canvas dan frame container
        self._bind_scroll_recursive(self._parent_canvas)
        self._bind_scroll_recursive(self)

    def _is_pointer_over_tab_bar(self, event) -> bool:
        """Cek apakah kursor berada di atas area tab bar atau widget turunannya."""
        try:
            if hasattr(event, "widget") and self._check_if_valid_scroll(event.widget):
                return True
        except Exception:
            pass
        try:
            if hasattr(event, "x_root") and hasattr(event, "y_root"):
                x, y = event.x_root, event.y_root
                canvas = self._parent_canvas
                rx = canvas.winfo_rootx()
                ry = canvas.winfo_rooty()
                rw = canvas.winfo_width()
                rh = canvas.winfo_height()
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    return True
        except Exception:
            pass
        return False

    def _on_mouse_scroll(self, event):
        """Scroll horizontal ketika menerima event swipe trackpad macOS (horizontal/vertikal) atau roda mouse."""
        canvas = self._parent_canvas
        raw_delta = getattr(event, "delta", 0)

        if not raw_delta:
            # Linux X11 button numbers
            num = getattr(event, "num", 0)
            step = -6 if num in (4, 6) else (6 if num in (5, 7) else 0)
            if step != 0:
                try:
                    canvas.xview("scroll", int(step), "units")
                except Exception:
                    pass
            return

        if sys.platform == "darwin":
            # Pada macOS trackpad, raw_delta berupa float/int (misal +/- 0.5 hingga 5.0)
            # Kalikan dengan multiplier (6.0) agar gerakan trackpad responsif di kedua arah
            self._delta_accumulator += -float(raw_delta) * 6.0
            step = int(self._delta_accumulator)
            if step != 0:
                self._delta_accumulator -= step
                try:
                    canvas.xview("scroll", int(step), "units")
                    # Reset akumulator saat mencapai batas ujung untuk mencegah lag saat berbalik arah
                    xv = canvas.xview()
                    if (step < 0 and xv[0] <= 0.0) or (step > 0 and xv[1] >= 1.0):
                        self._delta_accumulator = 0.0
                except Exception:
                    pass
        elif sys.platform.startswith("win"):
            # Pada Windows mouse wheel, raw_delta umumnya +/- 120
            self._delta_accumulator += -float(raw_delta) / 10.0
            step = int(self._delta_accumulator)
            if step == 0 and raw_delta != 0:
                step = -2 if raw_delta > 0 else 2
            if step != 0:
                self._delta_accumulator = 0.0
                try:
                    canvas.xview("scroll", int(step), "units")
                except Exception:
                    pass
        else:
            delta = -4 if raw_delta > 0 else 4
            try:
                canvas.xview("scroll", int(delta), "units")
            except Exception:
                pass

    def _mouse_wheel_all(self, event):
        """Override bawaan CustomTkinter agar gesture trackpad 2 jari kiri/kanan & atas/bawah menggeser tab horizontal."""
        if self._is_pointer_over_tab_bar(event):
            self._on_mouse_scroll(event)

    def _bind_scroll_recursive(self, widget: Any):
        """Bind event mouse & trackpad ke widget agar interaksi hover selalu merespons scroll."""
        try:
            widget.bind("<MouseWheel>", self._on_mouse_scroll, add="+")
            widget.bind("<Shift-MouseWheel>", self._on_mouse_scroll, add="+")
            widget.bind("<Option-MouseWheel>", self._on_mouse_scroll, add="+")
            widget.bind("<Command-MouseWheel>", self._on_mouse_scroll, add="+")
            widget.bind("<Button-4>", self._on_mouse_scroll, add="+")
            widget.bind("<Button-5>", self._on_mouse_scroll, add="+")
            widget.bind("<Button-6>", self._on_mouse_scroll, add="+")
            widget.bind("<Button-7>", self._on_mouse_scroll, add="+")
        except Exception:
            pass

    def bind_child_scroll(self, widget: Any):
        """Helper untuk me-register widget anak (tab card, button, label, dsb) ke scroll handler."""
        self._bind_scroll_recursive(widget)

    def scroll_left(self, step: int = 25):
        """Scroll ke kiri secara langsung saat tombol panah navigasi diklik."""
        try:
            self._parent_canvas.xview("scroll", -int(step), "units")
            self._delta_accumulator = 0.0
        except Exception:
            pass

    def scroll_right(self, step: int = 25):
        """Scroll ke kanan secara langsung saat tombol panah navigasi diklik."""
        try:
            self._parent_canvas.xview("scroll", int(step), "units")
            self._delta_accumulator = 0.0
        except Exception:
            pass

    def scroll_to_child(self, widget: Any):
        """Otomatis geser tampilan jika tab aktif berada di luar viewport."""
        try:
            self.update_idletasks()
            canvas = self._parent_canvas
            wx = widget.winfo_x()
            ww = widget.winfo_width()
            bbox = canvas.bbox("all")
            if not bbox:
                return
            total_w = bbox[2]
            cw = canvas.winfo_width()
            if total_w <= cw or total_w <= 0:
                return

            cx_left = canvas.xview()[0] * total_w
            cx_right = canvas.xview()[1] * total_w

            if wx < cx_left:
                target_fraction = max(0.0, float(wx) / float(total_w))
                canvas.xview_moveto(target_fraction)
            elif (wx + ww) > cx_right:
                target_fraction = min(1.0, float(wx + ww - cw + 20) / float(total_w))
                canvas.xview_moveto(target_fraction)
        except Exception:
            pass
