# SeedSigner — Touchscreen Build

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
  BIP-39 continuation go dark, and most words take 3–4 taps plus a confirm.
  Classic multi-tap T9 (constrained to valid continuations) and the upstream
  d-pad keyboard remain available.
- **BIP-85 child seeds.** Derived children auto-import with their real child
  index and full lineage in the seed label — `(c1)(c21)` for a
  child-of-a-child — so a mislabeled child can't point at the wrong recovery
  path.
- **SeedQR transcription QoL.** The zoomed transcription view pans toward
  wherever you tap, and the screensaver stays off while you copy.
- Every BIP-39 word is provably reachable on the predictive keyboard — the test
  suite walks all 2048 words for dead ends (`tests/test_t9_predict.py`).

## Building

Build as a normal [seedsigner-os](https://github.com/SeedSigner/seedsigner-os)
buildroot image with this repo as the app source and the display files above in
the boot partition. Nothing here requires a custom OS fork.

## Upstream

Based on [jdlcdl/seedsigner](https://github.com/jdlcdl/seedsigner) (early
BIP-85 groundwork). BIP-85 has since landed upstream; rebasing this work onto
current `SeedSigner/seedsigner` dev is planned.

License: MIT, same as upstream.
