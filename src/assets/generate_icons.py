import os
import subprocess
import urllib.request
from pathlib import Path

ICONS = [
    "rocket",
    "database",
    "key",
    "download",
    "upload",
    "refresh-cw",
    "plus",
    "zap",
    "search",
    "activity",
    "pencil",
    "trash-2",
    "trash",
    "folder-input",
    "folder-plus",
    "folder",
    "terminal",
    "table",
    "copy",
    "settings",
    "check",
    "x",
    "server",
    "play",
    "shield",
    "external-link",
    "sparkles",
    "file-text",
    "file-code",
    "laptop",
    "list-checks",
    "bell",
]

out_dir = Path(__file__).resolve().parent / "icons"
out_dir.mkdir(parents=True, exist_ok=True)

swift_render_code = """
import AppKit
import Foundation

let args = CommandLine.arguments
guard args.count >= 3 else { exit(1) }
let svgPath = args[1]
let outPngPath = args[2]

guard let svgData = try? Data(contentsOf: URL(fileURLWithPath: svgPath)),
      let svgImage = NSImage(data: svgData) else {
    exit(2)
}

let size: CGFloat = 64
let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: Int(size),
    pixelsHigh: Int(size),
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
)!

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
svgImage.draw(in: NSRect(x: 0, y: 0, width: size, height: size))
NSGraphicsContext.restoreGraphicsState()

if let pngData = rep.representation(using: .png, properties: [:]) {
    try? pngData.write(to: URL(fileURLWithPath: outPngPath))
}
"""

temp_swift = out_dir / "_render.swift"
temp_swift.write_text(swift_render_code)

print(f"Generating {len(ICONS)} Lucide icons into {out_dir}...")

for icon_name in ICONS:
    png_path = out_dir / f"{icon_name}.png"
    temp_svg = out_dir / f"_{icon_name}.svg"
    
    url = f"https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{icon_name}.svg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        svg_content = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
        # Ensure stroke is clean pure white for mask tinting
        svg_white = svg_content.replace('stroke="currentColor"', 'stroke="#FFFFFF"')
        temp_svg.write_text(svg_white)

        # Run swift renderer
        subprocess.run(["swift", str(temp_swift), str(temp_svg), str(png_path)], check=True)
        if temp_svg.exists():
            temp_svg.unlink()
        print(f"  ✓ {icon_name}.png generated")
    except Exception as e:
        print(f"  ✗ Failed to generate {icon_name}: {e}")

if temp_swift.exists():
    temp_swift.unlink()

print("All icons successfully created!")
