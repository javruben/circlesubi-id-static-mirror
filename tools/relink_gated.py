"""
Re-run the absolute -> relative link rewrite over every built page.

Adding the three `id/*` gated routes to html/mobile/manifest.json makes them
mirrored routes, so the 105 hrefs that still pointed at
`https://www.circlesubi.id/id/circles-research-faq` (and the two sibling
routes) can now resolve inside the mirror. relativize_links only matches
absolute circlesubi.id URLs, so this pass is idempotent for links that were
already rewritten by the original build.
"""

import json
import os

import build_mobile as bm

from paths import SITE, MANIFEST


def current_dir_for(path):
    """Relative-link base for a built file: the directory it is served from,
    relative to site/."""
    return os.path.relpath(os.path.dirname(path), SITE).replace(os.sep, "/").lstrip(".").lstrip("/")


def main():
    with open(MANIFEST) as f:
        manifest = json.load(f)
    url_to_rel = bm.build_url_to_rel(manifest)

    changed = 0
    for dirpath, dirnames, filenames in os.walk(SITE):
        if ".git" in dirpath.split(os.sep):
            continue
        for name in filenames:
            if not name.endswith(".html"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            new = bm.relativize_links(html, current_dir_for(path), url_to_rel)
            if new != html:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
                changed += 1
    print(f"rewrote {changed} files")


if __name__ == "__main__":
    main()
