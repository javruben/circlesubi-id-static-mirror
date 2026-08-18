"""
Combine desktop site/<rel>/index.html (already relativized, script-stripped)
with html/mobile/<key>.json captures into a dual-variant page per route.

Dynamically swapping a document's viewport meta via document.write() does NOT
reliably re-trigger the browser's viewport recalculation (verified: a
mid-parse document.open()/write()/close() left window.innerWidth stuck at the
desktop value even though the written document's own <meta viewport> claimed
width=320). A genuine top-level navigation, by contrast, always applies the
navigated-to document's own viewport meta correctly. So instead of swapping
DOM in place, small screens get redirected (via screen.width, which needs no
layout/meta processing and is available synchronously) to a real, separate
mobile document at site/<rel>/m/index.html.
"""
import json
import os
import posixpath
import re

from paths import CAPTURES_ROOT as ROOT, MANIFEST, SITE, data

SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)

HAMBURGER_CSS = """<style>
nav#TINY_MENU{position:relative}
nav#TINY_MENU>ul{display:none}
nav#TINY_MENU.menu-open>ul{
  display:flex!important;flex-direction:column;position:fixed;inset:0;
  z-index:99999;background:#fff;padding:5rem 1.5rem 2rem;margin:0;
  list-style:none;overflow-y:auto
}
nav#TINY_MENU.menu-open>ul li{border-bottom:1px solid rgba(0,0,0,.08)}
nav#TINY_MENU.menu-open>ul a{
  display:block;padding:1rem 0;font-size:1.1rem;text-decoration:none;color:inherit
}
nav#TINY_MENU.menu-open button[data-testid="tinymenu-menubutton"]{
  position:fixed!important;top:1rem!important;right:1rem!important;
  width:40px!important;height:40px!important;z-index:100000
}
</style>"""

HAMBURGER_JS = """<script>
(function(){
  var nav = document.getElementById('TINY_MENU');
  if (!nav) return;
  var btn = nav.querySelector('button[data-testid="tinymenu-menubutton"]');
  var list = nav.querySelector('ul');
  if (!btn || !list) return;
  btn.addEventListener('click', function(){
    nav.classList.toggle('menu-open');
    var open = nav.classList.contains('menu-open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    list.setAttribute('aria-hidden', open ? 'false' : 'true');
  });
})();
</script>"""

LINK_ATTR_RE = re.compile(r'((?:href|action)=")(https?://(?:www\.)?circlesubi\.id)(/[^"]*)?(")')


def load_manifest():
    with open(MANIFEST) as f:
        return json.load(f)


def build_url_to_rel(manifest):
    m = {}
    for e in manifest:
        rel = e["rel"]
        # normalize the mirrored path forms Wix might emit
        path = "/" + rel if rel else "/"
        m[path.rstrip("/") or "/"] = rel
        m[path if path.endswith("/") else path + "/"] = rel
    return m


def rel_link(current_dir, target_rel):
    cur_dir = current_dir if current_dir else "."
    tgt_dir = target_rel if target_rel else "."
    r = posixpath.relpath(tgt_dir, start=cur_dir)
    return "./" if r == "." else r + "/"


def relativize_links(html, current_dir, url_to_rel):
    def repl(m):
        prefix, domain, path, suffix = m.groups()
        path = path or "/"
        key = path if path.endswith("/") else path + "/"
        key_nolang = key.rstrip("/") or "/"
        target_rel = url_to_rel.get(key) or url_to_rel.get(key_nolang)
        if target_rel is None:
            # not a mirrored page (external PDF, non-scraped taxonomy page, etc.)
            return prefix + domain + path + suffix
        return prefix + rel_link(current_dir, target_rel) + suffix

    return LINK_ATTR_RE.sub(repl, html)


def process_mobile_html(raw, current_dir, url_to_rel):
    """current_dir is the *mobile file's own* directory (e.g. 'research/m'),
    used as the base for relative link computation — links always point back
    at the target route's desktop index.html, which re-runs the redirect
    check itself."""
    html = SCRIPT_RE.sub("", raw)
    html = relativize_links(html, current_dir, url_to_rel)
    if "</head>" in html:
        html = html.replace("</head>", HAMBURGER_CSS + "</head>", 1)
    else:
        html = HAMBURGER_CSS + html
    if "</body>" in html:
        html = html.replace("</body>", HAMBURGER_JS + "</body>", 1)
    else:
        html = html + HAMBURGER_JS
    return html


REDIRECT_SCRIPT = '<script>if(screen&&screen.width<=750){location.replace("m/");}</script>'


def inject_redirect(desktop_html):
    marker = '<meta charset="utf-8">'
    idx = desktop_html.find(marker)
    if idx == -1:
        raise ValueError("charset meta not found")
    insert_at = idx + len(marker)
    return desktop_html[:insert_at] + REDIRECT_SCRIPT + desktop_html[insert_at:]


HEADER_LANDMARK = (
    'M46.5 28.9L20.6 3c-.6-.6-1.6-.6-2.2 0l-4.8 4.8c-.6.6-.6 1.6 0 2.2l19.8 20-19.9 '
    '19.9c-.6.6-.6 1.6 0 2.2l4.8 4.8c.6.6 1.6.6 2.2 0l21-21 4.8-4.8c.8-.6.8-1.6.2-2.2z'
)
INSERT_AFTER = '</a></div><!--/$-->'


def extract_tiny_menu(mobile_home_html):
    i = mobile_home_html.find('id="TINY_MENU"')
    start = mobile_home_html.rfind("<nav", 0, i)
    end = mobile_home_html.find("</nav>", i) + len("</nav>")
    return mobile_home_html[start:end]


def extract_mobile_head_styles(mobile_home_html):
    """The spliced-in TINY_MENU markup (extract_tiny_menu) is a bare DOM
    fragment with none of its component-scoped CSS — that CSS only lives in
    the mobile capture's own <head> (verified: without it, the hamburger
    button rendered at 0x0, invisible). Grafting the real mobile capture's
    <style> tags in wholesale is the only way to get correct styling without
    hand-picking which of Wix's auto-generated, unstable class names matter."""
    head_end = mobile_home_html.find("</head>")
    head = mobile_home_html[:head_end] if head_end != -1 else mobile_home_html
    return "".join(re.findall(r"<style[^>]*>.*?</style>", head, re.DOTALL))


# #comp-lcsr4sj41 is circles-research-faq's own in-page desktop quick-nav
# strip (Resources/FAQ/Monitoring buttons), redundant with the spliced-in
# TINY_MENU hamburger and laid out for a wide viewport regardless of the
# min-width override, so it's hidden outright for the mobile variant.
WIDTH_OVERRIDE_CSS = (
    "<style>*{min-width:0!important;max-width:100%!important}"
    "#comp-lcsr4sj41{display:none!important}"
    "</style>"
)

FAQ_ACCORDION_CSS = """<style>
.faq-plain{padding:1rem}
.faq-plain details{border-bottom:1px solid rgba(0,0,0,.12);padding:.75rem 0}
.faq-plain summary{font-weight:600;cursor:pointer;list-style:none}
.faq-plain summary::-webkit-details-marker{display:none}
.faq-plain summary:before{content:"+ ";color:#3ecf8e}
.faq-plain details[open] summary:before{content:"\\2212 "}
.faq-plain p{margin:.75rem 0 0;white-space:pre-line;opacity:.85}
</style>"""

TAG_RE = re.compile(r"<(/?)([a-zA-Z0-9-]+)[^>]*?(/?)>")
VOID_TAGS = {"br", "img", "input", "meta", "link", "hr"}


def find_balanced_element(html, start, tagname):
    """start must point at the '<' of the element's own opening tag."""
    depth = 0
    for m in TAG_RE.finditer(html, start):
        name = m.group(2).lower()
        if name in VOID_TAGS:
            continue
        if m.group(1) == "/":
            if name == tagname:
                depth -= 1
                if depth == 0:
                    return m.end()
        else:
            if m.group(3) == "/":
                continue
            if name == tagname:
                depth += 1
    return None


def render_faq_accordion(qa_pairs):
    import html as html_mod

    items = []
    for pair in qa_pairs:
        q = html_mod.escape(pair["q"])
        a = html_mod.escape(pair["a"])
        items.append(f"<details><summary>{q}</summary><p>{a}</p></details>")
    return (
        '<section id="comp-lcsvllay" class="faq-plain">' + "".join(items) + "</section>"
    )


def replace_faq_accordion(html, qa_pairs):
    """circles-research-faq's #comp-lcsvllay is a Wix faq-ooi widget with
    hardcoded desktop-pixel row widths (~900px) baked into inline/computed
    styles at capture time — not a min-width issue, an actual geometry
    issue. Four rounds of increasingly targeted CSS (blanket max-width,
    then a scoped overflow-x:auto scroll container) both failed: rows are
    centered/flex-positioned so their overflow extends to *negative* x
    offsets relative to the container's own scroll origin, which
    overflow-x:auto structurally cannot reveal (scroll only reaches
    [0, scrollWidth], never negative). Per REBUILD-ANALYSIS.md §3's own
    recommendation for this exact widget, replace the widget's markup
    outright with plain <details>/<summary> rendered from the same Q&A
    data rather than continuing to patch Wix's geometry."""
    start = html.find('<section id="comp-lcsvllay"')
    if start == -1:
        return html
    end = find_balanced_element(html, start, "section")
    if end is None:
        raise ValueError("unbalanced #comp-lcsvllay section")
    return html[:start] + render_faq_accordion(qa_pairs) + html[end:]


def splice_mobile_nav(desktop_html, tiny_menu_block, mobile_head_styles, faq_qa_pairs=None):
    """Gated content.json is already a fully-merged desktop capture (all
    accordion tabs pre-expanded). Re-deriving that via mobile emulation would
    mean re-clicking through 21 FAQ tabs; instead reuse the same content and
    graft in the real mobile TINY_MENU chrome (identical site-wide nav
    component) at the same position it occupies in a real mobile capture.

    Wix's mesh-layout bakes `min-width:980px` onto ~19 per-component #comp-*
    id selectors in the desktop capture, which forces the mobile browser to
    auto-expand its layout viewport past the width=320 meta regardless (none
    of those rules use !important, so a blanket !important override safely
    beats every one of them without touching per-component positioning).

    The header-landmark search (matching the site-wide nav arrow icon's SVG
    path, then inserting after the following link/div close) only works when
    that exact markup shape is present in the desktop capture; on this page
    it isn't (find() returns -1), which silently produced a bogus insert_idx
    near byte 18 and spliced the nav block into the middle of the opening
    <html> tag, corrupting the whole document. Insert right after <body...>
    instead — robust regardless of header markup shape, and functionally
    equivalent (nav still renders at the very top of the page)."""
    body_match = re.search(r"<body[^>]*>", desktop_html)
    if not body_match:
        raise ValueError("<body> tag not found")
    insert_idx = body_match.end()
    html = desktop_html[:insert_idx] + tiny_menu_block + desktop_html[insert_idx:]
    html = html.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1" id="wixDesktopViewport">',
        '<meta name="viewport" content="width=320, user-scalable=yes" id="wixMobileViewport">',
    )
    if faq_qa_pairs:
        html = replace_faq_accordion(html, faq_qa_pairs)
    head_addition = mobile_head_styles + WIDTH_OVERRIDE_CSS + FAQ_ACCORDION_CSS
    if "</head>" in html:
        html = html.replace("</head>", head_addition + "</head>", 1)
    else:
        html = head_addition + html
    return html


def build_gated(manifest, url_to_rel, tiny_menu_block, mobile_head_styles, faq_qa_pairs):
    """Gated pages keep their existing password-gate shell (desktop
    viewport, unchanged) and swap in real content via a genuine navigation
    (location.replace) rather than document.write, for the same reason as
    the redirect approach above: content.html/content-mobile.html are full
    standalone documents with their own correct viewport meta.

    Two of the three gated pages (circles-resources, impact-monitoring-tools)
    got real mobile-emulation captures in html/mobile/<rel>.json, same as the
    67 public pages, once their live gate was already unlocked from an
    earlier capture in this session. circles-research-faq's content is only
    fully present in the desktop capture (128 Q&A merged across 21
    accordion tabs, each requiring a separate click to load/expand — too
    expensive to re-derive under mobile emulation), so it still uses the
    splice+CSS-override fallback."""
    built = []
    for e in manifest:
        if not e.get("gated"):
            continue
        rel = e["rel"]
        content_path = os.path.join(SITE, rel, "content.json")
        with open(content_path) as f:
            desktop_content = json.load(f)

        desktop_out = os.path.join(SITE, rel, "content.html")
        with open(desktop_out, "w") as f:
            f.write(desktop_content)

        mobile_outfile = os.path.join(ROOT, e["outfile"])
        if os.path.exists(mobile_outfile):
            with open(mobile_outfile) as f:
                raw_mobile = json.load(f)
            mobile_content = process_mobile_html(raw_mobile, rel, url_to_rel)
        else:
            qa_pairs = faq_qa_pairs if rel == "circles-research-faq" else None
            spliced = splice_mobile_nav(desktop_content, tiny_menu_block, mobile_head_styles, qa_pairs)
            mobile_content = process_mobile_html(spliced, rel, url_to_rel)
        mobile_out = os.path.join(SITE, rel, "content-mobile.html")
        with open(mobile_out, "w") as f:
            f.write(mobile_content)

        old_json = os.path.join(SITE, rel, "content-mobile.json")
        if os.path.exists(old_json):
            os.remove(old_json)

        built.append(rel)
    return built


def main():
    manifest = load_manifest()
    url_to_rel = build_url_to_rel(manifest)
    mobile_home_path = os.path.join(ROOT, "html", "mobile", "home.json")
    with open(mobile_home_path) as f:
        mobile_home_html = json.load(f)
    tiny_menu_block = extract_tiny_menu(mobile_home_html)
    mobile_head_styles = extract_mobile_head_styles(mobile_home_html)

    # circles-research-faq's frozen desktop capture only ever has the first
    # accordion category ("Exchange with Circles", 17 pairs) populated —
    # the other 20 tabs load per-click via a live Wix API call that has no
    # equivalent in this static mirror, so switching tabs on the deployed
    # desktop page is already dead UI. Matching that same 17-pair scope for
    # the mobile rewrite (rather than pulling in all 128 pairs from
    # faq-all-merged.json) keeps desktop/mobile content identical instead
    # of introducing a mismatch beyond the scope of the mobile-rendering fix.
    faq_merged_path = data("faq-all-merged.json")
    with open(faq_merged_path) as f:
        faq_qa_pairs = json.load(f)["Exchange with Circles"]

    gated_built = build_gated(manifest, url_to_rel, tiny_menu_block, mobile_head_styles, faq_qa_pairs)
    print(f"gated built: {gated_built}")

    built, skipped = [], []
    for e in manifest:
        if e.get("gated"):
            continue
        rel = e["rel"]
        outfile = os.path.join(ROOT, e["outfile"])
        if not os.path.exists(outfile):
            skipped.append(rel)
            continue
        with open(outfile) as f:
            raw = json.load(f)
        if isinstance(raw, dict) and raw.get("__mismatch"):
            skipped.append(rel + " (mismatch, needs recapture)")
            continue

        mobile_dir = posixpath.join(rel, "m") if rel else "m"
        mobile_html = process_mobile_html(raw, mobile_dir, url_to_rel)

        m_out_dir = os.path.join(SITE, rel, "m") if rel else os.path.join(SITE, "m")
        os.makedirs(m_out_dir, exist_ok=True)
        with open(os.path.join(m_out_dir, "index.html"), "w") as f:
            f.write(mobile_html)

        site_path = os.path.join(SITE, rel, "index.html") if rel else os.path.join(SITE, "index.html")
        with open(site_path) as f:
            desktop_html = f.read()

        combined = inject_redirect(desktop_html)
        with open(site_path, "w") as f:
            f.write(combined)
        built.append(rel)

    print(f"built: {len(built)}")
    print(f"skipped ({len(skipped)}): {skipped}")


if __name__ == "__main__":
    main()
