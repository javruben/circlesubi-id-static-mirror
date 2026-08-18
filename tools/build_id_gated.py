"""
Build the Indonesian (/id/) variants of the three password-gated pages.

The original mirror build captured the gated pages (circles-research-faq,
circles-resources, impact-monitoring-tools) in English only — html/mobile/
manifest.json lists 33 `id/*` routes, none of them gated, so `site/id/` had
no equivalent of those three routes at all and every ID page's link to them
(105 hrefs) still pointed at the live Wix site.

This script consumes fresh captures of the live ID pages (see CAPTURES
below) and emits the same four-file shape the English gated pages use:

    site/id/<rel>/index.html          password gate shell (Indonesian copy)
    site/id/<rel>/content.json        script-stripped, relativized capture
    site/id/<rel>/content.html        == content.json, written out
    site/id/<rel>/content-mobile.html mobile capture, same treatment

Unlike the English build, all three ID pages have a *real* mobile capture
(the English circles-research-faq had to fall back to splicing TINY_MENU
into the desktop DOM, because re-clicking 21 accordion tabs under mobile
emulation was judged too expensive). The Wix faq-ooi accordion is still
replaced with plain <details>/<summary> on mobile, for the same
baked-desktop-geometry reason documented in build_mobile.py.

Scope note: like the English capture, only the first accordion category
("Exchange with Circles" / 17 pairs) is populated. The other 20 tabs load
per-click from a live Wix API with no static equivalent, so they are dead
UI in both languages.
"""

import importlib.util
import json
import os
import shutil

import build_mobile as bm

from paths import CAPTURES_ROOT as ROOT, MANIFEST, SITE


def _load_gate_template():
    """gate-template.py has a hyphen in its name, so it can't be imported
    with a plain `import` statement."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate-template.py")
    spec = importlib.util.spec_from_file_location("gate_template", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gt = _load_gate_template()
CAPTURE_DIR = os.environ.get(
    "ID_CAPTURE_DIR", "/Users/prime/dev/naoms/context-dumps/wix-id-cap"
)

# rel (under site/) -> (live page title, desktop capture, mobile capture)
CAPTURES = {
    "id/circles-research-faq": (
        "Research FAQ",
        "desktop-circles-research-faq.json",
        "mobile-circles-research-faq.json",
    ),
    "id/circles-resources": (
        "Sarana Penelitian",
        "desktop-circles-resources.json",
        "mobile-circles-resources.json",
    ),
    "id/impact-monitoring-tools": (
        "Pengukuran Dampak",
        "desktop-impact-monitoring-tools.json",
        "mobile-impact-monitoring-tools.json",
    ),
}

FAQ_QA_CAPTURE = "faq-id-exchange.json"
DOCTYPE = "<!DOCTYPE html>\n"


def load_capture(name):
    with open(os.path.join(CAPTURE_DIR, name)) as f:
        return json.load(f)


def process_desktop(raw, rel, url_to_rel):
    html = bm.SCRIPT_RE.sub("", raw)
    html = bm.relativize_links(html, rel, url_to_rel)
    return DOCTYPE + html


def process_mobile(raw, rel, url_to_rel, faq_qa_pairs=None):
    html = bm.SCRIPT_RE.sub("", raw)
    if faq_qa_pairs:
        html = bm.replace_faq_accordion(html, faq_qa_pairs)
    html = bm.relativize_links(html, rel, url_to_rel)
    if "</head>" in html:
        html = html.replace("</head>", bm.FAQ_ACCORDION_CSS + bm.HAMBURGER_CSS + "</head>", 1)
    else:
        html = bm.FAQ_ACCORDION_CSS + bm.HAMBURGER_CSS + html
    if "</body>" in html:
        html = html.replace("</body>", bm.HAMBURGER_JS + "</body>", 1)
    else:
        html = html + bm.HAMBURGER_JS
    return DOCTYPE + html


def extend_manifest(manifest_path):
    """Register the ID gated routes so future runs of build_mobile.py (and
    the link relativizer, which derives its URL->rel map from the manifest)
    know these routes are mirrored."""
    with open(manifest_path) as f:
        manifest = json.load(f)
    have = {e["rel"] for e in manifest}
    added = []
    for rel in CAPTURES:
        if rel in have:
            continue
        manifest.append(
            {
                "rel": rel,
                "url": f"https://circlesubi.id/{rel}/",
                "outfile": f"html/mobile/{rel}.json",
                "gated": True,
            }
        )
        added.append(rel)
    if added:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=1)
            f.write("\n")
    return manifest, added


def main():
    manifest_path = MANIFEST
    manifest, added = extend_manifest(manifest_path)
    url_to_rel = bm.build_url_to_rel(manifest)

    faq_qa_pairs = load_capture(FAQ_QA_CAPTURE)

    for rel, (title, desktop_cap, mobile_cap) in CAPTURES.items():
        out_dir = os.path.join(SITE, rel)
        os.makedirs(out_dir, exist_ok=True)

        desktop = process_desktop(load_capture(desktop_cap), rel, url_to_rel)
        with open(os.path.join(out_dir, "content.json"), "w") as f:
            json.dump(desktop, f)
        with open(os.path.join(out_dir, "content.html"), "w") as f:
            f.write(desktop)

        qa = faq_qa_pairs if rel.endswith("circles-research-faq") else None
        mobile = process_mobile(load_capture(mobile_cap), rel, url_to_rel, qa)
        with open(os.path.join(out_dir, "content-mobile.html"), "w") as f:
            f.write(mobile)

        with open(os.path.join(out_dir, "index.html"), "w") as f:
            f.write(gt.gate_html(title, lang="id"))

        # keep the mobile capture alongside the English ones so the route is
        # reproducible from html/mobile/ without re-driving a browser
        mobile_store = os.path.join(ROOT, "html", "mobile", rel + ".json")
        os.makedirs(os.path.dirname(mobile_store), exist_ok=True)
        shutil.copyfile(os.path.join(CAPTURE_DIR, mobile_cap), mobile_store)

        print(f"built {rel}: desktop {len(desktop)} B, mobile {len(mobile)} B")

    print(f"manifest entries added: {added}")


if __name__ == "__main__":
    main()
