#!/usr/bin/env python3
"""
Rasterize Feather icons (https://feathericons.com, MIT) into tintable alpha
masks that the app can paste at runtime.

WHY PRE-RASTERIZE: the signer runs on an ARMv6 Pi Zero with PIL only. There is
no SVG rasterizer on the device (cairo/librsvg are far too heavy for that
target), so SVGs are converted here, on a workstation, and the repo ships
deterministic PNG assets. Runtime cost on the Pi is then a paste through an
alpha mask - the same mechanism used for anti-aliased button corners.

WHY ALPHA MASKS (not coloured PNGs): the interface derives icon state from
colour (accent / body / disabled). One mask per icon tinted at runtime is the
Feather guidance ("use currentColor, never separate assets") expressed in PIL.

Assets are written at ICON_RASTER_SIZE and downscaled with LANCZOS at runtime,
so one file serves every on-screen size.

Usage:
    DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python tools/build_feather_icons.py
    (needs `brew install cairo` + `pip install cairosvg`; build-time only,
     never installed on the device)
"""
import hashlib
import io
import json
import pathlib
import sys
import urllib.request

import cairosvg
from PIL import Image

# Pinned release. Bump deliberately, never float: these are third-party assets
# that end up inside a signer image, so the version must be auditable.
FEATHER_VERSION = "4.29.2"
BASE_URL = f"https://unpkg.com/feather-icons@{FEATHER_VERSION}/dist/icons"

# Rendered at 4x the largest on-screen icon, then LANCZOS-downscaled at runtime.
ICON_RASTER_SIZE = 128

# Feather's default stroke (2 at 24px) reads thin once scaled down on a
# 286 DPI panel; 2.25 keeps it matched to the semibold UI text weight.
STROKE_WIDTH = 2.25

OUT_DIR = pathlib.Path(__file__).parent.parent / "src/seedsigner/resources/icons/feather"

# SeedSigner icon constant -> Feather icon name.
#
# Deliberately NOT mapped (no faithful Feather equivalent; these keep the
# SeedSigner glyph, which also preserves the brand where it is most
# recognisable): BITCOIN, BITCOIN_ALT, FINGERPRINT, QRCODE, MICROSD, SPACE,
# SEEDSIGNER logo marks.
ICON_MAP = {
    "SCAN": "maximize",
    "SEEDS": "key",
    "SETTINGS": "settings",
    "TOOLS": "tool",
    "BACK": "arrow-left",
    "CHECK": "check",
    "CHECKBOX": "square",
    "CHECKBOX_SELECTED": "check-square",
    "CHEVRON_DOWN": "chevron-down",
    "CHEVRON_LEFT": "chevron-left",
    "CHEVRON_RIGHT": "chevron-right",
    "CHEVRON_UP": "chevron-up",
    "PLUS": "plus",
    "POWER": "power",
    "RESTART": "refresh-cw",
    "INFO": "info",
    "SUCCESS": "check-circle",
    "WARNING": "alert-triangle",
    "ERROR": "x-circle",
    "CHANGE": "shuffle",
    "DERIVATION": "git-branch",
    "PASSPHRASE": "lock",
    "SIGN": "edit-3",
    "DELETE": "delete",
}


def fetch(name: str) -> bytes:
    url = f"{BASE_URL}/{name}.svg"
    with urllib.request.urlopen(url, timeout=30) as r:
        if r.status != 200:
            raise SystemExit(f"{url} -> HTTP {r.status}")
        return r.read()


def rasterize(svg: bytes) -> Image.Image:
    # Feather strokes use currentColor; force white so the result is a clean
    # luminance ramp we can use directly as an alpha mask.
    svg_text = svg.decode()
    svg_text = svg_text.replace('stroke-width="2"', f'stroke-width="{STROKE_WIDTH}"')
    svg_text = svg_text.replace('stroke="currentColor"', 'stroke="#ffffff"')
    png = cairosvg.svg2png(
        bytestring=svg_text.encode(),
        output_width=ICON_RASTER_SIZE,
        output_height=ICON_RASTER_SIZE,
        background_color="transparent",
    )
    rgba = Image.open(io.BytesIO(png)).convert("RGBA")
    # The alpha channel IS the mask.
    return rgba.getchannel("A")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "https://feathericons.com",
        "license": "MIT",
        "version": FEATHER_VERSION,
        "raster_size": ICON_RASTER_SIZE,
        "stroke_width": STROKE_WIDTH,
        "icons": {},
    }
    for const_name, feather_name in sorted(ICON_MAP.items()):
        svg = fetch(feather_name)
        mask = rasterize(svg)
        out = OUT_DIR / f"{const_name}.png"
        mask.save(out, optimize=True)
        manifest["icons"][const_name] = {
            "feather": feather_name,
            "svg_sha256": hashlib.sha256(svg).hexdigest(),
            "png_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        }
        print(f"  {const_name:20s} <- feather/{feather_name}")

    (OUT_DIR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT_DIR / "LICENSE").write_text(
        "Feather icons\n"
        "https://github.com/feathericons/feather\n"
        f"Version {FEATHER_VERSION}\n"
        "Licensed under the MIT License. Copyright (c) 2013-2023 Cole Bemis.\n"
    )
    print(f"\n{len(ICON_MAP)} icons -> {OUT_DIR}")
    print("Provenance (source URL, version, per-file sha256) in MANIFEST.json")


if __name__ == "__main__":
    main()
