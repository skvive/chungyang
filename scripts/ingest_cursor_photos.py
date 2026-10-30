"""Convert Cursor GenerateImage assets to static WebP."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(r"C:\Users\user\.cursor\projects\e-currsor-C-blog\assets")
OUT = ROOT / "static" / "img"

MAP = {
    "chungyang-hero.jpg": "hero.webp",
    "chungyang-domestic.jpg": "domestic.webp",
    "chungyang-jeju.jpg": "jeju.webp",
    "chungyang-benchmark.jpg": "benchmark.webp",
    "chungyang-outing.jpg": "outing.webp",
    "chungyang-workshop.jpg": "workshop.webp",
    "chungyang-family.jpg": "family.webp",
    "chungyang-about.jpg": "about-team.webp",
    "chungyang-contact.jpg": "contact-hero.webp",
}


def to_webp(src: Path, dest: Path, max_side: int = 2400, quality: int = 86) -> None:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=quality, method=6)


def main() -> None:
    for src_name, dest_name in MAP.items():
        src = ASSETS / src_name
        if not src.exists():
            raise SystemExit(f"missing asset: {src}")
        to_webp(src, OUT / dest_name)
        print(dest_name, (OUT / dest_name).stat().st_size)
    # Feature banner shares workshop scene
    ws = OUT / "workshop.webp"
    to_webp(ASSETS / "chungyang-workshop.jpg", OUT / "group.webp")
    print("group.webp", (OUT / "group.webp").stat().st_size)


if __name__ == "__main__":
    main()
