"""
Make the FAQ accordion work off static data instead of a live Wix API.

The problem this replaces: the Wix faq-ooi widget renders its category tabs
eagerly but loads each category's Q&A on click, from a Wix backend. The mirror
has no backend, so every capture froze with exactly one category populated —
the one that happened to be open when the page was captured. On the deployed
site that means 1 of 21 categories works on circles-research-faq and 1 of 6 on
copy-of-faq-1; clicking any other tab is dead UI.

All 21 categories (128 Q&A pairs) were captured separately at scrape time and
live in faq-all-merged.json, so the data was never the missing piece — only the
delivery was. This pass writes that data out as a static JSON asset under
site/data/ and swaps the Wix widget for a small self-contained accordion that
fetches it.

Why replace the widget rather than re-populate it: the same reason the mobile
build already replaced it (see build_mobile.replace_faq_accordion) — the
captured widget carries hardcoded desktop-pixel geometry that no amount of CSS
recovers. Driving new content into that DOM would inherit the broken geometry
and depend on Wix's own class names surviving, which they don't across
captures. A plain tabs + <details> accordion is both smaller and honest about
what it is.

Indonesian: only the first category was ever captured with Indonesian text (it
is the one frozen open in the ID capture). The other 20 have no translation in
hand, so faq-id.json carries the English text for them and flags
translated:false; the renderer shows a short note on those tabs rather than
silently passing English off as the Indonesian page's own content.
"""

import html as html_mod
import json
import os
import re

import build_mobile as bm

from paths import SITE, data

DATA_DIR = os.path.join(SITE, "data")

# Every page that carries the FAQ widget. The gated routes have no index.html
# of their own (that slot holds the password shell), so their content lives in
# content.html / content-mobile.html instead.
PAGES = [
    "circles-research-faq/content.html",
    "circles-research-faq/content-mobile.html",
    "copy-of-faq-1/index.html",
    "copy-of-faq-1/m/index.html",
    "id/circles-research-faq/content.html",
    "id/circles-research-faq/content-mobile.html",
    "id/copy-of-faq-1/index.html",
    "id/copy-of-faq-1/m/index.html",
]

# the ID page whose frozen-open tab holds the one translated category
ID_TRANSLATED_SOURCE = "id/circles-research-faq/content-mobile.html"

TAB_RE = re.compile(r'data-hook="tab-item-(\d+)"[^>]*>(.{0,400}?)</', re.S)
DETAILS_RE = re.compile(r"<details><summary>(.*?)</summary><p>(.*?)</p></details>", re.S)
FAQ_ROOT = 'data-hook="faq-root"'
PLAIN_SECTION = '<section id="comp-lcsvllay" class="faq-plain">'
MARKER = 'id="static-faq"'


def strip_tags(s):
    return html_mod.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def page_tabs(html):
    """Ordered tab labels as the captured page shows them."""
    seen = {}
    for m in TAB_RE.finditer(html):
        i = int(m.group(1))
        if i not in seen:
            seen[i] = strip_tags(m.group(2))
    return [seen[i] for i in sorted(seen)]


def plain_qa(html):
    """Q&A out of a mobile build's already-flattened <details> accordion."""
    return [
        {"q": html_mod.unescape(q).strip(), "a": html_mod.unescape(a).strip()}
        for q, a in DETAILS_RE.findall(html)
    ]


def read(rel):
    with open(os.path.join(SITE, rel), encoding="utf-8") as f:
        return f.read()


def canonical_order():
    """Category titles in the order the site's own category list defines, so
    the tab strip does not depend on dict insertion order."""
    with open(data("faq-categories.json")) as f:
        cats = json.load(f)["categories"]
    return [c["title"] for c in sorted(cats, key=lambda c: c["sortOrder"])]


DERIVED = "faq-derived.json"


def derive():
    """Everything this build needs that only exists inside the captured Wix
    widget: the Indonesian category labels, the one category that was captured
    with Indonesian text, and each page's own category list.

    Read once from the captured pages and cached alongside the other capture
    metadata, because replacing the widget destroys the only copy — without the
    cache this script would work exactly once per capture, which is no good for
    a checkout that has the built site but not the 144 MB of raw captures.
    """
    path = data(DERIVED)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # Indonesian labels are index-aligned with the English tab strip on the
    # 21-category page, which is the only page that carries all of them.
    en_labels = page_tabs(read("circles-research-faq/content.html"))
    id_labels = page_tabs(read("id/circles-research-faq/content.html"))
    if not en_labels or not id_labels:
        raise SystemExit(
            f"{DERIVED} is missing and the captured FAQ widget is already gone "
            "from the built pages — restore the pages from git, or restore "
            f"{path}, before rebuilding."
        )
    id_to_en = {i: e for e, i in zip(en_labels, id_labels)}

    page_cats = {}
    for rel in PAGES:
        labels = page_tabs(read(rel)) or page_tabs(
            read(rel.replace("content-mobile.html", "content.html"))
        )
        page_cats[rel] = (
            [id_to_en.get(l, l) for l in labels] if rel.startswith("id/") else labels
        )

    derived = {
        "id_labels": dict(zip(en_labels, id_labels)),
        "id_translated": {en_labels[0]: plain_qa(read(ID_TRANSLATED_SOURCE))},
        "page_cats": page_cats,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(derived, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"wrote {DERIVED} (cached from the captured widget)")
    return derived


def build_datasets(derived):
    """(en, id) datasets: {"categories": [{title, label, translated, qa}]}."""
    with open(data("faq-all-merged.json")) as f:
        merged = json.load(f)

    order = [t for t in canonical_order() if t in merged]
    order += [t for t in merged if t not in order]

    en = {
        "categories": [
            {"title": t, "label": t, "translated": True, "qa": merged[t]}
            for t in order
        ]
    }

    label_map = derived["id_labels"]
    translated = derived["id_translated"]

    id_ = {
        "categories": [
            {
                "title": t,
                "label": label_map.get(t, t),
                "translated": t in translated,
                "qa": translated.get(t, merged[t]),
            }
            for t in order
        ]
    }
    return en, id_


FAQ_CSS = """<style>
#static-faq{max-width:900px;margin:0 auto;padding:1rem;box-sizing:border-box;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
#static-faq .faq-tabs{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1.25rem}
#static-faq .faq-tabs button{border:1px solid rgba(0,0,0,.15);background:#fff;color:inherit;
  border-radius:999px;padding:.4rem .9rem;font-size:.85rem;cursor:pointer;line-height:1.3}
#static-faq .faq-tabs button:hover{border-color:#3ecf8e}
#static-faq .faq-tabs button[aria-selected="true"]{background:#3ecf8e;border-color:#3ecf8e;color:#04241b;font-weight:600}
#static-faq .faq-note{font-size:.8rem;opacity:.7;margin:0 0 1rem;font-style:italic}
#static-faq details{border-bottom:1px solid rgba(0,0,0,.12);padding:.75rem 0}
#static-faq summary{font-weight:600;cursor:pointer;list-style:none}
#static-faq summary::-webkit-details-marker{display:none}
#static-faq summary:before{content:"+ ";color:#3ecf8e}
#static-faq details[open] summary:before{content:"\\2212 "}
#static-faq details p{margin:.75rem 0 0;white-space:pre-line;opacity:.85}
#static-faq .faq-empty{opacity:.6;padding:1rem 0}
</style>"""

FAQ_JS = """<script>
/* FAQ accordion: the Wix widget loaded each category from a live backend the
   mirror has no equivalent for, so all but one tab were dead. Read the same
   Q&A from a static asset instead. */
(function () {
  var root = document.getElementById('static-faq');
  if (!root) return;
  var want = (root.getAttribute('data-faq-cats') || '').split('|').filter(Boolean);
  var note = root.getAttribute('data-faq-note') || '';
  var tabs = root.querySelector('.faq-tabs');
  var body = root.querySelector('.faq-body');

  function text(el, s) { el.textContent = s; return el; }

  function render(cat) {
    body.innerHTML = '';
    if (cat.translated === false && note) {
      body.appendChild(text(document.createElement('p'), note)).className = 'faq-note';
    }
    if (!cat.qa.length) {
      body.appendChild(text(document.createElement('div'), '—')).className = 'faq-empty';
      return;
    }
    cat.qa.forEach(function (pair) {
      var d = document.createElement('details');
      d.appendChild(text(document.createElement('summary'), pair.q));
      d.appendChild(text(document.createElement('p'), pair.a));
      body.appendChild(d);
    });
  }

  fetch(root.getAttribute('data-faq-src')).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (data) {
    var byTitle = {};
    data.categories.forEach(function (c) { byTitle[c.title] = c; });
    var cats = (want.length ? want : data.categories.map(function (c) { return c.title; }))
      .map(function (t) { return byTitle[t]; }).filter(Boolean);
    if (!cats.length) return;

    cats.forEach(function (cat, i) {
      var b = text(document.createElement('button'), cat.label || cat.title);
      b.type = 'button';
      b.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
      b.addEventListener('click', function () {
        tabs.querySelectorAll('button').forEach(function (o) {
          o.setAttribute('aria-selected', o === b ? 'true' : 'false');
        });
        render(cat);
      });
      tabs.appendChild(b);
    });
    render(cats[0]);
  }).catch(function (e) {
    body.textContent = 'Could not load the FAQ (' + e.message + ').';
  });
})();
</script>"""

ID_NOTE = "Belum diterjemahkan — ditampilkan dalam bahasa Inggris."


def container(src, cats, note):
    attrs = f'id="static-faq" data-faq-src="{src}" data-faq-cats="{html_mod.escape("|".join(cats))}"'
    if note:
        attrs += f' data-faq-note="{html_mod.escape(note)}"'
    return f'<div {attrs}><div class="faq-tabs"></div><div class="faq-body"></div></div>'


def widget_span(html):
    """(start, end) of the FAQ widget to replace, whichever form it is in."""
    start = html.find(FAQ_ROOT)
    if start != -1:
        start = html.rfind("<", 0, start)
        end = bm.find_balanced_element(html, start, "div")
        if end is None:
            raise ValueError("unbalanced faq-root div")
        return start, end
    start = html.find(PLAIN_SECTION)
    if start != -1:
        end = bm.find_balanced_element(html, start, "section")
        if end is None:
            raise ValueError("unbalanced faq-plain section")
        return start, end
    return None


def data_src(rel, lang):
    """Path from a built page back up to site/data/faq-<lang>.json."""
    depth = rel.count("/")
    return "../" * depth + f"data/faq-{lang}.json"


def main():
    derived = derive()
    en, id_ = build_datasets(derived)
    os.makedirs(DATA_DIR, exist_ok=True)
    for lang, data in (("en", en), ("id", id_)):
        with open(os.path.join(DATA_DIR, f"faq-{lang}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        pairs = sum(len(c["qa"]) for c in data["categories"])
        untranslated = [c["title"] for c in data["categories"] if not c["translated"]]
        print(f"data/faq-{lang}.json: {len(data['categories'])} categories, {pairs} pairs"
              + (f", {len(untranslated)} untranslated" if untranslated else ""))

    page_cats = derived["page_cats"]

    for rel in PAGES:
        path = os.path.join(SITE, rel)
        html = read(rel)
        if MARKER in html:
            print(f"{rel}: already static, skipped")
            continue

        lang = "id" if rel.startswith("id/") else "en"
        cats = page_cats[rel]
        if not cats:
            print(f"{rel}: no categories resolved, skipped")
            continue

        span = widget_span(html)
        if span is None:
            print(f"{rel}: no FAQ widget found, skipped")
            continue

        block = container(data_src(rel, lang), cats, ID_NOTE if lang == "id" else "")
        new = html[: span[0]] + block + html[span[1] :]
        if "</head>" in new:
            new = new.replace("</head>", FAQ_CSS + "</head>", 1)
        else:
            new = FAQ_CSS + new
        if "</body>" in new:
            new = new.replace("</body>", FAQ_JS + "</body>", 1)
        else:
            new += FAQ_JS

        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        print(f"{rel}: {len(cats)} categories wired ({lang}), {len(html) - len(new)} B removed")


if __name__ == "__main__":
    main()
