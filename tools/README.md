# Build tooling

The scripts that produced this mirror, plus the capture metadata they read.
Kept here so the site can be rebuilt or amended without the original scrape
working tree — everything in this directory is small enough to version.

## What is *not* here

The raw page captures. Each mirrored route was captured as a JSON file holding
the fully-rendered `document.documentElement.outerHTML`, and the whole set is
about 144 MB (`html/`), with another 1.1 GB of downloaded assets. Those live
only in the scrape working tree.

That splits the scripts in two:

- **Run anywhere** — `static_faq.py`, `fix_lang_switcher.py`,
  `relink_gated.py`. These rewrite pages that are already built, so the built
  site plus `data/` is all they need.
- **Need the captures** — `build_mobile.py`, `build_id_gated.py`. These render
  pages from `html/`. Run them from the scrape tree, or point
  `CIRCLES_CAPTURES` at a copy of the directory that contains `html/`.

## Layout

`paths.py` works out where things are, so the same scripts run from either
place:

| | scrape tree | this repo |
| --- | --- | --- |
| scripts | `circles-scrape/scripts/` | `<repo>/tools/` |
| built site | `circles-scrape/site/` | `<repo>/` |
| metadata | `circles-scrape/*.json` | `<repo>/tools/data/` |
| captures | `circles-scrape/html/` | not present |

## The scripts

- **`build_mobile.py`** — the original pipeline. Builds `<rel>/m/index.html`
  from the mobile captures, splices in the real mobile nav, and adds the
  desktop→mobile redirect. Also builds the four-file shape the password-gated
  routes use. Exports most of the shared helpers the other scripts import.
- **`build_id_gated.py`** — builds the Indonesian variants of the three gated
  routes and registers them in the manifest.
- **`gate-template.py`** — the password gate shell, in English and Indonesian.
  The gate is client-side only and this repo is public, so it keeps the pages
  out of the way rather than actually protecting them.
- **`relink_gated.py`** — rewrites any remaining absolute `circlesubi.id` links
  to relative paths. Idempotent; run it after adding routes to the manifest.
- **`static_faq.py`** — replaces the Wix FAQ widget with a static accordion fed
  by `data/faq-all-merged.json`. See below.
- **`fix_lang_switcher.py`** — makes the EN/ID flag buttons navigate. Wix wires
  them up in JavaScript, which the mirror strips.

## Order matters

`build_mobile.py` and `build_id_gated.py` regenerate pages from the captures,
which discards everything the later passes added. After running either one, run
the rest in this order:

```sh
python3 relink_gated.py       # absolute -> relative links
python3 static_faq.py         # FAQ accordion
python3 fix_lang_switcher.py  # EN/ID flag navigation
```

Each is idempotent, so re-running the whole chain is safe. `static_faq.py` and
`fix_lang_switcher.py` both take `--force` semantics differently:
`fix_lang_switcher.py --force` re-derives link destinations on pages it already
wired; `static_faq.py` skips any page that already carries the static
accordion, so revert the page from git if you need to rebuild it.

## `data/faq-derived.json`

`static_faq.py` needs three things that only exist inside the captured Wix
widget: the Indonesian category labels, the single category that was captured
with Indonesian text, and each page's own category list. Replacing the widget
destroys that copy, so the first run caches them here. **Do not delete it** —
without it the script only works against pages that still hold the original
widget.

## Known gaps

- **The Indonesian FAQ is 1 of 21 categories.** The Wix widget loaded each
  category from a backend on click, so a capture only ever freezes the tab that
  was open. All 21 English categories were captured separately (128 Q&A pairs
  in `data/faq-all-merged.json`); only the first was ever captured in
  Indonesian. The other 20 tabs show the English text with a visible note
  saying so, which needs the live site to fix properly.
- **One Indonesian blog post was never mirrored** — the translation of
  "widening the wealth gap". Its language switcher falls back to the Indonesian
  home page.
