"""
Make the EN/ID flag switcher in the site header actually navigate.

Wix renders the language selector as two bare <button> elements and wires the
navigation up in JavaScript. The mirror strips every <script>, so the flags
render but do nothing — on the English pages and the Indonesian ones alike.

The destination for each page is already in the mirror: the original build
kept (and relativized) the Wix <link rel="alternate" hreflang="en-us"> /
hreflang="id-id"> head tags, so every page knows where its counterpart in the
other language lives.

Why the buttons stay buttons: the LanguageSelector stylesheet targets
`.CjkVyx>button` — element-qualified. Swapping in an <a> would drop the
background, height, flex layout, border radius and separator rule, i.e. the
whole widget's appearance. So this pass keeps the <button>, records the
destination in a data-lang-href attribute, and appends one small inline
script that turns a click into a navigation.

Idempotent: files that already carry data-lang-href are skipped.
"""

import os
import re
import sys

from paths import SITE

CONTAINER = 'data-testid="languages-container"'
# the two selector buttons always follow the container marker closely; bound
# the search so unrelated aria-label="English" page buttons can't be hit
WINDOW = 2000

BUTTON_RE = re.compile(r'<button(?P<attrs>[^>]*aria-label="(?P<lang>English|Indonesian)"[^>]*)>')
ALT_RE = re.compile(r'<link[^>]*rel="alternate"[^>]*>')
HREF_RE = re.compile(r'href="([^"]*)"')
HREFLANG_RE = re.compile(r'hreflang="([^"]*)"')

SWITCHER_JS = """<script>
/* language switcher: Wix drives these buttons with JS that the mirror strips,
   so re-attach the navigation from the destination baked in by the build. */
(function () {
  document.querySelectorAll('[data-lang-href]').forEach(function (b) {
    b.addEventListener('click', function () {
      window.location.href = b.getAttribute('data-lang-href');
    });
  });
})();
</script>"""


def alternates(html):
    """{hreflang: href} from the page's own <link rel="alternate"> tags."""
    out = {}
    for tag in ALT_RE.findall(html):
        lang = HREFLANG_RE.search(tag)
        href = HREF_RE.search(tag)
        if not lang or not href:
            continue
        # An absolute href means the build never mirrored that counterpart
        # (one ID blog post was missed by the original capture). Treat it as
        # no alternate rather than bouncing a mirror visitor onto the live
        # Wix site mid-browse; the caller degrades to the language home.
        if href.group(1).startswith(("http://", "https://", "//")):
            continue
        out[lang.group(1)] = href.group(1)
    return out


def resolve(path, href):
    """Absolute path of the directory `href` points at, from `path`'s dir."""
    return os.path.normpath(os.path.join(os.path.dirname(path), href))


def prefer_mobile(path, href):
    """Mobile pages live at <rel>/m/. A flag click from a mobile page should
    land on the other language's mobile build when one exists, not kick the
    visitor back to the desktop capture."""
    if not path.endswith(os.path.join("m", "index.html")):
        return href
    candidate = href.rstrip("/") + "/m/" if href not in ("./", "") else "m/"
    if os.path.isfile(os.path.join(resolve(path, candidate), "index.html")):
        return candidate
    return href


def targets(path, html):
    """(english_href, indonesian_href) for this page, or None if neither can
    be determined."""
    alt = alternates(html)
    en = alt.get("en-us") or alt.get("x-default")
    idn = alt.get("id-id")

    rel = os.path.relpath(path, SITE).replace(os.sep, "/")
    in_id = rel == "id/index.html" or rel.startswith("id/")

    if not en or not idn:
        # One gated desktop capture and one English-only blog post carry no
        # alternates. Mirror the path across the /id/ prefix, and only when
        # that counterpart does not exist fall back to the other language's
        # home page — which is where a switcher degrades to when the current
        # page genuinely has no translation.
        up = "../" * rel.count("/")
        page = rel.rsplit("/", 1)[0]
        if in_id:
            twin = up + (page[len("id/"):] + "/" if page != "id" else "")
            en = en or (twin if os.path.isdir(resolve(path, twin)) else up)
            idn = idn or "./"
        else:
            twin = up + "id/" + (page + "/" if page != rel else "")
            idn = idn or (twin if os.path.isdir(resolve(path, twin)) else up + "id/")
            en = en or "./"

    return prefer_mobile(path, en), prefer_mobile(path, idn)


def wire(html, en_href, id_href):
    """Add data-lang-href to the two buttons inside each languages-container."""
    hrefs = {"English": en_href, "Indonesian": id_href}
    changed = 0

    def sub(bm):
        nonlocal changed
        if "data-lang-href" in bm.group("attrs"):
            return bm.group(0)
        changed += 1
        return f'<button data-lang-href="{hrefs[bm.group("lang")]}"{bm.group("attrs")}>'

    starts = [m.end() for m in re.finditer(re.escape(CONTAINER), html)]
    out = []
    pos = 0
    for i, start in enumerate(starts):
        # a page can carry more than one selector (the gated captures hold a
        # desktop and a mobile header); never let one container's window run
        # into the next one's buttons
        limit = min(start + WINDOW, starts[i + 1] if i + 1 < len(starts) else len(html))
        out.append(html[pos:start])
        out.append(BUTTON_RE.sub(sub, html[start:limit], count=2))
        pos = limit
    out.append(html[pos:])
    return "".join(out), changed


STALE_ATTR_RE = re.compile(r' data-lang-href="[^"]*"')


def main():
    force = "--force" in sys.argv  # re-derive destinations on already-wired pages
    wired = 0
    for dirpath, _dirnames, filenames in os.walk(SITE):
        if ".git" in dirpath.split(os.sep):
            continue
        for name in filenames:
            if not name.endswith(".html"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as f:
                html = f.read()
            if CONTAINER not in html:
                continue
            if force:
                html = STALE_ATTR_RE.sub("", html)

            en_href, id_href = targets(path, html)
            new, changed = wire(html, en_href, id_href)
            if not changed:
                continue
            if "data-lang-href" in html:
                pass  # partially wired already; the script tag is present
            elif "</body>" in new:
                new = new.replace("</body>", SWITCHER_JS + "</body>", 1)
            else:
                new += SWITCHER_JS

            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            wired += 1
            print(f"{os.path.relpath(path, SITE)}: EN -> {en_href}  ID -> {id_href}")
    print(f"\nwired {wired} files")


if __name__ == "__main__":
    main()
