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


def get_file_type_info(filename: str, is_dir: bool = False) -> Tuple[str, Any]:
    """
    Menentukan icon Lucide dan warna representatif (light/dark tuple) berdasarkan nama file dan ekstensinya.
    Mendukung .js, .css, .html, .php, .py, .sql, .sh, .json, .cnf, .env, images, archives, dll.
    """
    if is_dir:
        return "folder", ("#2563EB", "#3B82F6")

    fn = Path(filename).name.lower()

    # Exact Filename Rules
    if fn.startswith("dockerfile") or fn.startswith("docker-compose"):
        return "server", ("#0284C7", "#38BDF8")
    if fn in ("package.json", "composer.json", "package-lock.json", "composer.lock"):
        return "settings", ("#E11D48", "#FB7185")
    if fn.startswith(".env"):
        return "key", ("#D97706", "#FBBF24")
    if fn.startswith(".git"):
        return "git-branch", ("#EA580C", "#F97316")
    if fn.startswith("readme") or fn.startswith("license"):
        return "file-text", ("#2563EB", "#60A5FA")
    if fn in ("makefile", "cmakelists.txt", "vagrantfile"):
        return "file-code", ("#D97706", "#F59E0B")

    # Extension Rules
    ext = Path(filename).suffix.lower()

    # Multi-extension check (misal .blade.php, .tar.gz)
    if fn.endswith(".blade.php"):
        return "file-code", ("#EA580C", "#FB923C")
    if fn.endswith(".tar.gz") or fn.endswith(".tar.bz2"):
        return "file-archive", ("#D97706", "#F59E0B")

    mapping = {
        (".js", ".mjs", ".cjs"): ("file-code", ("#CA8A04", "#FACC15")),             # JavaScript Yellow
        (".ts",): ("file-code", ("#2563EB", "#60A5FA")),                             # TypeScript Blue
        (".tsx", ".jsx"): ("file-code", ("#0891B2", "#22D3EE")),                     # React Cyan
        (".css", ".scss", ".sass", ".less"): ("file-code", ("#0284C7", "#38BDF8")), # CSS Sky Blue
        (".html", ".htm", ".xhtml", ".vue", ".svelte"): ("file-code", ("#EA580C", "#FB923C")), # HTML Orange
        (".php", ".phtml", ".php3", ".php4", ".php5"): ("file-code", ("#7C3AED", "#A855F7")),  # PHP Purple
        (".py", ".pyw", ".ipynb"): ("file-code", ("#0D9488", "#2DD4BF")),            # Python Teal
        (".json", ".json5", ".jsonc"): ("file-code", ("#D97706", "#FBBF24")),        # JSON Amber
        (".xml", ".svg"): ("file-code", ("#EA580C", "#F97316")),                     # XML/SVG Orange
        (".sql", ".db", ".sqlite", ".sqlite3", ".mdb"): ("database", ("#059669", "#34D399")),   # Database Green
        (".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1"): ("terminal", ("#16A34A", "#4ADE80")), # Shell Green
        (".cnf", ".conf", ".ini", ".cfg", ".config"): ("settings", ("#64748B", "#94A3B8")),     # Server Config Slate
        (".yaml", ".yml", ".toml"): ("settings", ("#9333EA", "#C084FC")),            # YAML/TOML Purple
        (".key", ".pem", ".crt", ".cer", ".pub", ".lock"): ("key", ("#D97706", "#FBBF24")),     # Key/Cert Gold
        (".md", ".markdown"): ("file-text", ("#2563EB", "#60A5FA")),                 # Markdown Blue
        (".txt", ".log", ".rtf"): ("file-text", ("#64748B", "#94A3B8")),             # Text/Log Slate
        (".pdf",): ("file-text", ("#DC2626", "#F87171")),                            # PDF Red
        (".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".bz2"): ("file-archive", ("#D97706", "#F59E0B")), # Archive Amber
        (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff"): ("file-image", ("#E11D48", "#FB7185")), # Image Rose
        (".mp4", ".mkv", ".avi", ".mov", ".mp3", ".wav", ".flac", ".ogg"): ("play", ("#7C3AED", "#A855F7")),        # Media Purple
        (".exe", ".msi", ".dll", ".so", ".dylib", ".bin", ".jar"): ("zap", ("#E11D48", "#F43F5E")),                # Binary Rose
    }

    for exts, val in mapping.items():
        if ext in exts:
            return val

    return "file", ("#64748B", "#94A3B8")


def get_file_type_tk_image(filename: str, is_dir: bool = False, size: Tuple[int, int] = (14, 14), mode: Optional[str] = None) -> ImageTk.PhotoImage:
    """Mengambil ImageTk.PhotoImage untuk file/folder dengan icon dan warna spesifik sesuai jenisnya."""
    icon_name, color = get_file_type_info(filename, is_dir)
    return get_tk_image(icon_name, size=size, color=color, mode=mode)


def get_file_type_icon(filename: str, is_dir: bool = False, size: Tuple[int, int] = (14, 14)) -> ctk.CTkImage:
    """Mengambil CTkImage untuk file/folder dengan icon dan warna spesifik sesuai jenisnya."""
    icon_name, color = get_file_type_info(filename, is_dir)
    return get_icon(icon_name, size=size, color=color)
