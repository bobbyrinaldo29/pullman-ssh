from pathlib import Path
from typing import Dict, Tuple
import customtkinter as ctk
from PIL import Image, ImageColor

from theme import resource_path

_ICON_CACHE: Dict[Tuple[str, Tuple[int, int], str], ctk.CTkImage] = {}
_BASE_IMG_CACHE: Dict[str, Image.Image] = {}


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    try:
        return ImageColor.getrgb(hex_str)[:3]
    except Exception:
        return (255, 255, 255)


def get_icon(name: str, size: Tuple[int, int] = (16, 16), color: str = "#FFFFFF") -> ctk.CTkImage:
    """Mengambil CTkImage icon Lucide dengan warna dan ukuran yang diinginkan."""
    cache_key = (name, size, color)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    if name not in _BASE_IMG_CACHE:
        # Cari file di assets/icons/
        p1 = resource_path(f"assets/icons/{name}.png")
        p2 = resource_path(f"src/assets/icons/{name}.png")
        icon_path = p1 if p1.exists() else (p2 if p2.exists() else None)

        if not icon_path or not icon_path.exists():
            # Fallback jika nama berbeda (misal trash-2 -> trash)
            if name == "trash-2":
                return get_icon("trash", size, color)
            if name == "edit":
                return get_icon("pencil", size, color)
            # Create transparent dummy
            _BASE_IMG_CACHE[name] = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        else:
            _BASE_IMG_CACHE[name] = Image.open(icon_path).convert("RGBA")

    base = _BASE_IMG_CACHE[name]

    # Colorize
    r_target, g_target, b_target = _hex_to_rgb(color)
    
    # Split alpha
    r, g, b, alpha = base.split()
    # Create solid color image with base alpha
    color_img = Image.new("RGBA", base.size, (r_target, g_target, b_target, 255))
    color_img.putalpha(alpha)

    # Resize cleanly
    target_px_size = (size[0] * 2, size[1] * 2)  # 2x for Retina crispness
    resized = color_img.resize(target_px_size, Image.Resampling.LANCZOS)

    ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=size)
    _ICON_CACHE[cache_key] = ctk_img
    return ctk_img
