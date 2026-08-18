GATE_HASH = "ae1dfecd103193d987852eb153841bb0dcad3f2f14b4a11f3cb39cffb30b0b3d"

# Gate chrome copy per language. The Indonesian wording mirrors the live Wix
# gate on /id/* ("Area Tamu" / "Masukkan kata sandi di bawah." / "Ayo") so the
# mirror's gate reads the same as the site it mirrors.
STRINGS = {
    "en": {
        "heading": "Password protected",
        "blurb": "This section of circlesubi.id requires a password to view.",
        "placeholder": "Password",
        "submit": "Unlock",
        "wrong": "Incorrect password.",
        "loading": "Loading...",
        "failed": "Failed to load content. Please try again.",
    },
    "id": {
        "heading": "Area Tamu",
        "blurb": "Bagian circlesubi.id ini memerlukan kata sandi untuk dilihat.",
        "placeholder": "Kata Sandi",
        "submit": "Ayo",
        "wrong": "Kata sandi salah.",
        "loading": "Memuat...",
        "failed": "Gagal memuat konten. Silakan coba lagi.",
    },
}


def gate_html(title, lang="en"):
    s = STRINGS[lang]
    heading = s["heading"]
    blurb = s["blurb"]
    placeholder = s["placeholder"]
    submit = s["submit"]
    wrong = s["wrong"]
    loading = s["loading"]
    failed = s["failed"]
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Circles</title>
<style>
  html,body{{height:100%;margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:#0b1f1a;color:#fff;display:flex;align-items:center;justify-content:center}}
  .gate{{max-width:380px;width:90%;text-align:center;padding:2rem}}
  .gate h1{{font-size:1.3rem;margin-bottom:.5rem}}
  .gate p{{opacity:.75;font-size:.9rem;margin-bottom:1.5rem}}
  .gate input{{width:100%;box-sizing:border-box;padding:.75rem 1rem;border-radius:8px;border:1px solid #3a5c50;background:#12332b;color:#fff;font-size:1rem;margin-bottom:1rem}}
  .gate button{{width:100%;padding:.75rem 1rem;border-radius:8px;border:none;background:#3ecf8e;color:#04241b;font-weight:600;font-size:1rem;cursor:pointer}}
  .gate button:hover{{background:#31b87b}}
  .gate .err{{color:#ff8a8a;font-size:.85rem;min-height:1.2em;margin-top:.75rem}}
  .gate .loading{{opacity:.6;font-size:.85rem;margin-top:.75rem}}
</style>
</head>
<body>
<div class="gate" id="gate-form">
  <h1>{heading}</h1>
  <p>{blurb}</p>
  <input type="password" id="gate-pw" placeholder="{placeholder}" autofocus>
  <button id="gate-submit">{submit}</button>
  <div class="err" id="gate-err"></div>
</div>
<script>
(function() {{
  var GATE_HASH = "{GATE_HASH}";
  var form = document.getElementById('gate-form');
  var pw = document.getElementById('gate-pw');
  var btn = document.getElementById('gate-submit');
  var err = document.getElementById('gate-err');

  async function sha256Hex(str) {{
    var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
    return Array.from(new Uint8Array(buf)).map(function(b) {{ return b.toString(16).padStart(2, '0'); }}).join('');
  }}

  async function attempt() {{
    var val = pw.value;
    if (!val) return;
    var hash = await sha256Hex(val);
    if (hash !== GATE_HASH) {{
      err.textContent = '{wrong}';
      pw.value = '';
      pw.focus();
      return;
    }}
    err.textContent = '';
    err.className = 'loading';
    err.textContent = '{loading}';
    try {{
      var file = screen.width <= 750 ? 'content-mobile.html' : 'content.html';
      location.replace(file);
    }} catch (e) {{
      err.className = 'err';
      err.textContent = '{failed}';
    }}
  }}

  btn.addEventListener('click', attempt);
  pw.addEventListener('keydown', function(e) {{ if (e.key === 'Enter') attempt(); }});
}})();
</script>
</body>
</html>
"""
