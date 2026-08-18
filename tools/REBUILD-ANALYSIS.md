# circlesubi.id — Rebuild Analysis

## 0. Status: static mirror built and deployed

A frozen static mirror has been built and deployed — this supersedes the "recommended rebuild architecture" in §3 below, which was written before the build existed and remains useful only as a reference for a *proper* (non-frozen) rebuild.

**Live at:** `https://javruben.github.io/circlesubi-id-static-mirror/` (repo: `javruben/circlesubi-id-static-mirror`, public, deployed via GitHub Pages from `main`/`/`).

**Build approach:** rather than reverse-engineering Wix's CSS delivery for an Astro rebuild, each captured page's `outerHTML` was used almost as-is — Wix's rendering pipeline already injects all necessary CSS as inline `<style>` tags into the DOM at capture time. The only transform applied is stripping all `<script>` tags (so Wix's hydration JS never runs against a live-Wix-origin app state, which would corrupt/blank the frozen DOM) and prepending `<!DOCTYPE html>`. Images and PDFs still link to the live `static.wixstatic.com` CDN / `circlesubi.id/_files/ugd/` rather than being re-hosted locally (a deliberate simplification — `assets/` has all 251 images + 26 PDFs downloaded locally if re-hosting is wanted later).

**Verified pixel-perfect:** full-page screenshot diffs (PIL/numpy, mean pixel diff + % pixels exceeding a diff threshold) between the local/deployed mirror and the live site, across the English homepage, an inner page, a blog post, and the Indonesian homepage — all in the 0.0–0.2% range, with the Indonesian homepage at exactly 0.000%.

**Site contents (structure under `site/`):**
- 34 English pages: home, research, FAQ (`copy-of-faq-1`), stories, resources, contact, grants, 27 blog posts.
- 33 Indonesian pages under `id/`: home, research, FAQ, stories, resources, contact, grants, 26 blog posts (translated slugs, discovered via Wix's `hreflang="id-id"` alternate-link tags on each English page — more reliable than the sitemap, which only lists English URLs). One English post ("Widening the Wealth Gap" research report) has no Indonesian variant.
- 3 password-gated pages (`circles-research-faq`, `circles-resources`, `impact-monitoring-tools`): each ships as a minimal HTML shell with a password field; on entry, the password is SHA-256-hashed client-side and compared against a stored hash, and only on match does JS `fetch()` the real page content (kept in a separate `content.json` fragment, not embedded in the initial HTML) and swap it in via `document.write`. **This is a soft UX gate, not real access control** — the repo is public and GitHub Pages' free/personal tier serves the built site publicly with no auth option regardless of repo visibility, so the gated content is reachable by anyone who inspects the JS/Network tab or clones the repo. This matches the live Wix site's own gate, which is equally soft — see §3 for more.
- Internal navigation links (`href="https://circlesubi.id/..."`) were rewritten to relative paths (e.g. `/research/`) wherever the target is actually mirrored above; links to non-mirrored content (blog category/hashtag/pagination pages, `blog-feed.xml`, PDFs, the untranslated post) were deliberately left pointing at the live site.

**Known gaps vs. a "real" rebuild:** no responsive image variants (linked directly to Wix's CDN originals), no re-hosted PDFs, blog taxonomy pages (categories/hashtags/pagination under `/stories/...`) were never scraped and still point live, and the password gate is cosmetic only as noted above.

## 1. What was scraped

All content-bearing pages of circlesubi.id were captured as fully client-rendered DOM snapshots (`html/*.json`, each wrapping the page's `document.documentElement.outerHTML`), plus every unique media asset referenced by them.

**Public pages (10):**
| Page | File | Notes |
|---|---|---|
| Home | `html/home.json` | Hero, mission, video embed, vision, partner logos |
| Research | `html/research.json` | |
| FAQ (general) | `html/faq.json` | `/copy-of-faq-1` |
| Stories | `html/stories.json` | Blog listing (5 categories) |
| Blog post × 3 | `html/post-*.json` | Individual posts; ~50 more exist per sitemap, only 3 captured as samples |
| Downloads | `html/resources.json` | ~10 public resources (PDF/image), EN+ID |
| Contact | `html/contact.json` | |
| Grants | `html/grants.json` | Undiscoverable via nav — found via `pages-sitemap.xml` |
| Legacy login | `html/legacy-login.json` | Dead/duplicate password gate, minimal content |

**Password-gated pages (3, unlocked with `circles2023`):**
| Page | File | Notes |
|---|---|---|
| Research FAQ | `html/member-faq-tab1.json` + `faq-qa-*.json` (21 files) | 21 category tabs, 128 Q&A pairs total, dynamically loaded per-click (see §3) |
| Resources (member) | `html/member-resources.json` | Distinct audience-tagged download set vs public `/resources` |
| Monitoring tools | `html/member-monitoring.json` | 7 Google Forms (interview/monitoring instruments), EN+ID |

**Confirmed dead ends (skipped):** `/copy-of-faq` → 404 redirect. `/style-sheet` not visited (Wix internal style-guide, never rendered to users).

**Assets downloaded** to `assets/`:
- `assets/images/` — 112 unique original images (188 MB), deduped from 328 resized-variant URLs found in the HTML (Wix serves every image through multiple `w_/h_/q_` transform variants of one canonical `~mv2.<ext>` file — only the canonical originals were kept)
- `assets/pdfs/` — 26 PDFs (245 MB) — research reports, guides, forms, monitoring templates
- `asset-manifest.json` — full URL manifest (all variant URLs + canonical + PDFs + the 9 Google Forms links)

**Total: 14 HTML pages, 128 FAQ Q&A pairs, 138 binary assets (433 MB).**

## 2. Why a Wix "export" isn't the path

As established in the earlier research: Wix has no native static export. Third-party scraper tools (NoCodeExport, SitedIn.io, NoCodeXport) work by crawling the *published* rendered output the same way this scrape did, and they inherit the same fundamental limitations:
- Velo/custom code (server functions, dynamic API calls) doesn't transfer — only the DOM output of one request does.
- Wix Forms, Wix Stores, Bookings, Members-Area login systems don't transfer — they're backed by Wix's own APIs.
- Wix's image CDN URLs (`static.wixstatic.com/media/...`) are not guaranteed permanent once a site is unpublished/deleted from Wix, so **assets must be re-hosted, not linked**.

This site is a good match for that pattern in the simple cases (home, research, stories, contact — plain content) but has three features that don't survive a naive HTML dump:

1. **The password gate** — a Wix "Members Area"-style protected page. In a static rebuild this needs a real (if lightweight) auth mechanism; it cannot be reproduced as static files without exposing the gated content publicly.
2. **The FAQ accordion widget** (`faq-ooi`, `_api/faq-server/v2/...`) — content isn't in the initial page HTML; it loads per-question, per-tab, on click. This was solved for scraping via genuine simulated clicks, but a rebuilt site needs the 128 Q&A pairs re-authored as static markup + a plain CSS/JS accordion (no Wix backend call).
3. **Google Forms embeds** — 9 monitoring/application forms are just `forms.gle` links, not truly part of the site; they survive untouched in any rebuild (external, already static-friendly).

## 3. Recommended rebuild architecture

**Static site generator: Astro** (or 11ty — either works; Astro chosen for component reuse across the repeated "resource card" / "FAQ accordion" / "post teaser" patterns seen in the captures).

```
site/
  src/
    layouts/BaseLayout.astro       # nav, footer, EN/ID toggle
    pages/
      index.astro                 # Home
      research.astro
      faq.astro                   # general FAQ (public)
      stories/index.astro         # blog listing
      stories/[slug].astro        # ~50 posts, generated from content collection
      resources.astro             # public Downloads
      contact.astro
      grants.astro
      research/
        index.astro                # gated FAQ landing (password check)
        faq.astro                  # 21-tab accordion, static content from faq-all-merged.json
        resources.astro            # member resources
        monitoring.astro           # monitoring tools + Google Form links
    components/
      Accordion.astro              # plain JS accordion, replaces faq-ooi widget
      ResourceCard.astro
      PostTeaser.astro
    content/
      posts/*.md                   # blog content, migrated from post-*.json
      faq/*.json                   # from faq-all-merged.json, one file per category
  public/
    assets/images/...              # from circles-scrape/assets/images (re-optimize/resize at build time)
    assets/pdfs/...                # from circles-scrape/assets/pdfs
```

### Handling the password gate
Since this is pre-existing "research participant" content, not something needing bank-grade security, the simplest faithful rebuild is:
- Client-side gate: a static page with a password field; on correct entry, set a signed cookie/localStorage flag and reveal the gated routes (still technically fetchable by a determined user, same as today's Wix gate — Wix's own protection is equivalently soft, so this doesn't reduce actual security).
- If real access control matters going forward, put the gated pages behind Cloudflare Access / a Netlify/Vercel Edge Function checking a shared password, or a small serverless function — still deployable to a CDN, with only the auth check running at the edge.

### Handling the FAQ accordion
Straightforward — `faq-all-merged.json` (already produced in this scrape) has all 21 categories × 128 Q&A pairs as clean `{q, a}` data. Render with any accordion component (native `<details>/<summary>` is the simplest zero-JS option and fully matches the single-expand-at-a-time semantics observed).

### Handling images
- Re-host all 112 canonical originals from `assets/images/` under the new domain/CDN — do not link back to `static.wixstatic.com`.
- Re-generate responsive variants at build time (Astro's `<Image>` / `astro:assets`) rather than keeping Wix's ad hoc `w_/h_/q_/enc_avif` query-param variants.

### Handling PDFs
Copy `assets/pdfs/` as-is into `public/assets/pdfs/` — links already resolve to `/_files/ugd/<id>.pdf`-style paths; rewrite to a clean `/resources/<slug>.pdf` naming scheme when migrating link references in the content.

### Handling Google Forms
No action needed — these are already external, static-compatible links (`forms.gle/...`). Keep as-is (9 forms cataloged in `asset-manifest.json`).

### Multilingual (EN/ID)
The site already segregates most download/resource copy into English and "Bahasa Indonesia" variants inline (not full i18n routing — no `/id/` path prefix observed). Simplest match: keep the same inline dual-language pattern per content block rather than introducing full i18n framework routing, unless a cleaner `/id/` structure is explicitly desired for the rebuild.

## 4. Remaining scrape gaps for a 100%-complete migration

**Closed:** all 27 blog posts (the full archive per `blog-posts-sitemap.xml` — fewer than the ~50 originally estimated) are now captured in `html/posts/*.json`, and the asset manifest/downloads were refreshed accordingly: 251 canonical images (up from 112) and the same 26 PDFs, all present in `assets/`.

**Closed:** the Indonesian-language mirror (33 pages under `html/id/`, mapped from English originals via Wix's `hreflang="id-id"` tags) and the 3 password-gated pages (now built into `site/` behind a client-side gate) are captured and deployed — see §0.

**Still open:**
- Embedded video (home page "An Urban & Rural Experience in Bali") and the YouTube/pro-gallery-video iframe on `/grants` and in some post pages are external embeds (YouTube) — no re-hosting needed, just re-embed the same iframe src.
- 17 images required a longer-timeout retry to fetch (transient, not content-related) — already resolved, all 251 present on disk.

## 5. Effort estimate
- Content migration (Astro pages/components + copy): 2–3 days for one developer, given content is already fully extracted here.
- Full blog archive walk (~50 posts): a few hours of scripted navigation, same pattern as this session.
- Styling to match current Wix visual design: 1–2 days (colors/fonts/layout can be read directly off the captured DOM's computed styles or screenshots if pixel fidelity matters).
- Auth gate + deployment (Cloudflare Pages/Netlify/Vercel): half a day.

**Total: roughly 1 developer-week for a faithful static rebuild**, versus an indefinite ongoing Wix subscription with the current export/scrape limitations.
