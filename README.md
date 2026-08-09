# SeedSigner Touchscreen Build

A personal fork of [SeedSigner](https://github.com/SeedSigner/seedsigner) rebuilt
around a capacitive touchscreen: direct tap input everywhere, a T9-style seed
word keyboard, and BIP-85 child seed workflows.

> **⚠️ Unofficial and unaudited.** This is a personal build, not affiliated with
> or endorsed by the SeedSigner project. It signs real transactions with real
> keys; unless you have reviewed the code yourself, use an official SeedSigner
> release for actual custody.

## Hardware

- Raspberry Pi Zero
- Waveshare 2.8" DPI capacitive touchscreen (480×640, Goodix GT911 touch)
- Pi Camera module

Display + touch bring-up for this panel is documented in
[`DISPLAY_SETUP.md`](DISPLAY_SETUP.md), with boot config, dtoverlays and setup
script in-tree (`config_dpi28.txt`, `overlays_dpi28/`, `setup_dpi28.sh`).
See also [SeedSigner/seedsigner-os#104](https://github.com/SeedSigner/seedsigner-os/issues/104).

## What's different from upstream

- **Full touch UI.** Direct tap on keys, buttons and lists; a persistent touch
  bar for context actions; touch events are queued during rendering so taps are
  never dropped.
- **T9 seed word entry**, three selectable modes (Settings → Advanced → Seed
  keyboard). The default, **T9 predict**, is one tap per key: candidates
  matching the tapped key sequence rank in a side list, keys with no valid
  BIP-39 continuation go dark, and most words take 3-4 taps plus a confirm.
  Classic multi-tap T9 (constrained to valid continuations) and the upstream
  d-pad keyboard remain available.
- **BIP-85 child seeds.** Derived children auto-import with their real child
  index and full lineage in the seed label (`(c1)(c21)` for a
  child-of-a-child), so a mislabeled child can't point at the wrong recovery
  path.
- **Touch-operable camera flows.** Photo seed generation: tap the live preview
  (or the touch bar shutter) to snap, then tap the left or right half of the
  photo to reshoot or accept. QR scanning keeps tap-anywhere-to-cancel.
- **SeedQR transcription QoL.** The zoomed transcription view pans toward
  wherever you tap, and the screensaver stays off while you copy.
- Every BIP-39 word is provably reachable on the predictive keyboard: the test
  suite walks all 2048 words for dead ends (`tests/test_t9_predict.py`).

## Releases

Flash-ready SD card images are published under
[Releases](https://github.com/FreeOnlineUser/seedsigner/releases), with a
sha256 for each image in the release notes. Verify the hash after downloading.

## Building

Build as a normal [seedsigner-os](https://github.com/SeedSigner/seedsigner-os)
buildroot image with this repo as the app source and the display files above in
the boot partition. Nothing here requires a custom OS fork.

Note: at boot the app reads `src/seedsigner/version.json`, which the current
seedsigner-os build process generates. If your build pipeline doesn't, create
it with `PYTHONPATH=src python3 tools/write_versionfile.py` before packing the
image, or the splash screen will crash.

## Upstream

A direct fork of [SeedSigner/seedsigner](https://github.com/SeedSigner/seedsigner),
kept in sync with its `dev` branch (last merged August 2026). Early BIP-85
groundwork came from jdlcdl's fork; BIP-85 has since landed upstream.

License: MIT, same as upstream.
