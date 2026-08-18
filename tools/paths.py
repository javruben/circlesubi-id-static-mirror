"""
Locate the built site, the capture metadata and the raw captures.

These scripts were written against the scrape working tree, where everything
sits side by side:

    circles-scrape/
      scripts/          <- this file
      site/             <- the built mirror (and the git repo)
      html/mobile/      <- raw page captures, ~144 MB
      faq-*.json        <- capture metadata

Only `site/` is versioned, so the copy of these scripts that lives inside the
repo is one level in from the site root instead:

    <repo>/
      tools/            <- this file
      tools/data/       <- the capture metadata, ~490 KB
      index.html …      <- the built mirror

Both layouts are recognised here so a script does not need to care which one it
is running from. The raw captures are far too large to version, so scripts that
need them (build_mobile.py, build_id_gated.py) only work from the scrape tree
unless CIRCLES_CAPTURES points at a copy.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)

if os.path.isdir(os.path.join(_PARENT, "site")):
    # scrape working tree: circles-scrape/scripts/
    SITE = os.path.join(_PARENT, "site")
    DATA = _PARENT
    CAPTURES_ROOT = _PARENT
else:
    # inside the published repo: <repo>/tools/
    SITE = _PARENT
    DATA = os.path.join(_HERE, "data")
    CAPTURES_ROOT = _PARENT

# manifest paths in the manifest itself ("outfile") are relative to whichever
# directory holds html/, so an override has to move CAPTURES_ROOT, not just the
# manifest
CAPTURES_ROOT = os.environ.get("CIRCLES_CAPTURES", CAPTURES_ROOT)

_LEGACY_MANIFEST = os.path.join(CAPTURES_ROOT, "html", "mobile", "manifest.json")
MANIFEST = _LEGACY_MANIFEST if os.path.isfile(_LEGACY_MANIFEST) else os.path.join(DATA, "manifest.json")


def data(name):
    """Path to a capture-metadata file, wherever this checkout keeps them."""
    return os.path.join(DATA, name)
