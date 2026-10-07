"""QA for the website in docs/. Exits 1 on any problem.

Static checks, every HTML file (fast, no browser):
  title 50-60 and description 140-160 characters (404 exempt), unique titles and descriptions, one <h1>; a Content-Security-Policy
  <meta> before any inline block whose hashes match exactly this page's inline <script>/<style> blocks; the referrer <meta>; no
  inline style or event attributes, no HTML comments; JSON-LD that parses, has no raw "<", and no ratings or reviews; no data:
  favicon; only http(s), mailto, tel (digits and +) or same-site links, and every same-site link and #anchor resolves; no
  "all/every" overclaims; each page type is there (guides, Lent, cities hub, cities, regions, place pages, about); place pages have
  Restaurant markup with geo and a #p= link that the web app can open; 404 has no canonical or og:url; sitemap and files agree.

Browser checks (headless Chrome via Python Playwright, 375 and 1280 px wide), every sitemap page (place pages: all at 375 px):
  no sideways scroll, one <h1>, no console errors, no Content-Security-Policy violations, no broken images; at 375 px, every visible
  link, button, input and select is at least 44x44 px (a link inside a sentence is exempt, as in WCAG 2.5.8).

The web app (explore/): loads; searches; opens a place as a modal dialog with the rest of the page inert and focus on Close, and
  closes on Escape with focus back on the row; detail.json waits for the first open; a saved place survives a reload; #g=constructor,
  #g=__proto__ and a junk stored guide don't break it; #p= links from place pages open the right place; Near me sorts by distance;
  the map draws; a failed core.json shows an error whose retry works; CLS stays under 0.05; tap targets with the panel open; and its
  key controls keep 4.5:1 text contrast in light and dark mode.

Usage: .venv/bin/python scripts/qa-site.py [--docs DIR] [--sample N] [--workers N]
  --docs    check another copy of the site (used to prove each check can fail)
  --sample  browser-check only N place pages (static checks still cover all of them); by default every place page
            is loaded at 375 px and every tenth at 1280 px, since they share one template
  --workers browsers to run side by side (default 3)
"""
import argparse
import base64
import functools
import hashlib
import html
import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ap = argparse.ArgumentParser()
ap.add_argument("--docs", default=os.path.join(ROOT, "docs"))
ap.add_argument("--sample", type=int, default=0)
ap.add_argument("--workers", type=int, default=3)
ARGS = ap.parse_args()
DOCS = os.path.abspath(ARGS.docs)
DOMAIN = open(os.path.join(DOCS, "CNAME")).read().strip()
problems = []


def bad(msg):
    problems.append(msg)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=DOCS))
    srv.handle_error = lambda *a: None     # a browser dropping a connection mid-file isn't a site problem
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def file_for(path):
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0]).lstrip("/")
    f = os.path.join(DOCS, path)
    if os.path.isdir(f):
        f = os.path.join(f, "index.html")
    return f if os.path.isfile(f) else None


def html_files():
    out = []
    for d, _, fs in os.walk(DOCS):
        out += [os.path.relpath(os.path.join(d, f), DOCS) for f in fs if f.endswith(".html")]
    return sorted(out)


# ---------------------------------------------------------------- static checks
SHA = lambda s: "sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
BANNED_LD = {"aggregateRating", "review", "reviews", "reviewRating", "ratingValue", "reviewCount", "bestRating"}
OVERCLAIMS = [r"every wisconsin restaurant", r"every restaurant", r"\ball the restaurants?\b", r"\bsearch all\b", r"\bhas all\b",
              r"\ball \d[\d,]* (wisconsin )?(restaurants|fish fries|supper clubs|custard)"]
_ids = {}


def ids_in(f):
    if f not in _ids:
        _ids[f] = set(re.findall(r'\sid="([^"]+)"', open(f).read()))
    return _ids[f]


def walk_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_keys(v)


def static_checks(core_ids):
    titles, descs = {}, {}
    files = html_files()
    for rel in files:
        s = open(os.path.join(DOCS, rel)).read()
        where = rel
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        d = re.search(r'<meta name="description" content="([^"]*)"', s)
        title, desc = html.unescape(t.group(1)) if t else "", html.unescape(d.group(1)) if d else ""
        if rel != "404.html":
            if not 50 <= len(title) <= 60:
                bad(f"{where}: title is {len(title)} characters: {title}")
            if not 140 <= len(desc) <= 160:
                bad(f"{where}: description is {len(desc)} characters")
            if title in titles:
                bad(f"{where}: same title as {titles[title]}")
            if desc in descs:
                bad(f"{where}: same description as {descs[desc]}")
            titles[title], descs[desc] = rel, rel
        else:
            if 'rel="canonical"' in s or 'property="og:url"' in s:
                bad("404.html: has a canonical or og:url")
            if 'href="/explore/"' not in s:
                bad("404.html: no search link")
        if len(re.findall(r"<h1[\s>]", s)) != 1:
            bad(f"{where}: {len(re.findall(r'<h1[\\s>]', s))} <h1>")
        # Content-Security-Policy: present, first, and hashes that match exactly
        m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', s)
        if not m:
            bad(f"{where}: no Content-Security-Policy meta")
        else:
            csp = dict((p.split(" ", 1) + [""])[:2] for p in (x.strip() for x in m.group(1).split(";")) if p)
            first_inline = min([i for i in (s.find("<style>"), s.find("<script>")) if i >= 0] or [len(s)])
            if m.start() > first_inline:
                bad(f"{where}: the CSP meta comes after an inline block, so it doesn't cover it")
            want = {"default-src": "'self'", "img-src": "'self' data:", "connect-src": "'self'", "object-src": "'none'", "base-uri": "'none'", "form-action": "'none'"}
            for k, v in want.items():
                if csp.get(k) != v:
                    bad(f"{where}: CSP {k} is {csp.get(k)!r}, want {v!r}")
            for kind, blocks in (("script-src", re.findall(r"<script>(.*?)</script>", s, re.S)), ("style-src", re.findall(r"<style>(.*?)</style>", s, re.S))):
                have = set(re.findall(r"'(sha256-[^']+)'", csp.get(kind, "")))
                need = {SHA(b) for b in blocks}
                if have != need or "unsafe" in csp.get(kind, ""):
                    bad(f"{where}: CSP {kind} hashes don't match the page's inline blocks")
        if '<meta name="referrer" content="strict-origin-when-cross-origin">' not in s:
            bad(f"{where}: no referrer meta")
        if re.search(r"<[a-zA-Z][^>]*\sstyle=", s):
            bad(f"{where}: inline style attribute (blocked by the CSP)")
        if re.search(r"<[a-zA-Z][^>]*\son[a-z]+=", s):
            bad(f"{where}: inline event handler (blocked by the CSP)")
        if "<!--" in s:
            bad(f"{where}: HTML comment left in the output")
        if re.search(r'<link[^>]+rel="icon"[^>]+href="data:', s):
            bad(f"{where}: data: favicon")
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
            if "<" in raw:
                bad(f"{where}: raw '<' inside JSON-LD")
            try:
                obj = json.loads(raw)
            except ValueError as e:
                bad(f"{where}: bad JSON-LD ({e})")
                continue
            hit = BANNED_LD & set(walk_keys(obj))
            if hit:
                bad(f"{where}: ratings or reviews in JSON-LD: {sorted(hit)}")
        text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S)).lower()
        for rx in OVERCLAIMS:
            if re.search(rx, html.unescape(text)):
                bad(f"{where}: overclaim matching {rx!r}")
        markup = re.sub(r"<script>.*?</script>", "", s, flags=re.S)     # links built inside the web app's script are checked in the browser
        for tag, ref in re.findall(r'<(a|img|link|source|script)\b[^>]*?\s(?:href|src|srcset)="([^"]*)"', markup):
            ref = html.unescape(ref)
            scheme = urllib.parse.urlsplit(ref).scheme.lower()
            if scheme in ("http", "https"):
                if tag == "a" and urllib.parse.urlsplit(ref).netloc == DOMAIN:
                    bad(f"{where}: absolute link to our own site {ref}")
                continue
            if scheme == "mailto":
                continue
            if scheme == "tel":
                if not re.fullmatch(r"tel:\+?\d{10,15}", ref):
                    bad(f"{where}: bad tel: link {ref}")
                continue
            if scheme:
                bad(f"{where}: link with scheme {scheme}: {ref[:60]}")
                continue
            target = urllib.parse.urljoin("/" + rel, ref)
            path, _, frag = target.partition("#")
            f = file_for(path) if path else os.path.join(DOCS, rel)
            if not f:
                bad(f"{where}: broken link {ref}")
            elif frag and f.endswith(".html") and not path.startswith("/explore") and frag not in ids_in(f):
                bad(f"{where}: link to a missing anchor {ref}")
    return files


def page_type_checks(files, core_ids, sitemap_paths):
    need = ["index.html", "wisconsin-fish-fry.html", "wisconsin-supper-clubs.html", "wisconsin-frozen-custard.html", "wisconsin-lent-fish-fry.html",
            "cities/index.html", "about.html", "privacy.html", "terms.html", "explore/index.html", "404.html",
            "regions/northwoods.html", "regions/western-wisconsin.html", "regions/central-wisconsin.html", "regions/door-county.html"]
    for n in need:
        if n not in files:
            bad(f"missing page {n}")
    places = [f for f in files if f.startswith("places/")]
    cities = [f for f in files if f.startswith("cities/") and f != "cities/index.html"]
    if len(places) < 100:
        bad(f"only {len(places)} place pages")
    if len(cities) < 10:
        bad(f"only {len(cities)} city pages")
    hub = open(os.path.join(DOCS, "cities/index.html")).read() if "cities/index.html" in files else ""
    for c in cities:
        if f'href="/{c}"' not in hub:
            bad(f"cities hub doesn't link {c}")
    for f in places:
        s = open(os.path.join(DOCS, f)).read()
        lds = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)]
        r = [x for x in lds if x.get("@type") == "Restaurant"]
        if not r or not r[0].get("name") or not r[0].get("address", {}).get("streetAddress") or not r[0].get("geo", {}).get("latitude"):
            bad(f"{f}: no Restaurant JSON-LD with name, address and geo")
        m = re.search(r'href="/explore/#p=([0-9a-f]+)"', s)
        if not m or m.group(1) not in core_ids:
            bad(f"{f}: no #p= link the web app can open")
        if "Checked open in" not in s:
            bad(f"{f}: no hand-check note")
        if "/" + f not in sitemap_paths:
            bad(f"{f}: not in the sitemap")
    # guides link to place pages and anchor each place
    for g in ("wisconsin-fish-fry.html", "wisconsin-supper-clubs.html", "wisconsin-frozen-custard.html"):
        s = open(os.path.join(DOCS, g)).read()
        lis = re.findall(r'<li id="([^"]+)"><h3><a href="/places/\1\.html">', s)
        if len(lis) < 10:
            bad(f"{g}: places aren't anchored and linked to their pages")
    # every web-app place id is unique
    if len(core_ids) != len(set(core_ids)):
        bad("core.json has duplicate place ids")


def sitemap_checks(files):
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.parse(os.path.join(DOCS, "sitemap.xml")).getroot()
    locs, paths = [], set()
    for u in root.findall("s:url", ns):
        loc, lastmod = u.find("s:loc", ns).text, u.find("s:lastmod", ns)
        if lastmod is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod.text or ""):
            bad(f"sitemap: {loc} has no valid lastmod")
        p = urllib.parse.urlparse(loc)
        if p.netloc != DOMAIN:
            bad(f"sitemap: {loc} isn't on {DOMAIN}")
        f = file_for(p.path)
        if not f:
            bad(f"sitemap: {loc} has no file")
        else:
            paths.add("/" + os.path.relpath(f, DOCS))
        locs.append(loc)
    if len(locs) != len(set(locs)):
        bad("sitemap: duplicate URLs")
    for f in files:
        if f != "404.html" and "/" + f not in paths:
            bad(f"sitemap: {f} exists but isn't in the sitemap")
    return locs, paths


# ---------------------------------------------------------------- browser checks
INIT = """
window.__csp = [];
document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(e.violatedDirective + ' ' + (e.blockedURI || 'inline')));
window.__cls = 0;
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
"""
TAP = """(scope) => {
  const out = [];
  const root = scope ? document.querySelector(scope) : document;
  const blockOf = (el) => { let n = el.parentElement; while (n && getComputedStyle(n).display.startsWith('inline')) n = n.parentElement; return n; };
  for (const el of root.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary')) {
    let t = el;
    if (el.matches('input[type=checkbox], input[type=radio]') && el.closest('label')) t = el.closest('label');
    if (t.closest('[hidden], [inert]') && !scope) continue;
    const cs = getComputedStyle(t);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = t.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right + scrollX <= 0 || r.bottom + scrollY <= 0) continue;   // not rendered, or the off-screen skip link
    if (t.tagName === 'A' && cs.display === 'inline') {     // a link inside a sentence is exempt (WCAG 2.5.8)
      const b = blockOf(t), own = t.textContent.replace(/\\s+/g, ' ').trim(), all = (b ? b.textContent : '').replace(/\\s+/g, ' ').trim();
      if (all.length > own.length + 2) continue;
    }
    if (r.width < 43.5 || r.height < 43.5) out.push(`${t.tagName.toLowerCase()}${t.id ? '#' + t.id : ''}${t.className && typeof t.className === 'string' ? '.' + t.className.split(' ')[0] : ''} "${(t.textContent || t.getAttribute('aria-label') || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  return out;
}"""
CONTRAST = """(scope) => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const bgOf = (el) => {
    const layers = [];
    for (let n = el; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let base = parse(getComputedStyle(document.body).backgroundColor) || [255, 255, 255, 1];
    if (layers.length && layers[layers.length - 1][3] >= 1) base = layers.pop();
    for (const c of layers.reverse()) base = [0, 1, 2].map((i) => c[i] * c[3] + base[i] * (1 - c[3])).concat(1);
    return base;
  };
  const out = [];
  for (const root of document.querySelectorAll(scope)) {
    for (const el of [root, ...root.querySelectorAll('*')]) {
      if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      if (el.closest('[hidden], .vh, option') || el.disabled || el.closest(':disabled')) continue;
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      if (!r.width || !r.height || cs.visibility === 'hidden') continue;
      const fg = parse(cs.color), bg = bgOf(el);
      if (!fg) continue;
      const a = lum(fg), b = lum(bg), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (ratio < 4.5) out.push(`${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ')[0]} "${el.textContent.trim().slice(0, 24)}" ${ratio.toFixed(2)}:1`);
    }
  }
  return out;
}"""


def goto(page, url, until="load"):
    """Navigate, once more with a longer wait if the machine is busy; None if the page never loaded."""
    for timeout in (30000, 90000):
        try:
            return page.goto(url, wait_until=until, timeout=timeout)
        except Exception as e:
            err = e
    bad(f"{urllib.parse.urlparse(url).path}: didn't load ({str(err).splitlines()[0][:80]})")
    return None


def fresh(page, url):
    """A real page load, even when only the #hash differs from the current URL (which would just fire hashchange)."""
    page.goto("about:blank")
    return goto(page, url, "networkidle")


def page_worker(base, jobs):
    """One Playwright instance per thread (its API isn't thread-safe); jobs are (path, width)."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        pages = {}
        errors = []
        for width in (375, 1280):
            ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 900})
            ctx.add_init_script(INIT)
            pg = ctx.new_page()
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pages[width] = pg
        for path, width in jobs:
            page = pages[width]
            errors.clear()
            if not goto(page, base + path, "networkidle" if path.startswith("/explore") else "load"):
                continue
            if path.startswith("/explore"):
                page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
            where = f"{path} @{width}"
            over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if over > 1:
                bad(f"{where}: scrolls sideways by {over}px")
            if page.locator("h1").count() != 1:
                bad(f"{where}: {page.locator('h1').count()} <h1>")
            for v in page.evaluate("window.__csp"):
                bad(f"{where}: CSP violation: {v}")
            if width == 375:
                for t in page.evaluate(TAP, None):
                    bad(f"{where}: tap target under 44px: {t}")
            else:
                imgs = page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.currentSrc || i.src)")
                imgs = [u for u in imgs if not page.request.get(u).ok]    # a second try, so a dropped local connection isn't a broken image
                problems.extend(f"{where}: image didn't load {u}" for u in imgs)
                errors[:] = [x for x in errors if "ERR_CONNECTION_RESET" not in x or imgs]
            problems.extend(f"{where}: console error: {e}" for e in errors)
        browser.close()


def browser_checks(base, locs, place_samples, workers):
    jobs = []
    for loc in locs:
        path = urllib.parse.urlparse(loc).path
        for width in (375, 1280):
            if path.startswith("/places/") and path not in place_samples and (ARGS.sample or width == 1280):
                continue    # place pages share one template: all of them at 375 px, a sample at 1280 px
            jobs.append((path, width))
    chunks = [jobs[i::workers] for i in range(workers)]
    threads = [threading.Thread(target=page_worker, args=(base, c)) for c in chunks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        webapp_checks(browser, base)
        browser.close()
    return len(jobs)


def slow_core(page):
    """Hold core.json back a little, so the page paints before the list arrives (the case where layout used to jump)."""
    page.route("**/data/core.json", lambda r: (time.sleep(0.6), r.continue_()))


def webapp_checks(browser, base):
    places = sorted(f for f in html_files() if f.startswith("places/"))
    picks = [places[0], places[len(places) // 2], places[-1]] if places else []
    for width in (375, 1280):
        ctx = browser.new_context(viewport={"width": width, "height": 812 if width < 600 else 720}, geolocation={"latitude": 43.0389, "longitude": -87.9065},
                                  permissions=["geolocation"])
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        errors, requests = [], []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: requests.append(r.url))
        slow_core(page)
        w = f"explore @{width}"
        goto(page, base + "/explore/", "networkidle")
        page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
        page.wait_for_timeout(1200)
        cls = page.evaluate("window.__cls")
        if cls >= 0.05:
            bad(f"{w}: layout shift (CLS) {cls:.3f} on load")
        if any(u.endswith("/data/detail.json") for u in requests):
            bad(f"{w}: detail.json loaded before any place was opened")
        if width == 375:
            for t in page.evaluate(TAP, None):
                bad(f"{w}: tap target under 44px: {t}")
        search = page.locator("#ex-q")
        search.fill("perch green bay")
        page.wait_for_timeout(400)
        if not page.locator(".ex-row").count():
            bad(f"{w}: search 'perch green bay' found nothing")
        else:
            page.locator(".ex-row").first.click()
            page.wait_for_function("() => document.querySelector('#ex-panel .ex-act-row a')", timeout=30000)
            page.wait_for_timeout(500)
            panel = page.locator("#ex-panel")
            if not panel.is_visible() or not panel.locator("a", has_text="Directions").count():
                bad(f"{w}: opening a place showed no details")
            st = page.evaluate("""() => ({ role: document.querySelector('#ex-panel').getAttribute('role'), modal: document.querySelector('#ex-panel').getAttribute('aria-modal'),
                label: document.getElementById(document.querySelector('#ex-panel').getAttribute('aria-labelledby'))?.textContent || '',
                inert: document.querySelector('.wrap').inert, focus: document.activeElement?.id })""")
            if st["role"] != "dialog" or st["modal"] != "true" or not st["label"] or not st["inert"] or st["focus"] != "ex-close":
                bad(f"{w}: place panel isn't a labelled modal dialog with the page inert and focus on Close: {st}")
            if not any(u.endswith("/data/detail.json") for u in requests):
                bad(f"{w}: opening a place didn't load detail.json")
            if width == 375:
                for t in page.evaluate(TAP, "#ex-panel"):
                    bad(f"{w} (panel open): tap target under 44px: {t}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            st = page.evaluate("({ hidden: document.querySelector('#ex-panel').hidden, inert: document.querySelector('.wrap').inert, row: document.activeElement?.classList.contains('ex-row') })")
            if not st["hidden"] or st["inert"] or not st["row"]:
                bad(f"{w}: Escape didn't close the panel, restore the page and return focus to the row: {st}")
        search.fill("🍕")
        page.wait_for_timeout(400)
        if page.locator(".ex-row").count():
            bad(f"{w}: an emoji search listed places")
        search.fill("")
        page.wait_for_timeout(300)
        # Near me (geolocation under the CSP)
        page.locator("#ex-locate").click()
        page.wait_for_timeout(800)
        if "away" not in (page.locator(".ex-row").first.text_content() or ""):
            bad(f"{w}: Near me didn't sort by distance")
        # the map draws (canvas pixels)
        page.locator('.ex-view button[data-v="map"]').click()
        page.wait_for_timeout(1200)
        painted = page.evaluate("""() => { const c = document.querySelector('#ex-map'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let n = 0; for (let i = 3; i < d.length; i += 4 * 7) if (d[i]) n++; return n; }""")
        if painted < 500:
            bad(f"{w}: the map didn't draw")
        page.locator('.ex-view button[data-v="list"]').click()
        # save survives a reload (localStorage)
        page.locator(".ex-row").first.click()
        page.wait_for_selector("#ex-save")
        name = page.locator("#ex-pname").text_content()
        page.locator("#ex-save").click()
        page.keyboard.press("Escape")
        fresh(page, base + "/explore/#g=saved")
        page.wait_for_function("() => document.querySelector('.ex-row, .ex-empty')", timeout=60000)
        if name not in (page.locator("#ex-list").text_content() or ""):
            bad(f"{w}: a saved place wasn't in Saved after a reload")
        # hostile hash and stored guide
        for h in ("#g=constructor", "#g=__proto__", "#g=toString&sort=__proto__&town=constructor"):
            errors.clear()
            fresh(page, base + "/explore/" + h)
            page.wait_for_timeout(300)
            if errors or not re.match(r"[\d,]+ places? ·", page.locator("#ex-count").text_content() or ""):
                bad(f"{w}: {h} broke the web app: {errors[:2]}")
        page.evaluate("localStorage.setItem('we-guide', JSON.stringify('__proto__'))")
        errors.clear()
        fresh(page, base + "/explore/")
        page.wait_for_timeout(300)
        if errors or not page.locator(".ex-row").count():
            bad(f"{w}: a junk stored guide broke the web app: {errors[:2]}")
        errors.clear()
        page.evaluate("location.hash = 'g=__proto__&p=constructor'")     # the hashchange path too
        page.wait_for_timeout(300)
        if errors:
            bad(f"{w}: a hostile hash change broke the web app: {errors[:2]}")
        # #p= links from place pages open the right place
        for f in picks:
            s = open(os.path.join(DOCS, f)).read()
            pid = re.search(r'href="/explore/#p=([0-9a-f]+)"', s).group(1)
            want = html.unescape(re.search(r"<h1>(.*?)</h1>", s).group(1))
            fresh(page, base + f"/explore/#p={pid}")
            page.wait_for_timeout(500)
            got = page.locator("#ex-pname").text_content() if page.locator("#ex-pname").count() else ""
            if got != want:
                bad(f"{w}: #p= from {f} opened {got!r}, want {want!r}")
        for v in page.evaluate("window.__csp"):
            bad(f"{w}: CSP violation: {v}")
        problems.extend(f"{w}: console error: {e}" for e in errors)
        ctx.close()
    # CLS at a short desktop window too, where the footer used to jump into view
    for vw, vh in ((1280, 720), (1440, 900), (768, 1024)):
        ctx = browser.new_context(viewport={"width": vw, "height": vh})
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        slow_core(page)
        goto(page, base + "/explore/", "networkidle")
        page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
        page.wait_for_timeout(1000)
        if page.evaluate("window.__cls") >= 0.05:
            bad(f"explore @{vw}x{vh}: CLS {page.evaluate('window.__cls'):.3f}")
        ctx.close()
    # a failed core.json: the error shows in #ex-loading, and retry works
    ctx = browser.new_context(viewport={"width": 375, "height": 812})
    page = ctx.new_page()
    page.route("**/data/core.json", lambda r: r.abort())
    goto(page, base + "/explore/", "networkidle")
    page.wait_for_timeout(500)
    msg = page.locator("#ex-loading").text_content() or ""
    if "couldn" not in msg or not page.locator("#ex-loading #ex-retry").count():
        bad(f"explore: a failed core.json didn't show an error with a retry ({msg!r})")
    else:
        page.unroute("**/data/core.json")
        page.locator("#ex-retry").click()
        try:
            page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
        except Exception:
            bad("explore: retry after a failed core.json didn't load the list")
    ctx.close()
    # contrast of the web app's key controls (and a few site pages), light and dark
    for scheme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 375, "height": 812}, color_scheme=scheme)
        page = ctx.new_page()
        for url, scope in (("/explore/#g=icons", "header.site, .ex-controls, #ex-list"), ("/explore/#g=inspections", ".ex-controls, #ex-list"),
                           ("/", "header.site, main, footer"), ("/wisconsin-fish-fry.html", "main"), ("/" + (picks[0] if picks else ""), "main")):
            goto(page, base + url, "networkidle")
            if url.startswith("/explore"):
                page.wait_for_function("() => document.querySelectorAll('.ex-row').length > 0", timeout=60000)
            for t in page.evaluate(CONTRAST, scope):
                bad(f"{url} ({scheme}): text contrast under 4.5:1: {t}")
            if url == "/explore/#g=icons":
                page.locator('.ex-view button[data-v="map"]').click()
                page.wait_for_timeout(300)
                for t in page.evaluate(CONTRAST, ".ex-view, #ex-maphint, .ex-zoom"):
                    bad(f"{url} map ({scheme}): text contrast under 4.5:1: {t}")
                page.locator('.ex-view button[data-v="list"]').click()
                page.locator(".ex-row").first.click()
                page.wait_for_function("() => document.querySelector('#ex-panel .ex-sec')", timeout=30000)
                page.locator("#ex-save").click()     # the pressed Save state
                page.wait_for_timeout(300)
                for t in page.evaluate(CONTRAST, "#ex-panel"):
                    bad(f"{url} panel ({scheme}): text contrast under 4.5:1: {t}")
        ctx.close()


def main():
    base = serve()
    core = json.load(open(os.path.join(DOCS, "data/core.json")))
    core_ids = core["cols"]["id"]
    files = static_checks(set(core_ids))
    locs, paths = sitemap_checks(files)
    page_type_checks(files, core_ids, paths)
    places = sorted(urllib.parse.urlparse(u).path for u in locs if "/places/" in u)
    every = max(1, len(places) // ARGS.sample) if ARGS.sample else 10
    samples = set(places[::every])
    n_static = len(problems)
    n_jobs = browser_checks(base, locs, samples, ARGS.workers)
    print(f"static: {len(files)} HTML files, {n_static} problems | browser: {n_jobs} page loads at 375 and 1280 px, plus the web app")
    for p in problems:
        print("  ✗", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
