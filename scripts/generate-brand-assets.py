"""
Derives every brand asset from `assets/logo.png`.

The source is a circular badge on a solid black square with no alpha channel,
which cannot be used directly anywhere: dropped onto a light screen it shows
black corners, and used as an adaptive icon foreground the launcher's circular
mask crops the tricolour ring and the wordmark.

Each output below solves one of those problems, and the script exists so the set
can be regenerated when the logo changes rather than being a folder of files
nobody can reproduce.

Run:  python scripts/generate-brand-assets.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parents[1] / "assets"
SOURCE = ASSETS / "logo.png"

#: The app's canvas colour. The icon must be opaque — iOS rejects an alpha
#: channel in an app icon — so the badge is composited onto this rather than
#: left transparent.
CANVAS = (247, 248, 250)

#: Android gives an adaptive icon's foreground a 108dp canvas, of which only the
#: middle 66dp is guaranteed visible — 0.611 of the width. Launchers choose their
#: own mask shape within that, so the badge is drawn a little inside the
#: guarantee rather than exactly on it; at 0.66 the outer navy ring was close
#: enough to the boundary for a circular mask to shave it.
ADAPTIVE_SAFE_FRACTION = 0.60


def load_badge() -> Image.Image:
    """
    Returns the badge with everything outside its circle made transparent.

    The alpha comes from a drawn circle rather than from keying out black:
    the badge's own shield is nearly black, so colour-keying would punch holes
    straight through the middle of it.
    """
    source = Image.open(SOURCE).convert("RGB")
    width, height = source.size

    grey = np.asarray(source).astype(int).sum(axis=2)
    ys, xs = np.nonzero(grey > 40)
    centre_x = (xs.min() + xs.max()) / 2
    centre_y = (ys.min() + ys.max()) / 2
    radius = min(xs.max() - xs.min(), ys.max() - ys.min()) / 2

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse(
        [centre_x - radius, centre_y - radius, centre_x + radius, centre_y + radius],
        fill=255,
    )
    # A one-pixel blur keeps the circumference from stair-stepping once the
    # badge is scaled down to icon sizes.
    mask = mask.filter(ImageFilter.GaussianBlur(1.0))

    badge = source.convert("RGBA")
    badge.putalpha(mask)
    return badge.crop(
        (
            int(centre_x - radius),
            int(centre_y - radius),
            int(centre_x + radius),
            int(centre_y + radius),
        )
    )


def square(badge: Image.Image, size: int, *, scale: float, background) -> Image.Image:
    """Centres the badge on a square canvas at `scale` of its width."""
    canvas = Image.new("RGBA", (size, size), background)
    target = max(1, int(size * scale))
    resized = badge.resize((target, target), Image.LANCZOS)
    offset = ((size - target) // 2, (size - target) // 2)
    canvas.alpha_composite(resized, offset)
    return canvas


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Source logo not found: {SOURCE}")

    badge = load_badge()
    written = []

    def write(name: str, image: Image.Image, *, opaque: bool = False) -> None:
        path = ASSETS / name
        if opaque:
            flat = Image.new("RGB", image.size, CANVAS)
            flat.paste(image, mask=image.split()[-1])
            flat.save(path)
        else:
            image.save(path)
        written.append((name, image.size))

    # In-app brand mark: transparent everywhere outside the badge, so it sits on
    # any surface the theme provides.
    write("brand-mark.png", badge.resize((512, 512), Image.LANCZOS))

    # App icon. Opaque, and only lightly inset — this one is not masked to a
    # circle on iOS, so the badge can fill most of the tile.
    write("icon.png", square(badge, 1024, scale=0.92, background=CANVAS + (255,)), opaque=True)

    # Adaptive icon. The foreground keeps its transparency and stays inside the
    # safe zone; the background is the flat canvas colour behind it.
    write(
        "android-icon-foreground.png",
        square(badge, 1024, scale=ADAPTIVE_SAFE_FRACTION, background=(0, 0, 0, 0)),
    )
    write("android-icon-background.png", Image.new("RGBA", (1024, 1024), CANVAS + (255,)))

    # Splash. Transparent, drawn over the splash background colour.
    write("splash-icon.png", badge.resize((512, 512), Image.LANCZOS))

    # Web favicon.
    write("favicon.png", badge.resize((64, 64), Image.LANCZOS))

    for name, size in written:
        print("%-32s %s" % (name, size))


if __name__ == "__main__":
    main()
