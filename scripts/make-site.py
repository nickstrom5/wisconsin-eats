"""Writes the public website in docs/ from the same data file the app ships (data/app/places.json).

Pages: the landing page, three statewide guides (fish fry, supper clubs, frozen custard), one page per big city,
privacy, terms, 404, plus sitemap.xml, robots.txt and site.webmanifest. Everything listed is hand-checked research
or licensed open data; nothing comes from Google, Yelp or any ratings site, and nothing is ranked by ratings.

Usage (from the repo root): .venv/bin/python scripts/make-site.py
Re-run it after every data rebuild, then check the pages (see CLAUDE.md, "Site").
"""
import html
import json
import math
import os
import re
import struct
from collections import Counter, defaultdict

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = f"{ROOT}/docs"
DOMAIN = "https://wisconsineats.com"
BRAND = "Wisconsin Eats"
TAGLINE = "Fish fry & supper club guide"
EMAIL = "work-with-nick@gmail.com"
TODAY = "2026-09-26"
CHECKED = "September 2026"

D = json.load(open(f"{ROOT}/data/app/places.json"))
CITIES, CUISINES = D["cities"], D["cuisines"]
SUPPER, FISHFRY, CURDS, CUSTARD, BOIL = 1, 2, 4, 8, 16


class P:
    """One place, with the same meaning the app gives each field (WisconsinEats/Models/Place.swift)."""

    def __init__(self, r):
        self.r = r
        self.name = r["n"]
        self.city = CITIES[r["c"]] if r.get("c") is not None else ""
        self.cuisine = CUISINES[r["cu"]]["name"] if isinstance(CUISINES[0], dict) and r.get("cu") is not None else (CUISINES[r["cu"]] if r.get("cu") is not None else "")
        self.addr = r.get("a") or ""
        self.zip = r.get("z") or ""
        self.lat, self.lon = r.get("la"), r.get("lo")
        self.tags = r.get("g") or 0
        self.chain = (r.get("ch") or 0) >= 5
        self.venue = r.get("v") == 1
        self.ip = r.get("ip")
        self.founded = r.get("f")
        self.fish = r.get("fish") or ""
        self.days = r.get("days") or ""
        self.sides = r.get("sides") or ""
        self.note = r.get("note") or r.get("icon") or ""
        self.icon = r.get("icon") or ""
        self.site = r.get("w") or ""
        self.honors = r.get("hon") or ""
        self.jbf = r.get("jbf") or ""
        self.hc = r.get("hc") == 1   # hand-checked open with a 2025-26 source; the only places the guides list

    def featured_key(self):
        # the app's "Featured first": honored places, then verified founding year, then name
        return (-(self.ip if self.ip is not None else -1), self.founded or 9999, self.name.lower())


PLACES = [P(r) for r in D["places"]]
REST = [p for p in PLACES if not p.venue]
FISH = sorted([p for p in REST if p.hc and p.tags & FISHFRY], key=P.featured_key)
SUP = sorted([p for p in REST if p.hc and p.tags & SUPPER], key=P.featured_key)
CUST = sorted([p for p in REST if p.hc and p.tags & CUSTARD and not p.chain], key=P.featured_key)
ICONS = [p for p in REST if p.ip is not None]

# ---------------------------------------------------------------- counties and regions
SHAPES = json.load(open(f"{ROOT}/data/wi/wi_shapes.json"))["counties"]
COUNTY = [(c["name"].replace(" County", "").replace("Saint Croix", "St. Croix"),
           prep(unary_union([Polygon(r) for r in c["c"] if len(r) >= 4]).buffer(0.005))) for c in SHAPES]
REGIONS = {
    "Milwaukee area": "Milwaukee Waukesha Ozaukee Washington",
    "Southeast Wisconsin": "Racine Kenosha Walworth Jefferson Rock Green",
    "Madison and south central": "Dane Columbia Sauk Iowa Lafayette Grant Richland Dodge Juneau Adams Marquette",
    "Door County and the lakeshore": "Door Kewaunee Manitowoc Sheboygan",
    "Green Bay and the Fox Valley": "Brown Outagamie Winnebago Calumet Fond_du_Lac Green_Lake Waupaca Waushara Shawano Oconto Menominee",
    "Central Wisconsin": "Marathon Portage Wood Lincoln Langlade Clark Taylor",
    "Northwoods and Lake Superior": "Oneida Vilas Forest Florence Marinette Iron Price Ashland Sawyer Bayfield Douglas Washburn Burnett",
    "Western Wisconsin": "Polk Barron Rusk St._Croix Pierce Dunn Chippewa Eau_Claire Pepin Buffalo Trempealeau Jackson Monroe La_Crosse Vernon Crawford",
}
REGION_OF = {c.replace("_", " "): r for r, cs in REGIONS.items() for c in cs.split()}
assert len(REGION_OF) == 72, len(REGION_OF)


def county(p):
    if p.lat is None:
        return None
    pt = Point(p.lon, p.lat)
    for name, g in COUNTY:
        if g.contains(pt):
            return name
    return None


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- html helpers
e = html.escape


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "")).strip("-")


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


APPLE = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M16.4 12.6c0-2.5 2-3.7 2.1-3.8-1.2-1.7-3-1.9-3.6-2-1.5-.2-3 .9-3.8.9-.8 0-2-.9-3.3-.9-1.7 0-3.3 1-4.1 2.5-1.8 3.1-.5 7.6 1.3 10.1.9 1.2 1.9 2.6 3.2 2.6 1.3-.1 1.8-.8 3.3-.8 1.6 0 2 .8 3.3.8 1.4 0 2.3-1.3 3.1-2.5 1-1.4 1.4-2.8 1.4-2.9 0 0-2.7-1-2.9-4zM14 5.2c.7-.8 1.2-2 1-3.2-1 0-2.2.7-2.9 1.5-.6.7-1.2 1.9-1.1 3.1 1.1.1 2.3-.6 3-1.4z"/></svg>'
LOGO = '<svg viewBox="0 0 64 64" width="30" height="30" aria-hidden="true"><rect width="64" height="64" rx="14" fill="#203731"/><path d="M10 34 H54 L23 19 Z" fill="#FFD45E"/><rect x="10" y="34" width="44" height="17" fill="#FFB612"/><circle cx="17.5" cy="42.5" r="3.7" fill="#203731"/><circle cx="30" cy="46" r="2.4" fill="#203731"/><circle cx="42.5" cy="41" r="4.3" fill="#203731"/><ellipse cx="31" cy="28.5" rx="2.6" ry="1.1" fill="#203731"/></svg>'
FAVICON = "data:image/svg+xml," + LOGO.replace('width="30" height="30" ', "").replace(' aria-hidden="true"', "").replace("<svg ", "<svg xmlns='http://www.w3.org/2000/svg' ").replace('"', "'").replace("#", "%23").replace("<", "%3C").replace(">", "%3E")

CSS = """
  :root {
    --bg: #fbfaf6; --surface: #fff; --surface2: #f3f1ea; --rule: #e3e0d6;
    --ink: #16211d; --ink2: #33443d; --muted: #53665b;
    --green: #203731; --green2: #2d5242; --gold: #ffb612; --goldsoft: #ffe7a8;
    --radius: 16px;
    --display: "Avenir Next Condensed", "HelveticaNeue-CondensedBold", "Arial Narrow", system-ui, sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #111815; --surface: #18221e; --surface2: #1f2b26; --rule: #2c3a34; --ink: #f2f1ea; --ink2: #d5d9d2; --muted: #a9b7ae; --green: #9fd3b8; --green2: #7fbf9f; }
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  @media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
  a { color: var(--green); text-underline-offset: 2px; }
  a:focus-visible, summary:focus-visible, button:focus-visible { outline: 3px solid var(--gold); outline-offset: 3px; border-radius: 6px; }
  .skip { position: absolute; left: -9999px; top: 0; background: var(--gold); color: #16211d; padding: 10px 14px; font-weight: 700; z-index: 10; }
  .skip:focus { left: 8px; top: 8px; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 20px; }
  header.site { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 0; border-bottom: 4px solid var(--gold); }
  .logo { display: flex; align-items: center; gap: 10px; font: 800 22px/1 var(--display); text-transform: uppercase; letter-spacing: .01em; color: var(--green); text-decoration: none; }
  header.site nav { display: flex; flex-wrap: wrap; gap: 4px 16px; justify-content: flex-end; }
  header.site nav a { color: var(--ink2); text-decoration: none; font-size: 15px; }
  header.site nav a:hover { color: var(--green); text-decoration: underline; }
  h1, h2 { font-family: var(--display); font-weight: 800; color: var(--green); letter-spacing: -.005em; }
  h1 { font-size: clamp(36px, 7.5vw, 56px); line-height: 1.02; margin: 0 0 16px; text-transform: uppercase; }
  h1 .kicker { display: block; font: 700 15px/1.4 -apple-system, system-ui, sans-serif; letter-spacing: .06em; color: var(--muted); margin-bottom: 12px; }
  h2 { font-size: 32px; line-height: 1.1; margin: 0 0 10px; }
  h3 { font-size: 18px; margin: 0; line-height: 1.3; }
  .lede { font-size: 19px; color: var(--ink2); margin: 0 0 26px; }
  .hero { padding: 44px 0 28px; }
  section { padding: 36px 0; border-top: 1px solid var(--rule); }
  section.hero { border: 0; }
  .sub { color: var(--ink2); margin: 0 0 22px; }
  .cta-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .btn { display: inline-flex; align-items: center; gap: 10px; background: var(--gold); color: #16211d; font-weight: 700; padding: 14px 20px; border-radius: 14px; text-decoration: none; font-size: 17px; }
  .btn svg { width: 22px; height: 22px; }
  .pill { font-size: 14px; color: var(--muted); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 28px 0 0; padding: 0; list-style: none; }
  .stats li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px; }
  .stats b { display: block; font: 800 30px/1 var(--display); color: var(--green); }
  .stats span { font-size: 14px; color: var(--muted); }
  .steps { display: grid; gap: 12px; list-style: none; margin: 0; padding: 0; }
  .step { display: flex; gap: 14px; background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .step .n { flex: 0 0 32px; height: 32px; border-radius: 50%; background: var(--gold); color: #16211d; font-weight: 800; display: grid; place-items: center; }
  .step p { margin: 4px 0 0; color: var(--ink2); }
  .shots { display: flex; gap: 14px; overflow-x: auto; margin: 0 -20px; padding: 4px 20px 14px; scroll-snap-type: x proximity; list-style: none; }
  .shots li { flex: 0 0 auto; width: 210px; scroll-snap-align: start; }
  .shots img { display: block; width: 210px; height: auto; border-radius: 24px; border: 1px solid var(--rule); background: var(--surface2); }
  .shots p { font-size: 14px; color: var(--muted); margin: 8px 2px 0; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .card { background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .card p { margin: 6px 0 0; color: var(--ink2); }
  a.card { display: block; text-decoration: none; color: var(--ink); }
  a.card:hover h3 { text-decoration: underline; color: var(--green); }
  .cities { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; margin: 0; }
  .cities a { display: inline-block; padding: 8px 12px; border-radius: 999px; border: 1px solid var(--rule); background: var(--surface); text-decoration: none; color: var(--ink); font-size: 15px; }
  .cities a:hover { border-color: var(--green); }
  details { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 2px 18px; margin-bottom: 10px; }
  summary { cursor: pointer; padding: 14px 0; font-weight: 600; list-style: none; display: flex; justify-content: space-between; gap: 12px; }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "+"; color: var(--green); font-weight: 800; }
  details[open] summary::after { content: "\\2013"; }
  details p { margin: 0 0 16px; color: var(--ink2); }
  .final { text-align: center; }
  .final .cta-row { justify-content: center; }
  nav.crumbs { font-size: 14px; color: var(--muted); padding: 16px 0 0; }
  nav.crumbs ol { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 6px; }
  nav.crumbs li + li::before { content: "/"; margin-right: 6px; color: var(--rule); }
  nav.crumbs a { color: var(--muted); }
  .places { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
  .places li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px 16px; min-width: 0; overflow-wrap: anywhere; }
  .places .where { margin: 2px 0 0; font-size: 15px; color: var(--muted); }
  .places .facts { margin: 8px 0 0; font-size: 15px; color: var(--ink2); }
  .places .facts b { color: var(--ink); font-weight: 600; }
  .places .note { margin: 6px 0 0; font-size: 15px; color: var(--ink2); }
  .places .link { font-size: 14px; }
  .tag { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; background: var(--goldsoft); color: #16211d; border-radius: 6px; padding: 1px 6px; margin-right: 4px; }
  .toc { columns: 2; padding-left: 20px; margin: 0; }
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--rule); }
  td.n { text-align: right; font-variant-numeric: tabular-nums; }
  .fine { font-size: 14px; color: var(--muted); }
  .legal h2 { font-size: 26px; margin-top: 28px; }
  .legal p, .legal li { color: var(--ink2); }
  footer { padding: 32px 0 56px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--rule); margin-top: 20px; }
  footer nav { display: flex; flex-wrap: wrap; gap: 8px 16px; }
  footer a { color: var(--muted); }
  footer p { margin: 12px 0 0; }
  @media (max-width: 600px) {
    .grid2 { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
    .toc { columns: 1; }
    header.site { flex-direction: column; align-items: flex-start; }
    header.site nav { justify-content: flex-start; }
  }
"""


def jsonld(obj):
    big = obj.get("@type") == "ItemList"
    return ('<script type="application/ld+json">\n' + json.dumps(obj, ensure_ascii=False, indent=None if big else 1, separators=(",", ":") if big else None)
            + "\n</script>")


def crumbs(trail):
    """trail: [(name, url)] ending with the current page."""
    items = "".join(f'<li><a href="{u}">{e(n)}</a></li>' if i < len(trail) - 1 else f'<li aria-current="page">{e(n)}</li>'
                    for i, (n, u) in enumerate(trail))
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": DOMAIN + u} for i, (n, u) in enumerate(trail)]}
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>', ld


def store_button(label="Get early access"):
    return (f'<a class="btn store-btn" href="mailto:{EMAIL}?subject=Wisconsin%20Eats%20early%20access&amp;body=Send%20me%20the%20TestFlight%20link.">'
            f'{APPLE}<span class="store-label">{label}</span></a>')


def page(path, title, desc, body, lds=(), robots="index,follow,max-image-preview:large", og_alt=None):
    assert 50 <= len(title) <= 60 or path == "404.html", (path, len(title), title)
    assert 140 <= len(desc) <= 160 or path == "404.html", (path, len(desc), desc)
    assert body.count("<h1") == 1, path
    url = DOMAIN + "/" + ("" if path == "index.html" else path)
    og_alt = og_alt or f"{BRAND}: {TAGLINE}. Every Wisconsin restaurant, with hand-checked fish fries, supper clubs and custard stands."
    ld = "\n".join(jsonld(x) for x in lds)
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="{robots}">
<meta name="theme-color" content="#203731">
<!-- Smart App Banner: once the App Store Connect record exists, replace APP_ID with the numeric Apple ID and uncomment.
<meta name="apple-itunes-app" content="app-id=APP_ID">
-->
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="{'website' if path == 'index.html' else 'article'}">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{DOMAIN}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(og_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{DOMAIN}/og.png">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<style>{CSS}</style>
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="wrap">
  <header class="site">
    <a class="logo" href="/" aria-label="{BRAND} home">{LOGO}{BRAND}</a>
    <nav aria-label="Main">
      <a href="/wisconsin-fish-fry.html">Fish fry</a>
      <a href="/wisconsin-supper-clubs.html">Supper clubs</a>
      <a href="/wisconsin-frozen-custard.html">Custard</a>
      <a href="/#cities">Cities</a>
    </nav>
  </header>
{body}
  <footer>
    <nav aria-label="Footer">
      <a href="/">{BRAND} app</a>
      <a href="/wisconsin-fish-fry.html">Wisconsin fish fry guide</a>
      <a href="/wisconsin-supper-clubs.html">Wisconsin supper clubs</a>
      <a href="/wisconsin-frozen-custard.html">Wisconsin frozen custard</a>
      <a href="/privacy.html">Privacy policy</a>
      <a href="/terms.html">Terms of use</a>
      <a href="mailto:{EMAIL}">Email us</a>
    </nav>
    <p>Place data: hand-checked research by {BRAND} ({CHECKED}); Overture Maps Foundation (CDLA Permissive 2.0); © OpenStreetMap contributors (ODbL); City of Milwaukee Open Data; Public Health Madison &amp; Dane County. Not affiliated with any restaurant, team, chain or government agency. Places open and close, so check before you go.</p>
    <p>© 2026 {BRAND}.</p>
  </footer>
</div>
<script>
  // Once the App Store listing exists, paste its URL here (looks like https://apps.apple.com/app/id123456789).
  // Every button switches from "Get early access" to "Download on the App Store" automatically.
  // Also fill in the apple-itunes-app meta tag in <head> on every page (re-run scripts/make-site.py after editing it there).
  var APP_STORE_URL = "";
  if (APP_STORE_URL) {{
    document.querySelectorAll(".store-btn").forEach(function (b) {{ b.href = APP_STORE_URL; b.rel = "noopener"; }});
    document.querySelectorAll(".store-label").forEach(function (l) {{ l.textContent = "Download on the App Store"; }});
    document.querySelectorAll(".store-note").forEach(function (n) {{ n.textContent = "Free for iPhone and iPad."; }});
  }}
</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(f"{DOCS}/{path}"), exist_ok=True)
    open(f"{DOCS}/{path}", "w").write(doc)
    return path


def place_item(p, show_town=True, extra=None):
    facts = []
    if p.tags & FISHFRY and p.fish:
        facts.append(f"<b>Fish:</b> {e(p.fish)}")
    if p.tags & FISHFRY and p.days:
        facts.append(f"<b>Fish fry:</b> {e(p.days)}")
    if p.sides:
        facts.append(f"<b>Sides:</b> {e(p.sides)}")
    if p.founded:
        facts.append(f"<b>Since</b> {p.founded}")
    kinds = [k for bit, k in ((SUPPER, "Supper club"), (FISHFRY, "Fish fry"), (CUSTARD, "Custard"), (BOIL, "Fish boil")) if p.tags & bit]
    where = ", ".join(x for x in (p.addr, p.city if show_town or not p.addr else p.city) if x)
    if extra:
        where += f" · {extra}"
    out = [f"<li><h3>{e(p.name)}</h3>", f'<p class="where">{e(where)}</p>']
    if kinds:
        out.append('<p class="facts">' + "".join(f'<span class="tag">{k}</span>' for k in kinds) + (" " + " · ".join(facts) if facts else "") + "</p>")
    elif facts:
        out.append('<p class="facts">' + " · ".join(facts) + "</p>")
    if p.note:
        out.append(f'<p class="note">{e(p.note)}</p>')
    if p.site:
        host = re.sub(r"^https?://(www\.)?", "", p.site).split("/")[0]
        out.append(f'<p class="link"><a href="{e(p.site)}" rel="noopener nofollow">{e(host)}</a></p>')
    out.append("</li>")
    return "".join(out)


def restaurant_ld(p):
    x = {"@type": "Restaurant", "name": p.name,
         "address": {"@type": "PostalAddress", "streetAddress": p.addr, "addressLocality": p.city, "addressRegion": "WI", "addressCountry": "US"}}
    if p.zip:
        x["address"]["postalCode"] = p.zip
    if p.site:
        x["url"] = p.site
    if p.founded:
        x["foundingDate"] = str(p.founded)
    if p.cuisine and p.cuisine not in ("Other", "Restaurant"):
        x["servesCuisine"] = p.cuisine
    return x


def item_list(name, places, url):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": len(places),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": restaurant_ld(p)} for i, p in enumerate(places)]}


def article_ld(url, headline, desc):
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline, "description": desc,
            "datePublished": TODAY, "dateModified": TODAY, "inLanguage": "en", "mainEntityOfPage": url,
            "image": f"{DOMAIN}/og.png", "author": {"@type": "Organization", "name": BRAND, "url": DOMAIN + "/"},
            "publisher": {"@type": "Organization", "name": BRAND, "url": DOMAIN + "/", "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png"}}}


def fit(options, lo, hi):
    for o in options:
        if lo <= len(o) <= hi:
            return o
    raise ValueError(f"nothing fits {lo}-{hi}: {[(len(o), o) for o in options]}")


# ---------------------------------------------------------------- counts shared by several pages
N_REST = len(REST)
N_TOWNS = len({p.city for p in REST if p.city})
FISH_WORDS = Counter()
for p in FISH:
    for f in {re.sub(r"^(lake|walleyed|yellow|icelandic|atlantic|north atlantic|alaskan|fresh|beer[- ]battered|breaded|baked|broiled|fried)\s+", "", x.strip().lower()) for x in p.fish.split(",") if x.strip()}:
        f = {"walleye pike": "walleye", "blue gill": "bluegill", "pollock": "pollock", "lake perch": "perch", "smelt": "smelt"}.get(f, f)
        FISH_WORDS[f] += 1
N_FISH_KNOWN = sum(1 for p in FISH if p.fish)
NOT_ONLY_FRIDAY = sum(1 for p in FISH if p.days and p.days.strip().lower() not in ("friday", "fridays"))
for p in PLACES:
    p.county = county(p)
    p.region = REGION_OF.get(p.county) if p.county else None


def by_region(places):
    groups = defaultdict(list)
    for p in places:
        groups[p.region or "Elsewhere in Wisconsin"].append(p)
    order = list(REGIONS) + ["Elsewhere in Wisconsin"]
    return [(r, sorted(groups[r], key=lambda p: (p.city, p.name.lower()))) for r in order if groups.get(r)]


def region_sections(places, noun):
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{slug(r)}">{e(r)}</a> ({len(ps)})</li>' for r, ps in by_region(places)) + "</ul>"
    secs = []
    for r, ps in by_region(places):
        secs.append(f'<section id="{slug(r)}" aria-labelledby="h-{slug(r)}"><h2 id="h-{slug(r)}">{e(r)}</h2>'
                    f'<p class="sub">{len(ps)} {noun}{"s" if len(ps) != 1 else ""}, by town.</p><ol class="places">'
                    + "".join(place_item(p) for p in ps) + "</ol></section>")
    return toc, "\n".join(secs)


CITY_PAGES = ["Milwaukee", "Madison", "Green Bay", "Appleton", "Kenosha", "Eau Claire", "Racine", "Oshkosh",
              "La Crosse", "Sheboygan", "Waukesha", "Janesville", "Wisconsin Dells"]


def city_url(c):
    return f"/cities/{slug(c)}.html"


def city_links():
    return '<ul class="cities">' + "".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in CITY_PAGES) + "</ul>"


written = []

# ---------------------------------------------------------------- fish fry guide
url = f"{DOMAIN}/wisconsin-fish-fry.html"
top_fish = FISH_WORDS.most_common(6)
fish_line = ", ".join(f"{f} ({n})" for f, n in top_fish)
title = fit([f"Wisconsin Friday Fish Fry Guide: {len(FISH)} Places | {BRAND}", f"Wisconsin Fish Fry Guide: {len(FISH)} Places | {BRAND}",
             f"Wisconsin Friday Fish Fry: {len(FISH)} Checked Places"], 50, 60)
desc = fit([f"{len(FISH)} Wisconsin Friday fish fries, each checked open in {CHECKED}: the fish they serve, the days, the sides, by region and town. Free, no ratings.",
            f"{len(FISH)} Wisconsin Friday fish fries checked open in {CHECKED}, with the fish, days and sides, listed by region and town. Free, no ads, no ratings."], 140, 160)
toc, secs = region_sections(FISH, "fish fry")
nav, bc = crumbs([("Home", "/"), ("Wisconsin fish fry guide", "/wisconsin-fish-fry.html")])
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} guide · checked {CHECKED}</span>Wisconsin Friday fish fry guide</h1>
    <p class="lede">{len(FISH)} restaurants, taverns and supper clubs across Wisconsin that serve a regular Friday fish fry, each confirmed open in {CHECKED} on its own website, menu or recent local news. For each one: the fish, the days and the sides when the place says so.</p>
    <div class="cta-row">{store_button()}<span class="pill store-note">Free for iPhone and iPad. Coming to the App Store.</span></div>
  </section>
  <section id="about-fish-fry">
    <h2>What counts as a Wisconsin fish fry</h2>
    <p>A Friday fish fry is a plate of battered or breaded fish, usually cod, perch, walleye, haddock or bluegill, with coleslaw, rye bread and a choice of potato: fries, potato pancakes with applesauce, or German potato salad. Taverns, supper clubs, bowling alleys and family restaurants serve it every Friday of the year, not just in Lent. Many also offer a broiled or baked choice and a fish sandwich.</p>
    <p>This list only includes places that serve one regularly. Lent-only church and Legion fries are left out, because their dates change every year. Seasonal Northwoods places are in when they post their season.</p>
    <h2>What the {len(FISH)} fish fries serve</h2>
    <p>{N_FISH_KNOWN} of the {len(FISH)} list the fish they serve. Counting each fish once per place, the most common are {e(fish_line)}. {NOT_ONLY_FRIDAY} serve their fish fry on days other than Friday too; those days are listed with each place.</p>
    <p>How the list was built: every place was checked against a 2025 or 2026 source, such as its own menu page, a dated post on its site, a local news story or its Travel Wisconsin listing. Places with no current source, a dead website or a fish fry that is only mentioned in passing were left out. Nothing here comes from review sites, and the order is by region and town, not by anyone's rating. Days and menus change, so check with the restaurant before you go.</p>
    <p>In the {BRAND} app, the same list sorts by distance from you, and each place opens Apple Maps' own card for live hours, photos and directions. Looking for a supper club instead? See the <a href="/wisconsin-supper-clubs.html">Wisconsin supper club guide</a>, and for dessert, the <a href="/wisconsin-frozen-custard.html">frozen custard guide</a>.</p>
    <h2>Jump to a region</h2>
    {toc}
    <p class="fine">City pages: {", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in CITY_PAGES)}.</p>
  </section>
{secs}
  </main>"""
written.append(page("wisconsin-fish-fry.html", title, desc, body,
                    [article_ld(url, "Wisconsin Friday fish fry guide", desc), bc, item_list("Wisconsin Friday fish fries", FISH, url)]))

# ---------------------------------------------------------------- supper club guide
url = f"{DOMAIN}/wisconsin-supper-clubs.html"
sup_fish = sum(1 for p in SUP if p.tags & FISHFRY)
sup_old = sorted([p for p in SUP if p.founded], key=lambda p: p.founded)
sup_pre1950 = sum(1 for p in sup_old if p.founded < 1950)
title = fit([f"Wisconsin Supper Clubs: {len(SUP)} Checked Places | {BRAND}", f"Wisconsin Supper Club Guide: {len(SUP)} Places | {BRAND}"], 50, 60)
desc = fit([f"{len(SUP)} Wisconsin supper clubs checked open in {CHECKED}, by region and town: founding years, Friday fish fries and what each is known for. Free, no ratings.",
            f"{len(SUP)} Wisconsin supper clubs checked open in {CHECKED}, listed by region and town with founding years and Friday fish fries. Free, no ads."], 140, 160)
toc, secs = region_sections(SUP, "supper club")
oldest_line = "; ".join(f"{e(p.name)} in {e(p.city)} ({p.founded})" for p in sup_old[:5])
nav, bc = crumbs([("Home", "/"), ("Wisconsin supper clubs", "/wisconsin-supper-clubs.html")])
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} guide · checked {CHECKED}</span>Wisconsin supper club guide</h1>
    <p class="lede">{len(SUP)} Wisconsin supper clubs, each confirmed open in {CHECKED} on its own website, menu or recent local news, with its founding year when we could verify it and its Friday fish fry when it has one.</p>
    <div class="cta-row">{store_button()}<span class="pill store-note">Free for iPhone and iPad. Coming to the App Store.</span></div>
  </section>
  <section id="about-supper-clubs">
    <h2>What makes a supper club</h2>
    <p>A Wisconsin supper club is a dinner-only restaurant, often on a highway or a lake outside town, where the evening starts at the bar with a brandy old fashioned and goes on to a relish tray, prime rib or steak, and a Friday fish fry. Many are family-run for generations. There is no official definition; this list includes places that call themselves supper clubs or are widely known as one, such as on Ron Faiola's Wisconsin supper club list or Travel Wisconsin's supper club pages.</p>
    <h2>The {len(SUP)} in numbers</h2>
    <p>{sup_fish} of the {len(SUP)} supper clubs also serve a Friday fish fry. {len(sup_old)} have a founding year we could verify, and {sup_pre1950} of those opened before 1950. The oldest on the list: {oldest_line}.</p>
    <p>How the list was built: every supper club was checked against a 2025 or 2026 source, such as its own site with current menus or hours, a dated news story or its Travel Wisconsin listing. Places whose only trace was an old website, a parked domain or a Facebook page we could not read without logging in were left out, even when they may well be open. Nothing here comes from review sites. The order is by region and town, never by rating.</p>
    <p>In the {BRAND} app, the list sorts by distance and each club opens Apple Maps' own card with live hours and photos. Supper clubs are dinner-only and many close one or two nights a week, so call ahead. For Fridays, see the <a href="/wisconsin-fish-fry.html">Wisconsin fish fry guide</a>.</p>
    <h2>Jump to a region</h2>
    {toc}
    <p class="fine">City pages: {", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in CITY_PAGES)}.</p>
  </section>
{secs}
  </main>"""
written.append(page("wisconsin-supper-clubs.html", title, desc, body,
                    [article_ld(url, "Wisconsin supper club guide", desc), bc, item_list("Wisconsin supper clubs", SUP, url)]))

# ---------------------------------------------------------------- custard guide
url = f"{DOMAIN}/wisconsin-frozen-custard.html"
cust_old = sorted([p for p in CUST if p.founded], key=lambda p: p.founded)
title = fit([f"Wisconsin Frozen Custard Stands: {len(CUST)} Places | {BRAND}", f"Wisconsin Frozen Custard: {len(CUST)} Local Stands | {BRAND}",
             f"Wisconsin Frozen Custard Stands: {len(CUST)} Local Places"], 50, 60)
desc = fit([f"{len(CUST)} local frozen custard stands in Wisconsin, not the big chains, checked open in {CHECKED} and listed by region and town. Free app for iPhone and iPad.",
            f"{len(CUST)} independent Wisconsin frozen custard stands, checked open in {CHECKED} and listed by region and town, without the big chains. Free, no ads."], 140, 160)
toc, secs = region_sections(CUST, "custard stand")
cust_old_line = "; ".join(f"{e(p.name)} in {e(p.city)} ({p.founded})" for p in cust_old[:4])
nav, bc = crumbs([("Home", "/"), ("Wisconsin frozen custard", "/wisconsin-frozen-custard.html")])
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} guide · checked {CHECKED}</span>Wisconsin frozen custard stands</h1>
    <p class="lede">{len(CUST)} local frozen custard stands across Wisconsin. The national chains are left out on purpose; they have their own apps.</p>
    <div class="cta-row">{store_button()}<span class="pill store-note">Free for iPhone and iPad. Coming to the App Store.</span></div>
  </section>
  <section id="about-custard">
    <h2>Custard, not soft serve</h2>
    <p>Frozen custard is ice cream made with egg yolk and churned slowly with little air, so it comes out dense and is served fresh, often with a flavor of the day. It is a Milwaukee-area tradition, and stands all over the state post a daily flavor calendar. Soft-serve and hard ice cream shops are not on this list unless they make custard.</p>
    <p>{len(cust_old)} of the {len(CUST)} stands have a founding year we could verify. The oldest: {cust_old_line}.</p>
    <p>How the list was built: stands were confirmed open with a 2025 or 2026 source, such as their own flavor calendar, menu or a dated news story. A stand is in only if it actually sells frozen custard. Chains with five or more locations in the state are left out. Many stands close for winter, so check their hours before you go.</p>
    <p>In the {BRAND} app, custard stands sort by distance, and each opens Apple Maps' own card for live hours. Pair one with a <a href="/wisconsin-fish-fry.html">Friday fish fry</a> or a <a href="/wisconsin-supper-clubs.html">supper club</a> dinner.</p>
    <h2>Jump to a region</h2>
    {toc}
  </section>
{secs}
  </main>"""
written.append(page("wisconsin-frozen-custard.html", title, desc, body,
                    [article_ld(url, "Wisconsin frozen custard stands", desc), bc, item_list("Wisconsin frozen custard stands", CUST, url)]))

# ---------------------------------------------------------------- city pages
city_stats = {}
for c in CITY_PAGES:
    here = [p for p in REST if p.city == c and p.lat is not None]
    n_town = sum(1 for p in REST if p.city == c)
    lat = sorted(p.lat for p in here)[len(here) // 2]
    lon = sorted(p.lon for p in here)[len(here) // 2]
    center = (lat, lon)

    def near(ps, radius):
        out = []
        for p in ps:
            if p.lat is None:
                continue
            d = miles(center, (p.lat, p.lon))
            if p.city == c or d <= radius:
                out.append((0 if p.city == c else 1, d, p))
        out.sort(key=lambda x: (x[0], x[1] if x[0] else 0, x[2].name.lower()))
        return [(d, p) for _, d, p in out]

    ff, sc, cu = near(FISH, 12), near(SUP, 25), near(CUST, 12)
    icons = sorted([p for p in here if p.ip is not None], key=lambda p: (-p.ip, p.name.lower()))
    oldest = sorted([p for p in here if p.founded], key=lambda p: (p.founded, p.name.lower()))[:10]
    cuis = Counter(p.cuisine for p in REST if p.city == c and p.cuisine and p.cuisine not in ("Other", "Restaurant")).most_common(10)
    city_stats[c] = (n_town, len(ff), len(sc), len(cu))

    def items(lst):
        return "".join(place_item(p, extra=None if p.city == c else f"{d:.0f} mi from {c}") for d, p in lst)

    path = f"cities/{slug(c)}.html"
    url = DOMAIN + "/" + path
    title = fit([f"{c} Fish Fries, Supper Clubs & Restaurants | {BRAND}", f"{c} Fish Fry, Supper Clubs & Restaurants | {BRAND}",
                 f"{c} Fish Fries & Supper Clubs | {BRAND}", f"{c}, WI Fish Fries & Supper Clubs | {BRAND}",
                 f"{c}, WI Fish Fry, Supper Clubs & Restaurants", f"{c}, Wisconsin Fish Fries & Supper Clubs Guide",
                 f"{c}, Wisconsin Fish Fries, Supper Clubs & Restaurants"], 50, 60)
    desc = fit([f"Friday fish fries, supper clubs and custard stands in and near {c}, WI, checked open in {CHECKED}, plus local icons and the oldest restaurants in town.",
                f"Fish fries, supper clubs and custard in and near {c}, Wisconsin, checked open in {CHECKED}, with local icons and the oldest restaurants in town.",
                f"Friday fish fries, supper clubs and frozen custard in and near {c}, Wisconsin, checked open in {CHECKED}, plus local icons and the oldest places.",
                f"Fish fries, supper clubs and custard in and near {c}, WI, checked open in {CHECKED}, with local icons and the oldest restaurants in town."], 140, 160)
    nav, bc = crumbs([("Home", "/"), ("Cities", "/#cities"), (c, "/" + path)])
    parts = [f"""{nav}
  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND} · {e(c)}, Wisconsin</span>{e(c)} fish fries, supper clubs &amp; restaurants</h1>
    <p class="lede">{len(ff)} Friday fish fries, {len(sc)} supper clubs and {len(cu)} custard stands in and around {e(c)}, each checked open in {CHECKED}. The {BRAND} app has all {n_town:,} restaurants, cafés, taverns and bakeries in {e(c)} and sorts them by distance from you.</p>
    <div class="cta-row">{store_button()}<span class="pill store-note">Free for iPhone and iPad. Coming to the App Store.</span></div>
  </section>"""]
    if ff:
        parts.append(f'<section id="fish-fry"><h2>Friday fish fry in and near {e(c)}</h2><p class="sub">Places in {e(c)} first, then others within 12 miles, closest first. Fish and days as each place lists them. <a href="/wisconsin-fish-fry.html">All {len(FISH)} Wisconsin fish fries</a>.</p><ol class="places">{items(ff)}</ol></section>')
    if sc:
        parts.append(f'<section id="supper-clubs"><h2>Supper clubs near {e(c)}</h2><p class="sub">Supper clubs in {e(c)}, then others within 25 miles, closest first. <a href="/wisconsin-supper-clubs.html">All {len(SUP)} Wisconsin supper clubs</a>.</p><ol class="places">{items(sc)}</ol></section>')
    if cu:
        parts.append(f'<section id="custard"><h2>Frozen custard in and near {e(c)}</h2><p class="sub">Local stands, not the chains, within 12 miles. <a href="/wisconsin-frozen-custard.html">All {len(CUST)} Wisconsin custard stands</a>.</p><ol class="places">{items([(d, p) for d, p in cu])}</ol></section>')
    if icons:
        parts.append(f'<section id="icons"><h2>{e(c)} icons</h2><p class="sub">James Beard Award winners, finalists and semifinalists, and long-running local institutions, most honored first. Honors are from the James Beard Foundation\'s own award records and other named sources.</p><ol class="places">'
                     + "".join(place_item(p) for p in icons) + "</ol></section>")
    if oldest:
        parts.append(f'<section id="oldest"><h2>Oldest restaurants in {e(c)}</h2><p class="sub">Founding years checked against the restaurant\'s own history page or local news, oldest first.</p><ol class="places">'
                     + "".join(place_item(p) for p in oldest) + "</ol></section>")
    if cuis:
        rows = "".join(f'<tr><td>{e(k)}</td><td class="n">{n:,}</td></tr>' for k, n in cuis)
        parts.append(f'<section id="cuisines"><h2>What {e(c)} eats</h2><p class="sub">The most common kinds of restaurant among the {n_town:,} in {e(c)}, from open map data and the city and county license lists.</p><table><thead><tr><th scope="col">Kind of place</th><th scope="col" class="n">Places</th></tr></thead><tbody>{rows}</tbody></table></section>')
    others = [x for x in CITY_PAGES if x != c]
    parts.append(f'<section id="more"><h2>More Wisconsin cities</h2>{city_links()}</section>\n  </main>')
    listed = [p for _, p in ff] + [p for _, p in sc if not p.tags & FISHFRY or p.city != c] + [p for _, p in cu]
    seen, uniq = set(), []
    for p in listed:
        if id(p) not in seen:
            seen.add(id(p)); uniq.append(p)
    written.append(page(path, title, desc, "\n".join(parts),
                        [article_ld(url, f"{c} fish fries, supper clubs and restaurants", desc), bc, item_list(f"Fish fries, supper clubs and custard near {c}", uniq, url)]))

# ---------------------------------------------------------------- landing page
shots = [("home", "Wisconsin Eats home screen: Friday Fish Fry, Supper Clubs, Frozen Custard, Wisconsin Icons, Oldest Places and Inspections guides, with a search box for every restaurant in the state.", "Guides for Fridays, supper clubs and custard."),
         ("fishfry", "Friday Fish Fry list in Wisconsin Eats, sorted by distance from downtown Milwaukee, with the fish each place serves.", "Fish fries nearest you first."),
         ("detail", "The Del-Bar supper club in Wisconsin Dells in Wisconsin Eats: address, a button for ratings, hours and photos in Apple Maps, and its history since 1943.", "Each place, with live Apple Maps hours and photos."),
         ("map", "Wisconsin Eats map of Wisconsin with clustered pins for fish fries.", "The map, by fish fry, supper club or custard."),
         ("icons", "Wisconsin Icons list in Wisconsin Eats: James Beard honorees and long-running institutions.", "James Beard honorees and institutions.")]
shot_html = []
for i, (name, alt, cap) in enumerate(shots):
    png = f"{DOCS}/img/screen-{name}.png"
    w, h = png_size(png) if os.path.exists(png) else (480, 1043)
    lazy = ' loading="lazy"' if i > 1 else ""
    shot_html.append(f'<li><picture><source srcset="/img/screen-{name}.webp" type="image/webp"><img src="/img/screen-{name}.png" alt="{e(alt)}" width="{w}" height="{h}"{lazy} decoding="async"></picture><p>{e(cap)}</p></li>')

faq = [
    ("Is Wisconsin Eats free?", "Yes. The app is free, with no ads, no in-app purchases and no account."),
    ("Where do the fish fries and supper clubs come from?", f"We checked each one by hand in {CHECKED}: every place on the fish fry, supper club and custard lists has a 2025 or 2026 source such as its own menu page, a dated news story or its Travel Wisconsin listing. The rest of the {N_REST:,} restaurants come from Overture Maps' open place data and the City of Milwaukee and Dane County license lists."),
    ("Does the app show ratings and reviews?", "Not its own. Tap a place and Apple Maps' own place card opens inside the app with Apple's current ratings, hours, photos and directions. Our lists are never ordered by ratings."),
    ("Does it need my location?", "Only if you want lists sorted by distance. Your location stays on your iPhone or iPad and is never sent to us. Everything else works without it."),
    ("What are the inspection grades?", "For Madison and Dane County, the app grades places on a curve from Public Health Madison & Dane County's routine inspections since January 2023. They are our summary, not official grades. Other counties don't publish inspections in bulk."),
    ("A place closed or is missing. How do I tell you?", f"Email {EMAIL} with the name and town. Corrections go into the next update."),
    ("Is there an Android version?", f"Not yet. Wisconsin Eats is for iPhone and iPad. If enough people ask at {EMAIL}, it moves up the list."),
]
faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "@id": f"{DOMAIN}/#faq",
          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
app_ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "MobileApplication", "@id": f"{DOMAIN}/#app", "name": "Wisconsin Eats: Restaurants",
     "alternateName": ["Wisconsin Eats", "WI Eats", "Wisconsin Eats: Fish Fry & Supper Club Guide"],
     "description": f"A free guide to every restaurant in Wisconsin, with hand-checked lists of {len(FISH)} Friday fish fries, {len(SUP)} supper clubs and {len(CUST)} frozen custard stands. Sort by distance, open Apple Maps' live place card for hours and photos, and save places for Friday.",
     "url": f"{DOMAIN}/", "image": f"{DOMAIN}/og.png", "screenshot": f"{DOMAIN}/img/screen-home.png",
     "operatingSystem": "iOS, iPadOS", "applicationCategory": "TravelApplication", "applicationSubCategory": "Food & Drink",
     "inLanguage": "en", "publisher": {"@id": f"{DOMAIN}/#org"},
     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "category": "free"}},
    {"@type": "Organization", "@id": f"{DOMAIN}/#org", "name": BRAND, "url": f"{DOMAIN}/",
     "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png", "width": 512, "height": 512}, "email": EMAIL,
     "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL, "availableLanguage": "en"}},
    {"@type": "WebSite", "@id": f"{DOMAIN}/#website", "name": BRAND, "alternateName": ["WI Eats", "Wisconsin Eats app"], "url": f"{DOMAIN}/",
     "inLanguage": "en", "publisher": {"@id": f"{DOMAIN}/#org"}}]}
title = "Wisconsin Eats: Fish Fry, Supper Club & Restaurant App"
desc = fit([f"Free iPhone and iPad guide to every Wisconsin restaurant, with {len(FISH)} hand-checked Friday fish fries, {len(SUP)} supper clubs and {len(CUST)} frozen custard stands.",
            f"Free iPhone and iPad guide to every restaurant in Wisconsin, with {len(FISH)} hand-checked Friday fish fries, {len(SUP)} supper clubs and custard stands."], 140, 160)
city_cards = "".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in CITY_PAGES)
body = f"""  <main id="main">
  <section class="hero">
    <h1><span class="kicker">{BRAND}: the {TAGLINE.lower()} for iPhone and iPad</span>Every Wisconsin restaurant, and the fish fries worth the drive</h1>
    <p class="lede">{BRAND} is a free Wisconsin restaurant guide. Find a Friday fish fry near you, a supper club for Saturday and a custard stand for after, from lists we checked by hand, plus all {N_REST:,} restaurants, cafés, taverns and bakeries in {N_TOWNS:,} towns.</p>
    <div class="cta-row">{store_button()}<span class="pill store-note">Free. No ads, no account. Coming to the App Store.</span></div>
    <ul class="stats" aria-label="What's in the app">
      <li><b>{len(FISH)}</b><span>Friday fish fries</span></li>
      <li><b>{len(SUP)}</b><span>supper clubs</span></li>
      <li><b>{len(CUST)}</b><span>custard stands</span></li>
      <li><b>{N_REST:,}</b><span>restaurants</span></li>
    </ul>
  </section>

  <section id="what">
    <h2>A Wisconsin restaurant guide that knows what Friday means</h2>
    <p class="sub">General restaurant apps rank by star ratings and can't tell you who serves perch on Friday. {BRAND} starts from the things people here actually look for: a fish fry, a supper club with a relish tray, a custard stand with a flavor of the day, and the old places that have been open since before your grandparents. Every one of those was checked open in {CHECKED}. For ratings, hours and photos, each place opens Apple Maps' own live card.</p>
  </section>

  <section id="how">
    <h2>How it works</h2>
    <ol class="steps">
      <li class="step"><div class="n" aria-hidden="true">1</div><div><h3>Pick a guide.</h3><p>Friday Fish Fry, Supper Clubs, Frozen Custard, Wisconsin Icons, Oldest Places, or search every restaurant by name, town or street.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">2</div><div><h3>See what's near you.</h3><p>Sort by distance, filter by town or cuisine, or browse the map. Each fish fry lists the fish and the days it's served.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">3</div><div><h3>Go.</h3><p>Open Apple Maps' place card for live hours and photos, call, get directions, or save it for Friday.</p></div></li>
    </ol>
  </section>

  <section id="screens">
    <h2>What it looks like</h2>
    <ul class="shots" tabindex="0" aria-label="Wisconsin Eats app screenshots">
      {"".join(shot_html)}
    </ul>
  </section>

  <section id="guides">
    <h2>Wisconsin food guides</h2>
    <p class="sub">The app's hand-checked lists, readable on the web.</p>
    <div class="grid2">
      <a class="card" href="/wisconsin-fish-fry.html"><h3>Wisconsin Friday fish fry guide</h3><p>{len(FISH)} fish fries by region and town, with the fish, days and sides.</p></a>
      <a class="card" href="/wisconsin-supper-clubs.html"><h3>Wisconsin supper club guide</h3><p>{len(SUP)} supper clubs, with founding years and Friday fish fries.</p></a>
      <a class="card" href="/wisconsin-frozen-custard.html"><h3>Wisconsin frozen custard stands</h3><p>{len(CUST)} local stands, without the big chains.</p></a>
      <div class="card"><h3>Every restaurant</h3><p>{N_REST:,} places in {N_TOWNS:,} towns, from open map data and the Milwaukee and Dane County license lists. In the app.</p></div>
    </div>
  </section>

  <section id="cities">
    <h2>Fish fries and supper clubs by city</h2>
    <p class="sub">Fish fries, supper clubs, custard, local icons and the oldest restaurants in Wisconsin's biggest towns.</p>
    <ul class="cities">{city_cards}</ul>
  </section>

  <section id="pricing">
    <h2>Free, and staying that way</h2>
    <p class="sub">No ads, no subscription, no in-app purchases, no account. The whole guide is built into the app, so lists open instantly and work with a weak signal up north.</p>
  </section>

  <section id="privacy">
    <h2>Your Friday plans are your business</h2>
    <p class="sub">{BRAND} collects nothing. If you allow location, it only sorts lists by distance on your device. Saved places stay on your device. This website sets no cookies and runs no trackers. <a href="/privacy.html">Read the privacy policy</a>.</p>
  </section>

  <section id="faq">
    <h2>Questions</h2>
    {faq_html}
  </section>

  <section id="download" class="final">
    <h2>Find Friday's fish fry</h2>
    <p class="sub">{BRAND} is coming to the App Store for iPhone and iPad. Free.</p>
    <div class="cta-row">{store_button()}</div>
  </section>
  </main>"""
written.append(page("index.html", title, desc, body, [app_ld, faq_ld]))

# ---------------------------------------------------------------- privacy and terms
nav, bc = crumbs([("Home", "/"), ("Privacy policy", "/privacy.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Privacy policy</h1>
    <p class="lede">Short version: the {BRAND} app collects nothing about you, and this website doesn't track you. Last updated {TODAY}.</p>
  </section>
  <section>
    <h2>The app</h2>
    <ul>
      <li><b>No account, no analytics, no ads.</b> The app has no sign-in, no advertising and no analytics or crash-reporting code. We receive no data from it.</li>
      <li><b>Location.</b> If you allow it, your location is used on your device to sort places by distance and show where you are on the map. It is never sent to us. You can turn it off in Settings at any time.</li>
      <li><b>Saved places and filters</b> are stored only on your device and are deleted when you delete the app.</li>
      <li><b>Apple Maps.</b> When you open a place's ratings, hours and photos, or ask for directions, the app asks Apple Maps for that place. Apple handles that request under <a href="https://www.apple.com/legal/privacy/" rel="noopener">Apple's privacy policy</a>, as it does for any app that shows a map.</li>
      <li><b>Spotlight.</b> The app adds its fish fries, supper clubs and other hand-checked places to your device's search index so you can find them from Spotlight. That index stays on your device.</li>
      <li><b>Calls, websites and email</b> you start from a place open in the Phone app, your browser or Mail, and are handled by them.</li>
    </ul>
    <p>On the App Store, the app's privacy label is "Data Not Collected".</p>
    <h2>This website</h2>
    <p>The site is static pages hosted on GitHub Pages. It sets no cookies and loads no analytics, fonts or scripts from anyone else. GitHub may keep standard server logs, such as IP addresses, for security; see <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>.</p>
    <h2>Email</h2>
    <p>If you email us, we use your message and address only to reply and to fix the listing you told us about. We don't add you to a mailing list or share your address.</p>
    <h2>Children</h2>
    <p>The app collects no personal information from anyone, including children.</p>
    <h2>Changes and contact</h2>
    <p>If this policy changes, the new version will be posted here with a new date. Questions: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
  </section>
  </main>"""
written.append(page("privacy.html", "Privacy Policy: Wisconsin Eats Fish Fry & Restaurant App",
                    fit(["The Wisconsin Eats privacy policy: the app collects no data, keeps your location and saved places on your device, and this website sets no cookies at all."], 140, 160),
                    body, [bc]))

nav, bc = crumbs([("Home", "/"), ("Terms of use", "/terms.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Terms of use</h1>
    <p class="lede">The plain-language terms for the {BRAND} app and this website. Last updated {TODAY}.</p>
  </section>
  <section>
    <h2>What the app is</h2>
    <p>{BRAND} is a free guide to restaurants in Wisconsin. It is provided as is, for personal use, without charge and without warranties of any kind.</p>
    <h2>Check before you go</h2>
    <p>Restaurants open, close, change their hours and change their menus. Fish fry days, fish, sides and founding years are what each place or a named source said when we checked in {CHECKED}. We work to keep the lists right, but we can't promise that any listing is current or complete. Call the restaurant before you make the trip.</p>
    <h2>Inspection grades</h2>
    <p>Grades in the Inspections guide are our own summary, graded on a curve from Public Health Madison &amp; Dane County's routine inspection records since January 2023. They are not official grades and are not a statement by the health department. For official records, see Public Health Madison &amp; Dane County.</p>
    <h2>Other people's content</h2>
    <p>Ratings, reviews, hours and photos in each place card come from Apple Maps and are Apple's and its providers', under Apple's terms. Restaurant names and trademarks belong to their owners. {BRAND} is not affiliated with any restaurant, team, chain or government agency.</p>
    <h2>Data sources and licenses</h2>
    <ul>
      <li>Overture Maps Foundation places data, under the Community Data License Agreement, Permissive 2.0; boundaries and water under the Open Database License. © OpenStreetMap contributors, Overture Maps Foundation.</li>
      <li>City of Milwaukee Open Data: active food dealer and tavern licenses.</li>
      <li>Public Health Madison &amp; Dane County: licensed establishments and inspection records.</li>
      <li>James Beard Foundation: award, finalist and semifinalist history.</li>
      <li>Fish fries, supper clubs, custard stands and founding years: our own research, with a source recorded for every place.</li>
    </ul>
    <h2>Corrections</h2>
    <p>If a listing is wrong, or you own a restaurant and want something fixed, email <a href="mailto:{EMAIL}">{EMAIL}</a>. We fix mistakes in the next update.</p>
    <h2>Liability</h2>
    <p>To the extent the law allows, we are not liable for any loss arising from use of the app or site, including a wasted drive to a closed restaurant. Wisconsin law governs these terms.</p>
    <h2>Changes</h2>
    <p>We may update these terms; the current version and its date are always on this page. See also the <a href="/privacy.html">privacy policy</a>.</p>
  </section>
  </main>"""
written.append(page("terms.html", "Terms of Use: Wisconsin Eats Fish Fry & Restaurant App",
                    fit(["The Wisconsin Eats terms of use: a free Wisconsin restaurant guide, provided as is. Check before you go, and see where each listing and grade comes from."], 140, 160),
                    body, [bc]))

body = f"""  <main id="main">
  <section class="hero">
    <h1>Page not found</h1>
    <p class="lede">That page isn't here. Try the <a href="/">{BRAND} home page</a>, the <a href="/wisconsin-fish-fry.html">fish fry guide</a> or the <a href="/wisconsin-supper-clubs.html">supper club guide</a>.</p>
  </section>
  </main>"""
page("404.html", f"Page not found | {BRAND}", "This page doesn't exist.", body, robots="noindex,follow")

# ---------------------------------------------------------------- plumbing
urls = ["" if w == "index.html" else w for w in written]
urls.sort(key=lambda u: (u != "", u.startswith("cities/"), u))
open(f"{DOCS}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                       + "".join(f"  <url><loc>{DOMAIN}/{u}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in urls) + "</urlset>\n")
open(f"{DOCS}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
json.dump({"name": BRAND, "short_name": "WI Eats", "description": f"{TAGLINE} for every Wisconsin restaurant.", "start_url": "/", "display": "browser",
           "background_color": "#fbfaf6", "theme_color": "#203731",
           "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]},
          open(f"{DOCS}/site.webmanifest", "w"), indent=2)
open(f"{DOCS}/CNAME", "w").write("wisconsineats.com\n")
open(f"{DOCS}/.nojekyll", "w").write("")
json.dump({"generated": TODAY, "restaurants": N_REST, "towns": N_TOWNS, "fish_fry": len(FISH), "supper_clubs": len(SUP), "custard": len(CUST),
           "fish_listed": N_FISH_KNOWN, "fish_counts": dict(FISH_WORDS.most_common(12)), "not_only_friday": NOT_ONLY_FRIDAY,
           "supper_with_fish_fry": sup_fish, "supper_founded_known": len(sup_old), "supper_pre1950": sup_pre1950,
           "cities": {c: dict(zip(["restaurants", "fish_fry_near", "supper_near", "custard_near"], v)) for c, v in city_stats.items()}},
          open(f"{ROOT}/playbook/site-numbers.json", "w"), indent=1)
print("wrote", len(written) + 1, "pages:", ", ".join(written))
print(f"restaurants {N_REST:,} in {N_TOWNS} towns | fish fry {len(FISH)} | supper {len(SUP)} | custard {len(CUST)}")
print("top fish:", FISH_WORDS.most_common(10))
