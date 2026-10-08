from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import customtkinter as ctk
from PIL import Image, ImageColor, ImageTk

from theme import resource_path

_ICON_CACHE: Dict[Tuple[str, Tuple[int, int], str], ctk.CTkImage] = {}
_TK_IMAGE_CACHE: Dict[Tuple[str, Tuple[int, int], str], ImageTk.PhotoImage] = {}
_BASE_IMG_CACHE: Dict[str, Image.Image] = {}


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    try:
        return ImageColor.getrgb(hex_str)[:3]
    except Exception:
        return (255, 255, 255)


def _color_to_rgb(color_val: Any, is_dark: bool = True) -> Tuple[int, int, int]:
    if isinstance(color_val, (tuple, list)):
        hex_str = color_val[1] if is_dark else color_val[0]
    else:
        hex_str = str(color_val)
    return _hex_to_rgb(hex_str)


def _get_base_image(name: str) -> Image.Image:
    if name not in _BASE_IMG_CACHE:
        p1 = resource_path(f"assets/icons/{name}.png")
        p2 = resource_path(f"src/assets/icons/{name}.png")
        icon_path = p1 if p1.exists() else (p2 if p2.exists() else None)

        if not icon_path or not icon_path.exists():
            if name == "trash-2":
                return _get_base_image("trash")
            if name == "edit":
                return _get_base_image("pencil")
            _BASE_IMG_CACHE[name] = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        else:
            _BASE_IMG_CACHE[name] = Image.open(icon_path).convert("RGBA")
    return _BASE_IMG_CACHE[name]


def get_icon(name: str, size: Tuple[int, int] = (16, 16), color: Any = "#FFFFFF") -> ctk.CTkImage:
    """Mengambil CTkImage icon Lucide dengan warna dan ukuran yang diinginkan (mendukung dynamic light/dark tuple)."""
    cache_key = (name, size, str(color))
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    base = _get_base_image(name)
    target_px_size = (size[0] * 2, size[1] * 2)  # 2x for Retina crispness
    r, g, b, alpha = base.split()

    # Light Mode Image
    r_l, g_l, b_l = _color_to_rgb(color, is_dark=False)
    light_img = Image.new("RGBA", base.size, (r_l, g_l, b_l, 255))
    light_img.putalpha(alpha)
    resized_light = light_img.resize(target_px_size, Image.Resampling.LANCZOS)

    # Dark Mode Image
    r_d, g_d, b_d = _color_to_rgb(color, is_dark=True)
    dark_img = Image.new("RGBA", base.size, (r_d, g_d, b_d, 255))
    dark_img.putalpha(alpha)
    resized_dark = dark_img.resize(target_px_size, Image.Resampling.LANCZOS)

    ctk_img = ctk.CTkImage(light_image=resized_light, dark_image=resized_dark, size=size)
    _ICON_CACHE[cache_key] = ctk_img
    return ctk_img


def get_tk_image(name: str, size: Tuple[int, int] = (16, 16), color: Any = "#FFFFFF", mode: Optional[str] = None) -> ImageTk.PhotoImage:
    """Mengambil ImageTk.PhotoImage icon Lucide untuk digunakan pada native tk.Menu / Tkinter widget."""
    current_mode = (mode or ctk.get_appearance_mode()).lower()
    is_dark = (current_mode != "light")
    cache_key = (name, size, f"{color}_{current_mode}")
    if cache_key in _TK_IMAGE_CACHE:
        return _TK_IMAGE_CACHE[cache_key]

    base = _get_base_image(name)
    r_target, g_target, b_target = _color_to_rgb(color, is_dark=is_dark)
    r, g, b, alpha = base.split()
    color_img = Image.new("RGBA", base.size, (r_target, g_target, b_target, 255))
    color_img.putalpha(alpha)

    resized = color_img.resize(size, Image.Resampling.LANCZOS)
    tk_img = ImageTk.PhotoImage(resized)
    _TK_IMAGE_CACHE[cache_key] = tk_img
    return tk_img
