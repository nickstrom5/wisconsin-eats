"""Writes the public website in docs/ from the same data file the app ships (data/app/places.json).

Pages: the landing page; three statewide guides (fish fry, supper clubs, frozen custard) and a Lent fish fry page; one page per
big city and a cities hub; four region pages; one page per hand-checked place; about, privacy, terms and 404; plus sitemap.xml,
robots.txt, site.webmanifest, the favicons and the web app's data files. Everything listed is hand-checked research or licensed
open data; nothing comes from Google, Yelp or any ratings site, and nothing is ranked by ratings.

Every page gets a strict Content-Security-Policy <meta> built from sha256 hashes of its own inline <script> and <style> blocks,
so a page with an inline style attribute, event handler or unhashed script fails here, at build time.

Usage (from the repo root): .venv/bin/python scripts/make-site.py
Re-run it after every data rebuild, then check the pages: .venv/bin/python scripts/qa-site.py (see CLAUDE.md, "Website").
"""
import base64
import datetime
import hashlib
import html
import json
import math
import os
import re
import shutil
import struct
import unicodedata
from collections import Counter, defaultdict
from urllib.parse import quote, urlsplit

from PIL import Image
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = f"{ROOT}/docs"
# Where the site lives: GitHub Pages behind this custom domain (docs/CNAME). Set it to None to go back to the github.io address.
CUSTOM_DOMAIN = "wisconsin.eatsranked.com"
DOMAIN = f"https://{CUSTOM_DOMAIN}" if CUSTOM_DOMAIN else "https://nickstrom5.github.io/wisconsin-eats"
BASE = "" if CUSTOM_DOMAIN else "/wisconsin-eats"     # path prefix for root-relative links
BRAND = "Wisconsin Eats"
TAGLINE = "Fish fry & supper club guide"
EMAIL = "nick@eatsranked.com"     # the public contact address (Nick, 2026-10-12; Cloudflare Email Routing). The app's Links.swift follows next build
AUTHOR = "Nicholas Soderstrom"     # the app's maker; name only in public markup, never an email

D = json.load(open(f"{ROOT}/data/app/places.json"))
BUILD_DATE = D["generated"][:10]   # the data export's date: dateModified, sitemap lastmod and "data as of" lines
BUILD = datetime.date.fromisoformat(BUILD_DATE)
# When the hand checks behind hc=1 were done, each against a 2025 or 2026 source. A fact about the research, not the build:
# change it only when the research is redone (the app's About screen says the same).
HAND_CHECKED = "September 2026"
SITE_LAUNCHED = "2026-09-26"    # the guides and city pages first went up (Article datePublished)
PAGES_ADDED = "2026-10-07"      # place, region, Lent, about and cities-hub pages first went up
POLICY_UPDATED = "2026-10-12"   # when the privacy policy or terms text last changed: edit this whenever you edit them (10-12: new contact address)

# The App Store listing. None until the app is live. When it is: set APP_STORE_URL (https://apps.apple.com/app/id6816947017),
# and put Apple's official "Download on the App Store" badge artwork at docs/img/app-store-badge.svg first (from Apple's
# marketing resources; never redraw it). Every page then links the badge, gets the Smart App Banner meta tag, and the
# MobileApplication JSON-LD gets installUrl/sameAs. The build fails if the badge file is missing.
APP_STORE_URL = None
APP_ID = "6816947017"
APP_STORE_BADGE = "/img/app-store-badge.svg"
if APP_STORE_URL:
    assert os.path.exists(DOCS + APP_STORE_BADGE), f"add Apple's official badge artwork at docs{APP_STORE_BADGE} before setting APP_STORE_URL"

CITIES, CUISINES = D["cities"], D["cuisines"]
SUPPER, FISHFRY, CURDS, CUSTARD, BOIL = 1, 2, 4, 8, 16


def modified(published):
    return max(BUILD_DATE, published)


def long_date(d):
    d = datetime.date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d:%B} {d.day}, {d.year}"


# ---------------------------------------------------------------- safe links built from data
def safe_url(u):
    """A place's website as an http(s) URL, or None. A bare host gets https://; any other scheme is dropped."""
    u = (u or "").strip()
    if not u or re.search(r"[\s\"'<>\\`{}|^]", u):
        return None
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", u):
        u = "https://" + u.lstrip("/")
    try:
        s = urlsplit(u)
    except ValueError:
        return None
    if s.scheme.lower() not in ("http", "https") or not s.hostname or "." not in s.hostname:
        return None
    return u


# The link checker's verdicts (pipeline/check_websites.py) and the manual ones (website_overrides.json). The export ships only
# links that passed, so places.json is the list; a verdict that turned bad after the export (a site found hijacked, say) takes the
# link off the website at the next site build. website_check.json is rewritten while a check runs (it saves partial results), so a
# link with no verdict yet, or one that only failed to load (a timeout, a 5xx, a 403 or 429), keeps its export-time pass until the
# next export: otherwise a build during a re-check, or after a network drop, would silently strip hundreds of good links.
LINK_VERDICTS = json.load(open(f"{ROOT}/data/wi/website_check.json"))
_over = f"{ROOT}/data/wi/website_overrides.json"
LINK_OVERRIDES = json.load(open(_over)) if os.path.exists(_over) else {}
TRANSIENT = re.compile(r"^(error: |http (403|408|429|5\d\d)$)")
SITE_DROPS = {}     # url -> why, for each website in places.json the site leaves off


def link_verdict(u):
    """(ok, why) for a link: a manual verdict first, then the checker's; (None, "") if neither has one."""
    for book in (LINK_OVERRIDES, LINK_VERDICTS):
        v = book.get(u) or book.get(u.removeprefix("https://"))
        if v:
            return bool(v.get("ok")), v.get("why", "")
    return None, ""


def place_site(u):
    """A place's website for the site and the web app: a safe http(s) URL with no standing bad verdict, or None."""
    u2 = safe_url(u)
    if not u2:
        return None
    ok, why = link_verdict(u)
    if ok is False and not TRANSIENT.match(why):
        SITE_DROPS[u] = why
        return None
    return u2


n_sites = len({r["w"] for r in D["places"] if place_site(r.get("w")) or r.get("w") in SITE_DROPS})
# a verdict file that turned bad wholesale (a broken check run) must not quietly strip the site's links: stop and say so
assert len(SITE_DROPS) <= max(10, n_sites // 100), (f"{len(SITE_DROPS)} of {n_sites} websites would be left off by website_check.json/"
    f"website_overrides.json verdicts newer than places.json: {Counter(w[:40] for w in SITE_DROPS.values()).most_common(8)}. "
    "Re-export places.json (WI_APP=1) after a link check instead of building the site against it.")


def safe_tel(ph):
    """tel: link with digits and + only, or None."""
    t = re.sub(r"[^\d+]", "", ph or "")
    return "tel:" + t if len(re.sub(r"\D", "", t)) >= 10 else None


def phone_text(ph):
    d = re.sub(r"\D", "", ph or "")
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (ph or "")


class P:
    """One place, with the same meaning the app gives each field (WisconsinEats/Models/Place.swift)."""

    def __init__(self, r):
        self.r = r
        self.id = r["id"]
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
        self.h = r.get("h") or 0
        self.founded = r.get("f")
        self.fish = r.get("fish") or ""
        self.days = r.get("days") or ""
        self.sides = r.get("sides") or ""
        self.note = r.get("note") or r.get("icon") or ""
        self.icon = r.get("icon") or ""
        self.site = place_site(r.get("w"))
        self.tel = safe_tel(r.get("ph"))
        self.phone = phone_text(r.get("ph")) if self.tel else ""
        self.honors = r.get("hon") or ""
        self.jbf = r.get("jbf") or ""
        self.hc = r.get("hc") == 1   # hand-checked open with a 2025-26 source; the only places the guides list
        self.slug = None            # set for places with their own page

    def featured_key(self):
        # the app's "Featured first": honored places, then verified founding year, then name
        return (-(self.ip if self.ip is not None else -1), self.founded or 9999, self.name.lower())

    def day_list(self):
        return [d.strip().lower() for d in self.days.split(",") if d.strip()]


PLACES = [P(r) for r in D["places"]]
REST = [p for p in PLACES if not p.venue]
FISH = sorted([p for p in REST if p.hc and p.tags & FISHFRY], key=P.featured_key)
SUP = sorted([p for p in REST if p.hc and p.tags & SUPPER], key=P.featured_key)
CUST = sorted([p for p in REST if p.hc and p.tags & CUSTARD and not p.chain], key=P.featured_key)
BOILS = sorted([p for p in REST if p.hc and p.tags & BOIL], key=P.featured_key)
# icons are hand-picked, so a cheese shop or sausage maker among them keeps its Icons row and its own page
ICONS = [p for p in PLACES if p.ip is not None and (not p.venue or p.hc)]
CHECKED_PLACES = sorted([p for p in PLACES if p.hc and (not p.venue or p.ip is not None)], key=lambda p: (p.city, p.name.lower(), p.id))

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
# Region pages. The rule: a place belongs to the region (or county) its map point falls in, using the county lists above.
REGION_PAGES = {   # slug: (page name, how it's defined, counties)
    "northwoods": ("Northwoods", "Northwoods and Lake Superior", REGIONS["Northwoods and Lake Superior"]),
    "western-wisconsin": ("Western Wisconsin", "Western Wisconsin", REGIONS["Western Wisconsin"]),
    "central-wisconsin": ("Central Wisconsin", "Central Wisconsin", REGIONS["Central Wisconsin"]),
    "door-county": ("Door County", None, "Door"),
}


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


for p in PLACES:
    p.county = county(p)
    p.region = REGION_OF.get(p.county) if p.county else None


def region_page_of(p):
    for k, (_, region, counties) in REGION_PAGES.items():
        if (region and p.region == region) or (not region and p.county in counties.replace("_", " ").split()):
            return k
    return None


# ---------------------------------------------------------------- html helpers
e = html.escape


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("'", "").replace("’", "")).strip("-")


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def join_and(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def oldest_of(ps):
    """The places tied for the earliest verified founding year, as linked HTML ("A in X and B in Y"), plus that year."""
    dated = [p for p in ps if p.founded]
    if not dated:
        return None, None, 0
    y = min(p.founded for p in dated)
    top = sorted([p for p in dated if p.founded == y], key=lambda p: p.name.lower())
    link = lambda p: f'<a href="{place_url(p)}">{e(p.name)}</a>' if p.slug else e(p.name)
    return join_and([f"{link(p)} in {e(p.city)}" for p in top]), y, len(top)


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def cheese_svg(size=None, rx=12):
    """The brand mark, a wedge of cheese on green: the same geometry as scripts/make-brand.swift, in a 64-unit box."""
    s, x, y, w = 64.0, 64 * .15, 64 * .26, 64 * .70
    h, back = w * .40, w * .34
    n = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    Y = lambda v: n(s - v)
    holes = [(0.17, 0.52, 0.085), (0.46, 0.30, 0.06), (0.74, 0.60, 0.10), (0.58, 0.78, 0.045), (0.30, 0.18, 0.04), (1.0, 0.25, 0.07), (0.0, 0.85, 0.05)]
    dims = f' width="{size}" height="{size}" aria-hidden="true" focusable="false"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"{dims}>'
            f'<rect width="64" height="64" rx="{rx}" fill="#203731"/>'
            f'<path d="M{n(x)} {Y(y + h)}H{n(x + w)}L{n(x + w * .30)} {Y(y + h + back)}Z" fill="#FFD45E"/>'
            f'<clipPath id="wedge"><rect x="{n(x)}" y="{Y(y + h)}" width="{n(w)}" height="{n(h)}"/></clipPath>'
            f'<rect x="{n(x)}" y="{Y(y + h)}" width="{n(w)}" height="{n(h)}" fill="#FFB612"/>'
            f'<g clip-path="url(#wedge)" fill="#203731">'
            + "".join(f'<circle cx="{n(x + w * hx)}" cy="{Y(y + h * hy)}" r="{n(w * r)}"/>' for hx, hy, r in holes)
            + f'</g><ellipse cx="{n(x + w * .5)}" cy="{Y(y + h + back * .30 + w * .025)}" rx="{n(w * .06)}" ry="{n(w * .025)}" fill="#203731"/>'
            f'<rect x="{n(x)}" y="{Y(y + h)}" width="{n(w)}" height="{n(w * .012)}" fill="#E09A00"/></svg>')


LOGO = cheese_svg(30, rx=14)

CSS = """
  :root {
    --bg: #fbfaf6; --surface: #fff; --surface2: #f3f1ea; --rule: #e3e0d6;
    --ink: #16211d; --ink2: #33443d; --muted: #53665b;
    --green: #203731; --green2: #2d5242; --on-green: #fff; --gold: #ffb612; --goldsoft: #ffe7a8; --on-gold: #16211d;
    --dot: #203731; --water: #cfe3ea; --county: rgba(83,102,91,.35);
    --radius: 16px;
    --text: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
    --display: "Avenir Next Condensed", "HelveticaNeue-CondensedBold", "Arial Narrow", system-ui, sans-serif;
    color-scheme: light dark;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #111815; --surface: #18221e; --surface2: #1f2b26; --rule: #2c3a34; --ink: #f2f1ea; --ink2: #d5d9d2; --muted: #a9b7ae;
      --green: #9fd3b8; --green2: #7fbf9f; --on-green: #10201a; --dot: #9fd3b8; --water: #10303b; --county: rgba(169,183,174,.35); }
  }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  @media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 var(--text); -webkit-font-smoothing: antialiased; }
  a { color: var(--green); text-underline-offset: 2px; }
  /* the gold ring alone is 1.7:1 on the light page; the green ring inside it gives the focus indicator 3:1 or more in both schemes */
  a:focus-visible, summary:focus-visible, button:focus-visible, select:focus-visible, input:focus-visible { outline: 3px solid var(--gold); outline-offset: 3px; border-radius: 6px; box-shadow: 0 0 0 3px var(--green); }
  .skip { position: absolute; left: -9999px; top: 0; background: var(--gold); color: var(--on-gold); padding: 10px 14px; font-weight: 700; z-index: 30; }
  .skip:focus { left: 8px; top: 8px; }
  .vh { position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 20px; }
  header.site { display: flex; align-items: center; justify-content: space-between; gap: 6px 12px; padding: 12px 0; border-bottom: 4px solid var(--gold); }
  .logo { display: inline-flex; align-items: center; gap: 10px; min-height: 44px; font: 800 22px/1 var(--display); text-transform: uppercase; letter-spacing: .01em; color: var(--green); text-decoration: none; }
  header.site nav { display: flex; flex-wrap: wrap; gap: 0 10px; justify-content: flex-end; }
  header.site nav a, footer nav a, nav.crumbs a { display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; }
  header.site nav a { color: var(--ink2); text-decoration: none; font-size: 15px; }
  header.site nav a:hover { color: var(--green); text-decoration: underline; }
  h1, h2 { font-family: var(--display); font-weight: 800; color: var(--green); letter-spacing: -.005em; }
  h1 { font-size: clamp(36px, 7.5vw, 56px); line-height: 1.02; margin: 0 0 16px; text-transform: uppercase; overflow-wrap: anywhere; }
  .kicker { font: 700 15px/1.4 var(--text); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin: 0 0 12px; }
  h2 { font-size: 32px; line-height: 1.1; margin: 0 0 10px; }
  h3 { font-size: 18px; margin: 0; line-height: 1.3; }
  .lede { font-size: 19px; color: var(--ink2); margin: 0 0 26px; }
  .hero { padding: 40px 0 28px; }
  section { padding: 36px 0; border-top: 1px solid var(--rule); }
  section.hero { border: 0; }
  .sub { color: var(--ink2); margin: 0 0 22px; }
  .cta-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 10px; min-height: 44px; background: var(--gold); color: var(--on-gold); font-weight: 700; padding: 13px 20px; border-radius: 14px; text-decoration: none; font-size: 17px; line-height: 1.2; }
  .btn svg { width: 22px; height: 22px; }
  .btn-ghost { background: transparent; color: var(--green); border: 2px solid var(--green); }
  .store-badge { display: inline-flex; min-height: 44px; align-items: center; }
  .pill { font-size: 14px; color: var(--muted); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 28px 0 0; padding: 0; list-style: none; }
  .stats li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px; }
  .stats b { display: block; font: 800 30px/1 var(--display); color: var(--green); }
  .stats span { font-size: 14px; color: var(--muted); }
  .steps { display: grid; gap: 12px; list-style: none; margin: 0; padding: 0; }
  .step { display: flex; gap: 14px; background: var(--surface); border: 1px solid var(--rule); border-radius: var(--radius); padding: 18px; }
  .step .n { flex: 0 0 32px; height: 32px; border-radius: 50%; background: var(--gold); color: var(--on-gold); font-weight: 800; display: grid; place-items: center; }
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
  .cities a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--rule); background: var(--surface); text-decoration: none; color: var(--ink); font-size: 15px; }
  .cities a:hover { border-color: var(--green); }
  details { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 2px 18px; margin-bottom: 10px; }
  summary { cursor: pointer; padding: 14px 0; font-weight: 600; list-style: none; display: flex; justify-content: space-between; gap: 12px; }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "+"; color: var(--green); font-weight: 800; }
  details[open] summary::after { content: "\\2013"; }
  details p { margin: 0 0 16px; color: var(--ink2); }
  .final { text-align: center; }
  .final .cta-row { justify-content: center; }
  nav.crumbs { font-size: 14px; color: var(--muted); padding: 6px 0 0; }
  nav.crumbs ol { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 0 6px; }
  nav.crumbs li { display: inline-flex; align-items: center; min-height: 44px; }
  nav.crumbs li + li::before { content: "/"; margin-right: 6px; color: var(--muted); }
  nav.crumbs a { color: var(--muted); }
  .places { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
  .places li { background: var(--surface); border: 1px solid var(--rule); border-radius: 14px; padding: 14px 16px; min-width: 0; overflow-wrap: anywhere; scroll-margin-top: 12px; }
  .places h3 a { display: block; padding: 11px 0; margin: -11px 0; text-decoration: none; }
  .places h3 a:hover { text-decoration: underline; }
  .places .where { margin: 2px 0 0; font-size: 15px; color: var(--muted); }
  .places .facts { margin: 8px 0 0; font-size: 15px; color: var(--ink2); }
  .places .facts b { color: var(--ink); font-weight: 600; }
  .places .note { margin: 6px 0 0; font-size: 15px; color: var(--ink2); }
  .places .link { font-size: 15px; margin: 2px 0 -8px; }
  .places .link a, .near a, .toc a, .plinks a, td a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; }
  .tag { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; background: var(--goldsoft); color: var(--on-gold); border-radius: 6px; padding: 1px 6px; margin-right: 4px; }
  .toc { columns: 2; padding-left: 20px; margin: 0; }
  .near, .plist { list-style: none; padding: 0; margin: 0; }
  .plist { columns: 2; column-gap: 24px; }
  .plist li { break-inside: avoid; padding: 2px 0; }
  .plist a { display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; font-weight: 600; }
  .plist span { display: block; font-size: 14px; color: var(--muted); margin: -8px 0 4px; }
  .near span { display: block; font-size: 14px; color: var(--muted); margin: -8px 0 6px; }
  .actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 6px 0 0; }
  .actions .btn { font-size: 16px; padding: 10px 16px; }
  dl.facts { display: grid; grid-template-columns: max-content 1fr; gap: 10px 18px; margin: 0 0 18px; }
  dl.facts dt { font-weight: 700; color: var(--ink); }
  dl.facts dd { margin: 0; color: var(--ink2); }
  dl.facts ul { margin: 0; padding-left: 18px; }
  .addr { font-size: 17px; color: var(--ink2); margin: 0 0 14px; }
  .qa h3 { margin: 22px 0 6px; font-size: 19px; }
  .qa p { margin: 0 0 10px; color: var(--ink2); }
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--rule); }
  td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
  .fine { font-size: 14px; color: var(--muted); }
  .legal h2 { font-size: 26px; margin-top: 28px; }
  .legal p, .legal li { color: var(--ink2); }
  .notice { white-space: pre-wrap; font-size: 14px; color: var(--ink2); background: var(--surface); border: 1px solid var(--rule); border-radius: 12px; padding: 14px; overflow-wrap: anywhere; }
  footer { padding: 24px 0 56px; color: var(--muted); font-size: 14px; border-top: 1px solid var(--rule); margin-top: 20px; }
  footer nav { display: flex; flex-wrap: wrap; gap: 0 18px; }
  footer a { color: var(--muted); }
  footer p { margin: 12px 0 0; }
  @media (max-width: 600px) {
    .grid2 { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
    .toc, .plist { columns: 1; }
    header.site { flex-direction: column; align-items: flex-start; }
    header.site nav { justify-content: flex-start; }
    dl.facts { grid-template-columns: 1fr; gap: 2px; }
    dl.facts dd { margin-bottom: 10px; }
  }
"""

# ---------------------------------------------------------------- structured data shared by every page
ORG_ID, PERSON_ID, SITE_ID = f"{DOMAIN}/#org", f"{DOMAIN}/about.html#nicholas-soderstrom", f"{DOMAIN}/#website"
BASE_LD = {"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "@id": ORG_ID, "name": BRAND, "url": f"{DOMAIN}/",
     "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/icon-512.png", "width": 512, "height": 512}, "founder": {"@id": PERSON_ID},
     "email": EMAIL, "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL, "availableLanguage": "en"},
     # the Eats Ranked hub lists this site as a subOrganization; say so from this side too
     "parentOrganization": {"@type": "Organization", "@id": "https://eatsranked.com/#organization", "name": "Eats Ranked",
                            "url": "https://eatsranked.com/"}},
    {"@type": "Person", "@id": PERSON_ID, "name": AUTHOR, "url": f"{DOMAIN}/about.html"},
    {"@type": "WebSite", "@id": SITE_ID, "name": BRAND, "alternateName": ["WI Eats", "Wisconsin Eats app"], "url": f"{DOMAIN}/",
     "inLanguage": "en", "publisher": {"@id": ORG_ID}}]}


def jsonld(obj):
    # "<", ">" and "&" as \u escapes: a place name containing "</script>" can't end the block early
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">' + raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") + "</script>"


def crumbs(trail):
    """trail: [(name, url)] ending with the current page."""
    items = "".join(f'<li><a href="{u}">{e(n)}</a></li>' if i < len(trail) - 1 else f'<li aria-current="page">{e(n)}</li>'
                    for i, (n, u) in enumerate(trail))
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": DOMAIN + u} for i, (n, u) in enumerate(trail)]}
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{items}</ol></nav>', ld


STORE_NOTE = "No charge, on iPhone and iPad." if APP_STORE_URL else "No charge, on iPhone and iPad. App Store release pending."


def store_button(label="Get early access"):
    if APP_STORE_URL:   # Apple's own badge artwork, unaltered (see APP_STORE_URL above)
        return (f'<a class="store-badge" href="{e(APP_STORE_URL)}" rel="noopener">'
                f'<img src="{APP_STORE_BADGE}" alt="Download on the App Store" width="120" height="40"></a>')
    return (f'<a class="btn store-btn" href="mailto:{EMAIL}?subject=Wisconsin%20Eats%20early%20access&amp;body=Send%20me%20the%20TestFlight%20link.">'
            f'<span>{label}</span></a>')   # no Apple logo: Apple allows it only in its own badge artwork


def cta(extra=""):
    return f'<div class="cta-row">{store_button()}{extra}<span class="pill">{STORE_NOTE}</span></div>'


def sha(s):
    return "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"


def add_csp(doc):
    """A strict CSP from hashes of this page's own inline <script> and <style> blocks (JSON-LD is data and isn't run)."""
    assert not re.search(r"<script(?![^>]*application/ld\+json)[^>]+>", doc), "only plain inline <script> and JSON-LD are allowed"
    assert not re.search(r"<[a-z][^>]*\sstyle=", doc), "inline style attributes would be blocked by the CSP"
    assert not re.search(r"<[a-z][^>]*\son[a-z]+=", doc), "inline event handlers would be blocked by the CSP"
    scripts = re.findall(r"<script>(.*?)</script>", doc, re.S)
    styles = re.findall(r"<style>(.*?)</style>", doc, re.S)
    csp = (f"default-src 'self'; script-src {' '.join(map(sha, scripts)) or chr(39) + 'none' + chr(39)}; "
           f"style-src {' '.join(map(sha, styles)) or chr(39) + 'none' + chr(39)}; img-src 'self' data:; connect-src 'self'; "
           "object-src 'none'; base-uri 'none'; form-action 'none'")
    return doc.replace("<!--csp-->", f'<meta http-equiv="Content-Security-Policy" content="{csp}">', 1)


PAGES = []              # (path, lastmod) for the sitemap
TITLES, DESCS = {}, {}


def page(path, title, desc, body, lds=(), robots="index,follow,max-image-preview:large", og_alt=None, extra_css="", head_extra="",
         after="", published=SITE_LAUNCHED, lastmod=None):
    is404 = path == "404.html"
    if not is404:
        assert 50 <= len(title) <= 60, (path, len(title), title)
        assert 140 <= len(desc) <= 160, (path, len(desc), desc)
        assert title not in TITLES, ("duplicate title", path, TITLES[title])
        assert desc not in DESCS, ("duplicate description", path, DESCS[desc])
        TITLES[title], DESCS[desc] = path, path
    assert body.count("<h1") == 1, path
    url = DOMAIN + "/" + ("" if path == "index.html" else path.removesuffix("index.html"))
    og_alt = og_alt or f"{BRAND}: {TAGLINE}. Wisconsin restaurants, with hand-checked fish fries, supper clubs and custard stands."
    ld = "\n".join(jsonld(x) for x in (BASE_LD, *lds))
    where = "" if is404 else f'<link rel="canonical" href="{url}">\n'
    og_url = "" if is404 else f'<meta property="og:url" content="{url}">\n'
    # Smart App Banner: live once the app is (APP_STORE_URL); until then the SEO spec's commented placeholder, with the real app id
    banner = (f'<meta name="apple-itunes-app" content="app-id={APP_ID}">\n' if APP_STORE_URL else
              f'<!-- <meta name="apple-itunes-app" content="app-id={APP_ID}"> goes live with the app: set APP_STORE_URL in scripts/make-site.py -->\n')
    doc = f"""<!DOCTYPE html>
<html lang="en" data-base="{BASE}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!--csp-->
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{where}<meta name="robots" content="{robots}">
<meta name="theme-color" content="#203731">
{banner}<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
{og_url}<meta property="og:type" content="{'website' if path == 'index.html' else 'article'}">
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
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<style>{CSS}{extra_css}</style>
{head_extra}{ld}
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
      <a href="/cities/">Cities</a>
      <a href="/explore/">Search</a>
    </nav>
  </header>
{body}
  <footer>
    <nav aria-label="Footer">
      <a href="/">{BRAND} app</a>
      <a href="/explore/">Search Wisconsin restaurants</a>
      <a href="/wisconsin-fish-fry.html">Fish fry guide</a>
      <a href="/wisconsin-lent-fish-fry.html">Lent fish fry</a>
      <a href="/wisconsin-supper-clubs.html">Supper clubs</a>
      <a href="/wisconsin-frozen-custard.html">Frozen custard</a>
      <a href="/cities/">Cities and regions</a>
      <a href="/about.html">About and sources</a>
      <a href="/privacy.html">Privacy</a>
      <a href="/terms.html">Terms</a>
      <a href="mailto:{EMAIL}">Email us</a>
    </nav>
    <p>Place data: hand-checked research by {BRAND} (checked {HAND_CHECKED}); Overture Maps Foundation places data (CDLA Permissive 2.0), including data from Foursquare (Apache 2.0) and AllThePlaces (CC0 1.0); © OpenStreetMap contributors (ODbL); City of Milwaukee Open Data; Public Health Madison &amp; Dane County. Restaurant data as of {long_date(BUILD_DATE)}. Not affiliated with or endorsed by any restaurant, team, chain or government agency. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Places open and close, so check before you go.</p>
    <p>© {BUILD.year} {BRAND}, an independent app by {AUTHOR}. Part of <a href="https://eatsranked.com/">Eats Ranked</a>, restaurant apps state by state.</p>
  </footer>
</div>
{after}</body>
</html>
"""
    if BASE:   # served under /wisconsin-eats/: every root-relative link and asset gets the prefix
        doc = re.sub(r'(href|src|srcset)="/', rf'\1="{BASE}/', doc)
    doc = add_csp(doc)
    os.makedirs(os.path.dirname(f"{DOCS}/{path}"), exist_ok=True)
    open(f"{DOCS}/{path}", "w").write(doc)
    if not is404:
        PAGES.append((path, lastmod or modified(published)))
    return path


def article_ld(url, headline, desc, published=SITE_LAUNCHED):
    return {"@context": "https://schema.org", "@type": "Article", "headline": headline, "description": desc,
            "datePublished": published, "dateModified": modified(published), "inLanguage": "en", "mainEntityOfPage": url,
            "image": f"{DOMAIN}/og.png", "author": {"@id": PERSON_ID}, "publisher": {"@id": ORG_ID}, "isPartOf": {"@id": SITE_ID}}


def fit(options, lo, hi):
    for o in options:
        if lo <= len(o) <= hi:
            return o
    raise ValueError(f"nothing fits {lo}-{hi}: {[(len(o), o) for o in options]}")


# ---------------------------------------------------------------- place pages: slugs first, so every list can link to them
def place_path(p):
    return f"places/{p.slug}.html"


def place_url(p):
    return "/" + place_path(p)


_groups = defaultdict(list)
for p in CHECKED_PLACES:
    _groups[slug(f"{p.name} {p.city or 'wisconsin'}")].append(p)
for base, ps in _groups.items():
    if len(ps) == 1:
        ps[0].slug = base
        continue
    with_addr = Counter(f"{base}-{slug(p.addr)}" for p in ps)
    for p in ps:    # every member of a clash gets the same treatment, so slugs don't depend on order
        s = f"{base}-{slug(p.addr)}"
        p.slug = s if with_addr[s] == 1 and p.addr else f"{base}-{p.id[:6]}"
assert len({p.slug for p in CHECKED_PLACES}) == len(CHECKED_PLACES)


def short_kind(p):
    return join_and([k for bit, k in ((SUPPER, "supper club"), (FISHFRY, "fish fry"), (CUSTARD, "custard"), (BOIL, "fish boil")) if p.tags & bit]) or (
        "James Beard honoree" if p.h & 15 else "icon" if p.ip is not None else f"since {p.founded}" if p.founded else "hand-checked")


LISTED = set()     # ids of places some guide, city or region page links to; the cities hub links the rest, so no place page is an orphan


class Lister:
    """Renders place cards for one page; only a place's first card on a page gets its id anchor."""

    def __init__(self):
        self.seen = set()

    def item(self, p, extra=None):
        LISTED.add(p.id)
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
        where = ", ".join(x for x in (p.addr, p.city) if x)
        if extra:
            where += f" · {extra}"
        anchor = f' id="{p.slug}"' if p.slug and p.slug not in self.seen else ""
        if p.slug:
            self.seen.add(p.slug)
        name = f'<a href="{place_url(p)}">{e(p.name)}</a>' if p.slug else e(p.name)
        out = [f"<li{anchor}><h3>{name}</h3>", f'<p class="where">{e(where)}</p>']
        if kinds:
            out.append('<p class="facts">' + "".join(f'<span class="tag">{k}</span>' for k in kinds) + (" " + " · ".join(facts) if facts else "") + "</p>")
        elif facts:
            out.append('<p class="facts">' + " · ".join(facts) + "</p>")
        if p.note:
            out.append(f'<p class="note">{e(p.note)}</p>')
        if p.site:
            host = re.sub(r"^https?://(www\.)?", "", p.site, flags=re.I).split("/")[0]
            out.append(f'<p class="link"><a href="{e(p.site)}" rel="noopener nofollow">{e(host)}</a></p>')
        out.append("</li>")
        return "".join(out)

    def items(self, ps, extra=lambda p: None):
        return "".join(self.item(p, extra(p)) for p in ps)


def restaurant_ld(p, url=None):
    x = {"@type": "Restaurant", "name": p.name,
         "address": {"@type": "PostalAddress", "streetAddress": p.addr, "addressLocality": p.city, "addressRegion": "WI", "addressCountry": "US"}}
    if url:
        x = {"@context": "https://schema.org", "@id": url + "#place", **x, "mainEntityOfPage": url}
    if p.zip:
        x["address"]["postalCode"] = p.zip
    if p.lat is not None:
        x["geo"] = {"@type": "GeoCoordinates", "latitude": round(p.lat, 5), "longitude": round(p.lon, 5)}
    if p.site:
        x["url"] = p.site
    if p.tel:
        x["telephone"] = p.tel.removeprefix("tel:")
    if p.founded:
        x["foundingDate"] = str(p.founded)
    cuisine = [c for c in (p.cuisine if p.cuisine not in ("Other", "Restaurant", "American & Other") else None,
                           "Fish fry" if p.tags & FISHFRY else None, "Frozen custard" if p.tags & CUSTARD else None) if c]
    if cuisine:
        x["servesCuisine"] = cuisine if len(cuisine) > 1 else cuisine[0]
    return x


def item_list(name, places, url):
    # minimal entries: each place's own page carries its full Restaurant markup
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "url": url, "numberOfItems": len(places),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": p.name, "url": DOMAIN + place_url(p)}
                                for i, p in enumerate(places) if p.slug]}


# ---------------------------------------------------------------- counts shared by several pages
N_REST = len(REST)
N_TOWNS = len({p.city for p in REST if p.city})
FISH_PREFIX = r"^(lake|walleyed|yellow|icelandic|atlantic|north atlantic|alaskan|fresh|beer[- ]battered|breaded|baked|broiled|fried)\s+"
FISH_ALIAS = {"walleye pike": "walleye", "blue gill": "bluegill", "lake perch": "perch"}


def fish_words(ps):
    c = Counter()
    for p in ps:
        for f in {FISH_ALIAS.get(f, f) for f in (re.sub(FISH_PREFIX, "", x.strip().lower()) for x in p.fish.split(",") if x.strip())}:
            c[f] += 1
    # ties in alphabetical order: most_common() keeps insertion order for ties, and a set's order changes with every run's hash seed
    return Counter(dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))))


FISH_WORDS = fish_words(FISH)
N_FISH_KNOWN = sum(1 for p in FISH if p.fish)
OTHER_DAYS = [p for p in FISH if p.day_list() and p.day_list() != ["friday"]]
NOT_ONLY_FRIDAY = len(OTHER_DAYS)
SERVES = {k: [p for p in FISH if re.search(rx, p.fish.lower())] for k, rx in
          (("perch", r"\bperch\b"), ("walleye", r"\bwalleye"), ("bluegill", r"\bblue ?gill"), ("cod", r"\bcod\b"), ("haddock", r"\bhaddock\b"))}


def side_count(word):
    return sum(1 for p in FISH if word in p.sides.lower())


def by_region(places):
    groups = defaultdict(list)
    for p in places:
        groups[p.region or "Elsewhere in Wisconsin"].append(p)
    order = list(REGIONS) + ["Elsewhere in Wisconsin"]
    return [(r, sorted(groups[r], key=lambda p: (p.city, p.name.lower()))) for r in order if groups.get(r)]


REGION_LINK = {region: k for k, (_, region, _) in REGION_PAGES.items() if region}


def region_sections(places, noun, lister):
    toc = '<ul class="toc">' + "".join(f'<li><a href="#{slug(r)}">{e(r)}</a> ({len(ps)})</li>' for r, ps in by_region(places)) + "</ul>"
    secs = []
    for r, ps in by_region(places):
        more = f' The <a href="/regions/{REGION_LINK[r]}.html">{e(REGION_PAGES[REGION_LINK[r]][0])} page</a> has the region\'s other guides too.' if r in REGION_LINK else ""
        secs.append(f'<section id="{slug(r)}" aria-labelledby="h-{slug(r)}"><h2 id="h-{slug(r)}">{e(r)}</h2>'
                    f'<p class="sub">{plural(len(ps), noun)}, by town.{more}</p><ol class="places">'
                    + lister.items(ps) + "</ol></section>")
    return toc, "\n".join(secs)


CITY_PAGES = ["Milwaukee", "Madison", "Green Bay", "Appleton", "Kenosha", "Eau Claire", "Racine", "Oshkosh",
              "La Crosse", "Sheboygan", "Waukesha", "Janesville", "Wisconsin Dells"]
CITY_CENTER = {}
for c in CITY_PAGES:
    here = [p for p in REST if p.city == c and p.lat is not None]
    CITY_CENTER[c] = (sorted(p.lat for p in here)[len(here) // 2], sorted(p.lon for p in here)[len(here) // 2])


def nearest_city(p):
    """The one city page a place belongs to: its own town's, else the nearest city page's. Returns (city, miles)."""
    if p.city in CITY_CENTER:
        return p.city, 0.0
    if p.lat is None:
        return None, None
    d, c = min((miles(CITY_CENTER[c], (p.lat, p.lon)), c) for c in CITY_PAGES)
    return c, d


for p in PLACES:
    p.home_city, p.city_miles = nearest_city(p)

RADIUS = {"fish": 12, "supper": 25, "custard": 12}
_center = {c: P({"id": "", "n": c, "la": la, "lo": lo}) for c, (la, lo) in CITY_CENTER.items()}
for _p in _center.values():
    _p.county = county(_p)
    _p.region = REGION_OF.get(_p.county)
CITY_REGION = {c: region_page_of(_p) for c, _p in _center.items()}


def city_url(c):
    return f"/cities/{slug(c)}.html"


def city_links():
    return '<ul class="cities">' + "".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in CITY_PAGES) + "</ul>"


def region_links():
    return '<ul class="cities">' + "".join(f'<li><a href="/regions/{k}.html">{e(v[0])}</a></li>' for k, v in REGION_PAGES.items()) + "</ul>"


# ---------------------------------------------------------------- Lent (computed, so the page is right every year)
def easter(y):   # anonymous Gregorian algorithm
    a, (b, c) = y % 19, divmod(y, 100)
    d, e_ = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e_ + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return datetime.date(y, month, day + 1)


LENT_YEAR = BUILD.year if easter(BUILD.year) >= BUILD else BUILD.year + 1
EASTER = easter(LENT_YEAR)
ASH_WEDNESDAY = EASTER - datetime.timedelta(days=46)
GOOD_FRIDAY = EASTER - datetime.timedelta(days=2)
LENT_FRIDAYS = [ASH_WEDNESDAY + datetime.timedelta(days=2 + 7 * k) for k in range(7)]
assert LENT_FRIDAYS[-1] == GOOD_FRIDAY and ASH_WEDNESDAY.weekday() == 2
if LENT_YEAR == 2027:
    assert (ASH_WEDNESDAY, GOOD_FRIDAY) == (datetime.date(2027, 2, 10), datetime.date(2027, 3, 26))


def short_date(d):
    return f"{d:%b} {d.day}"


written = []


# ---------------------------------------------------------------- favicons, licenses
open(f"{DOCS}/favicon.svg", "w").write(cheese_svg() + "\n")
Image.open(f"{DOCS}/brand/icon-1024.png").convert("RGBA").save(f"{DOCS}/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
os.makedirs(f"{DOCS}/licenses", exist_ok=True)
for f in ("Apache-2.0", "CDLA-Permissive-2.0", "Foursquare-NOTICE"):
    shutil.copyfile(f"{ROOT}/WisconsinEats/Resources/Licenses/{f}.txt", f"{DOCS}/licenses/{f}.txt")
FOURSQUARE_NOTICE = open(f"{ROOT}/WisconsinEats/Resources/Licenses/Foursquare-NOTICE.txt").read().strip()


# ---------------------------------------------------------------- fish fry guide
url = f"{DOMAIN}/wisconsin-fish-fry.html"
L = Lister()
top_fish = FISH_WORDS.most_common(6)
fish_line = ", ".join(f"{f} ({n})" for f, n in top_fish)
title = fit([f"Wisconsin Friday Fish Fry Guide: {len(FISH)} Places | {BRAND}", f"Wisconsin Fish Fry Guide: {len(FISH)} Places | {BRAND}",
             f"Wisconsin Friday Fish Fry: {len(FISH)} Checked Places"], 50, 60)
desc = fit([f"{len(FISH)} Wisconsin Friday fish fries, each checked open in {HAND_CHECKED}: the fish they serve, the days, the sides, by region and town. Free, no ratings.",
            f"{len(FISH)} Wisconsin Friday fish fries checked open in {HAND_CHECKED}, with the fish, days and sides, listed by region and town. Free, no ads, no ratings."], 140, 160)
toc, secs = region_sections(FISH, "fish fry", L)
nav, bc = crumbs([("Home", "/"), ("Wisconsin fish fry guide", "/wisconsin-fish-fry.html")])
cod, perch, walleye, bluegill = (len(SERVES[k]) for k in ("cod", "perch", "walleye", "bluegill"))
n_sides = sum(1 for p in FISH if p.sides)
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} guide · checked {HAND_CHECKED}</p>
    <h1>Wisconsin Friday fish fry guide</h1>
    <p class="lede">{len(FISH)} restaurants, taverns and supper clubs across Wisconsin that serve a regular Friday fish fry, each checked open in {HAND_CHECKED} against its own website, menu or recent local news. For each one: the fish, the days and the sides when the place says so.</p>
    {cta()}
  </section>
  <section id="about-fish-fry">
    <h2>What counts as a Wisconsin fish fry</h2>
    <p>A Friday fish fry is a plate of battered or breaded fish, usually cod, perch, walleye, haddock or bluegill, with coleslaw, rye bread and a choice of potato: fries, potato pancakes with applesauce, or German potato salad. Many taverns, supper clubs, bowling alleys and family restaurants serve it every Friday of the year, not just in Lent. Many also offer a broiled or baked choice and a fish sandwich.</p>
    <p>This list only includes places that serve one regularly. Lent-only church and Legion fries are left out, because their dates change every year. Seasonal Northwoods places are in when they post their season. For Lent {LENT_YEAR}, see the <a href="/wisconsin-lent-fish-fry.html">Lent fish fry page</a>, with the Lent dates and the places that serve perch, walleye or bluegill or fry on other days too.</p>
    <h2>What the {len(FISH)} fish fries serve</h2>
    <p>{N_FISH_KNOWN} of the {len(FISH)} list the fish they serve. Counting each fish once per place, the most common are {e(fish_line)}. {NOT_ONLY_FRIDAY} serve their fish fry on days other than Friday too; those days are listed with each place.</p>
    <p>Each place earned its spot with a 2025 or 2026 source, such as its own menu page, a dated post on its website, a local news story or its Travel Wisconsin listing. A tavern with no current source, a dead website, or a fish fry mentioned only in passing didn't make it. No review-site scores went into the list, and it is grouped by region and town rather than ranked. Fish fry days shift, in Lent especially, so call before you drive. Our sources are on the <a href="/about.html">about {BRAND}</a> page.</p>
    <p>On your phone, the {BRAND} app puts the nearest fish fry at the top and opens Apple Maps' place card for tonight's hours, photos and directions. After a supper club instead? Try the <a href="/wisconsin-supper-clubs.html">Wisconsin supper club guide</a>; for dessert, the <a href="/wisconsin-frozen-custard.html">frozen custard guide</a>.</p>
    <h2>Jump to a region</h2>
    {toc}
    <p class="fine">City pages: {", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in CITY_PAGES)}. Region pages: {", ".join(f'<a href="/regions/{k}.html">{e(v[0])}</a>' for k, v in REGION_PAGES.items())}.</p>
  </section>
  <section id="questions" class="qa">
    <h2>Fish fry questions</h2>
    <h3>Why does Wisconsin have a fish fry on Friday?</h3>
    <p>It grew out of the Catholic custom of not eating meat on Fridays. Until 1966, church rules in the United States called for no meat on every Friday of the year; today the requirement covers Ash Wednesday and the Fridays of Lent, for Catholics 14 and older. Wisconsin has large Catholic communities, many with German and Polish roots, and fish from Lake Michigan, Lake Superior and inland lakes. Taverns and supper clubs kept the Friday fish fry going all year.</p>
    <h3>Cod, perch, walleye or bluegill: what's the difference?</h3>
    <p>Cod and haddock are ocean fish with large, mild, flaky fillets. Yellow perch, walleye and bluegill are freshwater fish: perch fillets are small and sweet and usually come several to a plate, walleye fillets are thicker, and bluegill is a small panfish. Of the places in this guide that list their fish, {cod} serve cod, {perch} perch, {walleye} walleye and {bluegill} bluegill. The <a href="/wisconsin-lent-fish-fry.html#perch">perch</a>, <a href="/wisconsin-lent-fish-fry.html#walleye">walleye</a> and <a href="/wisconsin-lent-fish-fry.html#bluegill">bluegill</a> lists are on the Lent page.</p>
    <h3>Is the fish fry only on Friday?</h3>
    <p>Mostly. {NOT_ONLY_FRIDAY} of the {len(FISH)} places here list their fish fry on at least one other day as well, most often Wednesday. They are listed together on the <a href="/wisconsin-lent-fish-fry.html#other-days">Lent fish fry page</a>.</p>
    <h3>What comes with a fish fry?</h3>
    <p>Of the {n_sides} places here that list their sides, {side_count("slaw")} mention coleslaw, {side_count("rye")} rye bread and {side_count("potato pancake")} potato pancakes. Fries, a baked potato and potato salad are the other common choices.</p>
  </section>
{secs}
  </main>"""
written.append(page("wisconsin-fish-fry.html", title, desc, body,
                    [article_ld(url, "Wisconsin Friday fish fry guide", desc), bc, item_list("Wisconsin Friday fish fries", FISH, url)]))

# ---------------------------------------------------------------- supper club guide
url = f"{DOMAIN}/wisconsin-supper-clubs.html"
L = Lister()
sup_fish = sum(1 for p in SUP if p.tags & FISHFRY)
sup_old = sorted([p for p in SUP if p.founded], key=lambda p: (p.founded, p.name.lower()))
sup_pre1950 = sum(1 for p in sup_old if p.founded < 1950)
title = fit([f"Wisconsin Supper Clubs: {len(SUP)} Checked Places | {BRAND}", f"Wisconsin Supper Club Guide: {len(SUP)} Places | {BRAND}"], 50, 60)
desc = fit([f"{len(SUP)} Wisconsin supper clubs checked open in {HAND_CHECKED}, by region and town: founding years, Friday fish fries and what each is known for. Free, no ratings.",
            f"{len(SUP)} Wisconsin supper clubs checked open in {HAND_CHECKED}, listed by region and town with founding years and Friday fish fries. Free, no ads."], 140, 160)
toc, secs = region_sections(SUP, "supper club", L)
oldest_line = "; ".join(f'<a href="{place_url(p)}">{e(p.name)}</a> in {e(p.city)} ({p.founded})' for p in sup_old[:5])
nav, bc = crumbs([("Home", "/"), ("Wisconsin supper clubs", "/wisconsin-supper-clubs.html")])
o_names, o_year, o_n = oldest_of(SUP)
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} guide · checked {HAND_CHECKED}</p>
    <h1>Wisconsin supper club guide</h1>
    <p class="lede">{len(SUP)} Wisconsin supper clubs, each checked open in {HAND_CHECKED} against its own website, menu or recent local news, with its founding year when we could verify it and its Friday fish fry when it has one.</p>
    {cta()}
  </section>
  <section id="about-supper-clubs">
    <h2>The {len(SUP)} in numbers</h2>
    <p>{sup_fish} of the {len(SUP)} supper clubs also serve a Friday fish fry. {len(sup_old)} have a founding year we could verify, and {sup_pre1950} of those opened before 1950. The oldest on the list: {oldest_line}.</p>
    <p>To get on this list, a supper club needed a 2025 or 2026 source, such as its own site with a current menu or hours, a dated news story, or its Travel Wisconsin listing. Clubs we could trace only to an old website, a parked domain or a Facebook page that needs a login stayed off, even though some of them may still be open. No review-site scores went into it; the clubs are grouped by region and town, not ranked. Our sources are on the <a href="/about.html">about {BRAND}</a> page.</p>
    <p>The {BRAND} app sorts these clubs by how far they are from you and opens Apple Maps' card for current hours and photos. Most supper clubs serve dinner only, and many take a night or two off each week, so a call ahead saves a wasted drive. Friday plans? The <a href="/wisconsin-fish-fry.html">Wisconsin fish fry guide</a> has those.</p>
    <h2>Jump to a region</h2>
    {toc}
    <p class="fine">City pages: {", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in CITY_PAGES)}. Region pages: {", ".join(f'<a href="/regions/{k}.html">{e(v[0])}</a>' for k, v in REGION_PAGES.items())}.</p>
  </section>
  <section id="questions" class="qa">
    <h2>Supper club questions</h2>
    <h3>What is a Wisconsin supper club?</h3>
    <p>A dinner-only restaurant, often on a highway or a lake outside town, where the evening usually starts at the bar with a brandy old fashioned and goes on to a relish tray, prime rib or steak, and on Fridays a fish fry. Many are family-run for generations. There is no official definition; this list includes places that call themselves supper clubs or are widely known as one, such as on Ron Faiola's Wisconsin supper club list or Travel Wisconsin's supper club pages.</p>
    <h3>What is the oldest supper club in Wisconsin?</h3>
    <p>{f'Of the {len(sup_old)} supper clubs here with a founding year we could verify, the oldest {"is" if o_n == 1 else "are"} {o_names}, {"founded" if o_n == 1 else "all founded"} in {o_year}. Some clubs without a verified year may be older, so this answers for our list, not for the whole state.' if o_n else 'We have not verified a founding year for any supper club yet.'}</p>
    <h3>Do supper clubs have a fish fry?</h3>
    <p>Many do: {sup_fish} of the {len(SUP)} here also serve a Friday fish fry, and they are in the <a href="/wisconsin-fish-fry.html">fish fry guide</a> too.</p>
    <h3>What is on a relish tray?</h3>
    <p>It varies by club. The classic tray holds raw vegetables, pickles and a cheese spread with crackers, brought to the table before dinner.</p>
  </section>
{secs}
  </main>"""
written.append(page("wisconsin-supper-clubs.html", title, desc, body,
                    [article_ld(url, "Wisconsin supper club guide", desc), bc, item_list("Wisconsin supper clubs", SUP, url)]))

# ---------------------------------------------------------------- custard guide
url = f"{DOMAIN}/wisconsin-frozen-custard.html"
L = Lister()
cust_old = sorted([p for p in CUST if p.founded], key=lambda p: (p.founded, p.name.lower()))
title = fit([f"Wisconsin Frozen Custard Stands: {len(CUST)} Places | {BRAND}", f"Wisconsin Frozen Custard: {len(CUST)} Local Stands | {BRAND}",
             f"Wisconsin Frozen Custard Stands: {len(CUST)} Local Places"], 50, 60)
desc = fit([f"{len(CUST)} local frozen custard stands in Wisconsin, not the big chains, checked open in {HAND_CHECKED} and listed by region and town. Free app for iPhone and iPad.",
            f"{len(CUST)} independent Wisconsin frozen custard stands, checked open in {HAND_CHECKED} and listed by region and town, without the big chains. Free, no ads."], 140, 160)
toc, secs = region_sections(CUST, "custard stand", L)
cust_old_line = "; ".join(f'<a href="{place_url(p)}">{e(p.name)}</a> in {e(p.city)} ({p.founded})' for p in cust_old[:4])
nav, bc = crumbs([("Home", "/"), ("Wisconsin frozen custard", "/wisconsin-frozen-custard.html")])
o_names, o_year, o_n = oldest_of(CUST)
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} guide · checked {HAND_CHECKED}</p>
    <h1>Wisconsin frozen custard stands</h1>
    <p class="lede">{len(CUST)} local frozen custard stands across Wisconsin. The national chains are left out on purpose; they have their own apps.</p>
    {cta()}
  </section>
  <section id="about-custard">
    <h2>Custard, not soft serve</h2>
    <p>Frozen custard is ice cream made with egg yolk and churned slowly with little air, so it comes out dense and is served fresh, often with a flavor of the day. It is a Milwaukee-area tradition, and many stands around the state post a flavor calendar. Soft-serve and hard ice cream shops are not on this list unless they make custard.</p>
    <p>{len(cust_old)} of the {len(CUST)} stands have a founding year we could verify. The oldest: {cust_old_line}.</p>
    <p>Each stand here was checked open against a 2025 or 2026 source, such as its own flavor calendar or menu, or a dated news story. Soft-serve shops that don't make custard aren't included, and neither are chains with five or more Wisconsin locations. Plenty of stands shut for the winter, so look up the hours first. Our sources are on the <a href="/about.html">about {BRAND}</a> page.</p>
    <p>The {BRAND} app lists the stands nearest you first and links each one to Apple Maps for today's hours. A cone goes well after a <a href="/wisconsin-fish-fry.html">Friday fish fry</a> or a <a href="/wisconsin-supper-clubs.html">supper club</a> dinner.</p>
    <h2>Jump to a region</h2>
    {toc}
  </section>
  <section id="questions" class="qa">
    <h2>Custard questions</h2>
    <h3>What is the difference between frozen custard and ice cream?</h3>
    <p>Egg yolk. Under the federal standard for ice cream (21 CFR 135.110), ice cream has at least 10 percent milkfat, and one with at least 1.4 percent egg yolk solids by weight may be called frozen custard. Custard machines also tend to whip in less air, which is why custard is denser, and many stands serve it fresh from the machine rather than from a freezer case.</p>
    <h3>What is a flavor of the day?</h3>
    <p>Many stands make vanilla and chocolate every day plus one or two rotating flavors, and post the month's schedule on their site or social media. Check the stand's own calendar; flavors change.</p>
    <h3>What is the oldest custard stand in Wisconsin?</h3>
    <p>{f'Of the {len(cust_old)} stands here with a verified founding year, the oldest {"is" if o_n == 1 else "are"} {o_names}, {"founded" if o_n == 1 else "all founded"} in {o_year}. That answers for our list only; stands without a verified year may be older.' if o_n else 'We have not verified a founding year for any stand yet.'}</p>
  </section>
{secs}
  </main>"""
written.append(page("wisconsin-frozen-custard.html", title, desc, body,
                    [article_ld(url, "Wisconsin frozen custard stands", desc), bc, item_list("Wisconsin frozen custard stands", CUST, url)]))


# ---------------------------------------------------------------- Lent fish fry page
def plist(ps, show=lambda p: ""):
    return '<ul class="plist">' + "".join(
        f'<li><a href="{place_url(p)}">{e(p.name)}</a><span>{e(" · ".join(x for x in (p.city, show(p)) if x))}</span></li>'
        for p in sorted(ps, key=lambda p: (p.city, p.name.lower()))) + "</ul>"


url = f"{DOMAIN}/wisconsin-lent-fish-fry.html"
wed = [p for p in FISH if "wednesday" in p.day_list()]
title = fit([f"Wisconsin Lent Fish Fry {LENT_YEAR}: Dates & {len(FISH)} Fish Fries", f"Lent Fish Fry {LENT_YEAR} in Wisconsin: {len(FISH)} Places | {BRAND}",
             f"Wisconsin Lent Fish Fry Guide {LENT_YEAR} | {BRAND}"], 50, 60)
desc = fit([f"Lent {LENT_YEAR} runs from Ash Wednesday, {short_date(ASH_WEDNESDAY)}, to Good Friday, {short_date(GOOD_FRIDAY)}. Wisconsin fish fries checked open in {HAND_CHECKED}, with perch, walleye and bluegill lists.",
            f"Lent {LENT_YEAR} dates and Wisconsin fish fries checked open in {HAND_CHECKED}: places frying on other days, plus perch, walleye and bluegill fish fries."], 140, 160)
nav, bc = crumbs([("Home", "/"), ("Wisconsin fish fry guide", "/wisconsin-fish-fry.html"), (f"Lent fish fry {LENT_YEAR}", "/wisconsin-lent-fish-fry.html")])
rows = "".join(f"<tr><td>{'Good Friday' if d == GOOD_FRIDAY else f'Friday {i + 1} of Lent'}</td><td>{d:%A}, {long_date(d)}</td></tr>" for i, d in enumerate(LENT_FRIDAYS))
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · Lent {LENT_YEAR}</p>
    <h1>Wisconsin Lent fish fry guide, {LENT_YEAR}</h1>
    <p class="lede">Lent {LENT_YEAR} begins on Ash Wednesday, {long_date(ASH_WEDNESDAY)}, and its last Friday is Good Friday, {long_date(GOOD_FRIDAY)}, before Easter on {long_date(EASTER)}. These are the {len(FISH)} fish fries in our guide, each checked open in {HAND_CHECKED}, sorted for Lent: the ones that fry on other days too, and the ones that serve perch, walleye or bluegill.</p>
    {cta()}
  </section>
  <section id="dates">
    <h2>Lent {LENT_YEAR} fish fry Fridays</h2>
    <table><thead><tr><th scope="col">Friday</th><th scope="col">Date</th></tr></thead><tbody>{rows}</tbody></table>
    <p class="fine">Dates follow the Western (Gregorian) church calendar: Easter Sunday is {long_date(EASTER)} and Ash Wednesday falls 46 days before it.</p>
  </section>
  <section id="about-lent" class="qa">
    <h2>Fish fry in Lent</h2>
    <h3>Why fish in Lent?</h3>
    <p>In the United States, Catholics aged 14 and older are asked to abstain from meat on Ash Wednesday and on the Fridays of Lent, and fish doesn't count as meat. That is the root of the Friday fish fry, and during Lent many church halls, Legion posts and VFW halls run fish fries of their own.</p>
    <h3>What this page lists</h3>
    <p>The places in our <a href="/wisconsin-fish-fry.html">fish fry guide</a> serve a regular fish fry, not a Lent-only one. Lent-only church and Legion fries aren't in it, because their dates change every year; check your parish bulletin or local post. Some Northwoods places are seasonal and may still be closed in late winter, so check before you go.</p>
  </section>
  <section id="other-days">
    <h2>Fish fry not just on Friday</h2>
    <p class="sub">{plural(NOT_ONLY_FRIDAY, "place")} in our guide list a fish fry on other days too. {len(wed)} of them list Wednesday; check whether they serve on Ash Wednesday itself.</p>
    {plist(OTHER_DAYS, lambda p: p.days)}
  </section>
  <section id="perch">
    <h2>Perch fish fries</h2>
    <p class="sub">{plural(len(SERVES["perch"]), "place")} that list perch, often lake perch, among their fish.</p>
    {plist(SERVES["perch"])}
  </section>
  <section id="walleye">
    <h2>Walleye fish fries</h2>
    <p class="sub">{plural(len(SERVES["walleye"]), "place")} that list walleye.</p>
    {plist(SERVES["walleye"])}
  </section>
  <section id="bluegill">
    <h2>Bluegill fish fries</h2>
    <p class="sub">{plural(len(SERVES["bluegill"]), "place")} that list bluegill, a freshwater panfish.</p>
    {plist(SERVES["bluegill"])}
  </section>
  </main>"""
written.append(page("wisconsin-lent-fish-fry.html", title, desc, body,
                    [article_ld(url, f"Wisconsin Lent fish fry guide, {LENT_YEAR}", desc, PAGES_ADDED), bc], published=PAGES_ADDED))


# ---------------------------------------------------------------- city pages
def fish_sentence(ff, where):
    """What the fish fries in a set serve: "most often" only when one fish clearly leads."""
    fw = fish_words(ff).most_common()
    if not fw:
        return ""
    if fw[0][1] >= 2 and (len(fw) == 1 or fw[0][1] > fw[1][1]):
        second = [f for f, n in fw[1:] if n == fw[1][1]] if len(fw) > 1 else []    # a tie for second names every fish in it
        then = (f", then {e(second[0])} ({fw[1][1]})" if len(second) == 1 else
                f", then {join_and([e(f) for f in second])} ({fw[1][1]} each)" if 1 < len(second) <= 3 else "")
        return f"Among the {plural(len(ff), 'fish fry', 'fish fries')} {where}, the fish named most often is {e(fw[0][0])} ({fw[0][1]}){then}."
    return f"The {plural(len(ff), 'fish fry', 'fish fries')} {where} list {join_and([e(f) for f, _ in fw[:4]])}."


def city_paragraph(c, town, ff, sc, cu):
    """A few sentences that only this city's data can produce."""
    s = []
    kinds = Counter(p.cuisine for p in town if p.cuisine and p.cuisine not in ("Other", "Restaurant", "American & Other")).most_common(2)
    lead = f"Our list has {plural(len(town), 'place')} to eat and drink in {e(c)}"
    s.append(lead + (f"; the most common kinds are {e(kinds[0][0])} ({kinds[0][1]:,}) and {e(kinds[1][0])} ({kinds[1][1]:,})." if len(kinds) == 2 else "."))
    names, year, n = oldest_of(town)
    if n:
        s.append(f"The oldest with a verified founding year {'is' if n == 1 else 'are'} {names} ({year}).")
    s.append(fish_sentence(ff, "on this page"))
    other = [p for p in ff if p.day_list() and p.day_list() != ["friday"]]
    if other:
        s.append(f"{len(other)} of them {'serves' if len(other) == 1 else 'serve'} fish on days besides Friday.")
    jb = [p for p in town if p.h & 15]
    if jb:
        s.append(f"{plural(len(jb), 'place')} in {e(c)} {'has' if len(jb) == 1 else 'have'} a James Beard Foundation honor: an America's Classics award, a win, or a finalist or semifinalist nod.")
    names, year, n = oldest_of(sc)
    if n and sum(1 for p in sc if p.founded) >= 2:
        s.append(f"The oldest supper club on this page is {names}, founded in {year}." if n == 1 else
                 f"The oldest supper clubs on this page are {names}, all founded in {year}.")
    return " ".join(s)


city_stats = {}
for c in CITY_PAGES:
    town = [p for p in REST if p.city == c]
    n_town = len(town)

    def near(ps, radius):
        out = [p for p in ps if p.home_city == c and p.city_miles is not None and p.city_miles <= radius]
        return sorted(out, key=lambda p: (p.city != c, p.city_miles if p.city != c else 0, p.name.lower()))

    ff, sc, cu = near(FISH, RADIUS["fish"]), near(SUP, RADIUS["supper"]), near(CUST, RADIUS["custard"])
    icons = sorted([p for p in ICONS if p.city == c], key=lambda p: (-p.ip, p.name.lower()))   # incl. hand-picked shops (ICONS)
    oldest = sorted([p for p in town if p.founded], key=lambda p: (p.founded, p.name.lower()))[:10]
    cuis = Counter(p.cuisine for p in town if p.cuisine and p.cuisine not in ("Other", "Restaurant")).most_common(10)
    city_stats[c] = (n_town, len(ff), len(sc), len(cu))
    L = Lister()

    def dist(p, c=c):
        return None if p.city == c else f"{p.city_miles:.0f} mi from {c}"

    path = f"cities/{slug(c)}.html"
    url = DOMAIN + "/" + path
    title = fit([f"{c} Fish Fries, Supper Clubs & Restaurants | {BRAND}", f"{c} Fish Fry, Supper Clubs & Restaurants | {BRAND}",
                 f"{c} Fish Fries & Supper Clubs | {BRAND}", f"{c}, WI Fish Fries & Supper Clubs | {BRAND}",
                 f"{c}, WI Fish Fry, Supper Clubs & Restaurants", f"{c}, Wisconsin Fish Fries & Supper Clubs Guide",
                 f"{c}, Wisconsin Fish Fries, Supper Clubs & Restaurants"], 50, 60)
    desc = fit([f"Friday fish fries, supper clubs and custard stands in and near {c}, WI, checked open in {HAND_CHECKED}, plus local icons and the oldest places we could date.",
                f"Fish fries, supper clubs and custard in and near {c}, Wisconsin, checked open in {HAND_CHECKED}, with local icons and the oldest places we could date.",
                f"Friday fish fries, supper clubs and frozen custard in and near {c}, Wisconsin, checked open in {HAND_CHECKED}, plus local icons and old favorites.",
                f"Fish fries, supper clubs and custard in and near {c}, WI, checked open in {HAND_CHECKED}, with local icons and the oldest places we could date."], 140, 160)
    nav, bc = crumbs([("Home", "/"), ("Cities and regions", "/cities/"), (c, "/" + path)])
    counts = [x for x in (plural(len(ff), "Friday fish fry", "Friday fish fries"), plural(len(sc), "supper club"), plural(len(cu), "custard stand")) if not x.startswith("0 ")]
    parts = [f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · {e(c)}, Wisconsin</p>
    <h1>{e(c)} fish fries, supper clubs &amp; restaurants</h1>
    <p class="lede">{join_and(counts)} in {e(c)} and the towns closest to it, each checked open in {HAND_CHECKED}. The {BRAND} app lists {n_town:,} restaurants, cafés, taverns and bakeries in {e(c)} and sorts them by distance from you.</p>
    {cta()}
  </section>
  <section id="at-a-glance">
    <h2>{e(c)} at a glance</h2>
    <p>{city_paragraph(c, town, ff, sc, cu)}</p>
    <p class="fine">Each place nearby is listed on the page of the closest of our {len(CITY_PAGES)} city pages, so a town between two cities appears once. See <a href="/cities/">all cities and regions</a>.</p>
  </section>"""]
    if ff:
        parts.append(f'<section id="fish-fry"><h2>Friday fish fry in and near {e(c)}</h2><p class="sub">Places in {e(c)} first, then others within {RADIUS["fish"]} miles that are closer to {e(c)} than to another city page, closest first. Fish and days as each place lists them. The statewide <a href="/wisconsin-fish-fry.html">fish fry guide</a> has {len(FISH)}.</p><ol class="places">{L.items(ff, dist)}</ol></section>')
    if sc:
        parts.append(f'<section id="supper-clubs"><h2>Supper clubs near {e(c)}</h2><p class="sub">Supper clubs in {e(c)}, then others within {RADIUS["supper"]} miles that are closer to {e(c)} than to another city page. The statewide <a href="/wisconsin-supper-clubs.html">supper club guide</a> has {len(SUP)}.</p><ol class="places">{L.items(sc, dist)}</ol></section>')
    if cu:
        parts.append(f'<section id="custard"><h2>Frozen custard in and near {e(c)}</h2><p class="sub">Local stands, not the chains, within {RADIUS["custard"]} miles. The statewide <a href="/wisconsin-frozen-custard.html">custard guide</a> has {len(CUST)}.</p><ol class="places">{L.items(cu, dist)}</ol></section>')
    if icons:
        parts.append(f'<section id="icons"><h2>{e(c)} icons</h2><p class="sub">James Beard Award winners, finalists and semifinalists, and long-running local institutions, most honored first. Honors are from the James Beard Foundation\'s own award records and other named sources.</p><ol class="places">'
                     + L.items(icons) + "</ol></section>")
    if oldest:
        parts.append(f'<section id="oldest"><h2>Oldest places in {e(c)} we could date</h2><p class="sub">Oldest first, by the founding year on the place\'s own history page or in local news. A place we couldn\'t date isn\'t in this list, however old it may be.</p><ol class="places">'
                     + L.items(oldest) + "</ol></section>")
    if cuis:
        rows = "".join(f'<tr><td>{e(k)}</td><td class="n">{n:,}</td></tr>' for k, n in cuis)
        parts.append(f'<section id="cuisines"><h2>What {e(c)} eats</h2><p class="sub">The most common kinds of place among the {n_town:,} in {e(c)} on our list, from open map data and the city and county license lists.</p><table><thead><tr><th scope="col">Kind of place</th><th scope="col" class="n">Places</th></tr></thead><tbody>{rows}</tbody></table></section>')
    parts.append(f'<section id="more"><h2>More Wisconsin cities</h2>{city_links()}<p class="sub">Or by region:</p>{region_links()}</section>\n  </main>')
    uniq = list(dict.fromkeys(ff + sc + cu + icons + oldest))
    written.append(page(path, title, desc, "\n".join(parts),
                        [article_ld(url, f"{c} fish fries, supper clubs and restaurants", desc), bc,
                         item_list(f"Fish fries, supper clubs and custard near {c}", uniq, url)]))

# ---------------------------------------------------------------- region pages
region_stats = {}
for k, (name, region, counties) in REGION_PAGES.items():
    ps = [p for p in CHECKED_PLACES if region_page_of(p) == k]
    ff = [p for p in ps if p.tags & FISHFRY]
    sc = [p for p in ps if p.tags & SUPPER]
    cu = [p for p in ps if p.tags & CUSTARD and not p.chain]
    bo = [p for p in ps if p.tags & BOIL]
    rest = [p for p in ps if p not in ff + sc + cu + bo and (p.ip is not None or p.founded)]
    region_stats[k] = (len(ps), len(ff), len(sc), len(cu), len(bo))
    county_names = [x.replace("_", " ") for x in counties.split()]
    rule = (f"{join_and(county_names)} counties" if len(county_names) > 1 else f"{county_names[0]} County")
    path = f"regions/{k}.html"
    url = DOMAIN + "/" + path
    nice = f"{name} Wisconsin" if name == "Northwoods" else name
    where = "the Northwoods" if name == "Northwoods" else name     # "in the Northwoods", "in Door County"
    title = fit(([f"{nice} Fish Boils, Fish Fries & Supper Clubs | {BRAND}", f"{nice} Fish Boils, Fish Fries and Supper Clubs"] if bo else [])
                + [f"{nice} Fish Fries & Supper Clubs | {BRAND}", f"{name} Fish Fries & Supper Clubs | {BRAND}",
                   f"{nice} Fish Fries, Supper Clubs & Custard Guide", f"{nice} Fish Fries and Supper Clubs: A Checked Guide"], 50, 60)
    kinds_txt = join_and([x for x in (plural(len(ff), "fish fry", "fish fries"), plural(len(sc), "supper club"),
                                      plural(len(bo), "fish boil") if bo else "", plural(len(cu), "custard stand") if cu else "") if x])
    desc = fit([f"{kinds_txt} in {where}, Wisconsin, each checked open in {HAND_CHECKED}, with the fish, days, founding years and links. Free, no ads, no ratings.",
                f"{kinds_txt} in {where}, Wisconsin, each checked open in {HAND_CHECKED}, listed by town with the fish, days and founding years. Free.",
                f"{kinds_txt} in Wisconsin's {name}, each checked open in {HAND_CHECKED}, listed by town with fish, days and founding years. Free, no ads.",
                f"{kinds_txt} in {where}, each checked open in {HAND_CHECKED}, with the fish, days, founding years and links. A free Wisconsin guide, no ratings.",
                f"Fish fries, supper clubs and more in {where}, Wisconsin, each checked open in {HAND_CHECKED}, listed by town with the fish and days. Free, no ads."], 140, 160)
    nav, bc = crumbs([("Home", "/"), ("Cities and regions", "/cities/"), (name, "/" + path)])
    L = Lister()
    towns = Counter(p.city for p in ps).most_common(3)
    facts = [f"Our hand-checked lists have {plural(len(ps), 'place')} in {e(where)}"
             + (f"; the towns with the most are {join_and([f'{e(t)} ({n})' for t, n in towns])}." if len(towns) > 1 else ".")]
    names, year, n = oldest_of(ps)
    if n:
        facts.append(f"The oldest with a verified founding year {'is' if n == 1 else 'are'} {names} ({year}).")
    if ff:
        facts.append(fish_sentence(ff, "here"))
    secs = []
    for sid, h, lst, sub in (("fish-fry", "Friday fish fries", ff, "Fish and days as each place lists them, by town."),
                             ("supper-clubs", "Supper clubs", sc, "By town, with founding years when we could verify them."),
                             ("fish-boil", "Fish boils", bo, "The Door County-style fish boil: whitefish, potatoes and onions boiled outdoors over a wood fire, usually finished with a boil-over."),
                             ("custard", "Frozen custard", cu, "Local stands, not the chains."),
                             ("icons", "Icons and old favorites", rest, "Long-running and honored places that aren't in the lists above.")):
        if lst:
            secs.append(f'<section id="{sid}"><h2>{h} in {e(where)}</h2><p class="sub">{plural(len(lst), "place")}. {sub}</p><ol class="places">'
                        + L.items(sorted(lst, key=lambda p: (p.city, p.name.lower()))) + "</ol></section>")
    cities_here = [c for c in CITY_PAGES if CITY_REGION[c] == k]
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · region guide</p>
    <h1>{e(name)} fish fries, supper clubs &amp; more</h1>
    <p class="lede">{kinds_txt[0].upper() + kinds_txt[1:]} in {e(where)}, each checked open in {HAND_CHECKED} against a 2025 or 2026 source.</p>
    {cta()}
  </section>
  <section id="about-region">
    <h2>About this region</h2>
    <p>{" ".join(facts)}</p>
    <p class="fine">How we define it: {e(where[0].upper() + where[1:])} here means {e(rule)}; a place is in it when its map point falls inside {"one of those counties" if len(county_names) > 1 else "the county line"}.{" City pages here: " + ", ".join(f'<a href="{city_url(c)}">{e(c)}</a>' for c in cities_here) + "." if cities_here else ""} Statewide guides: <a href="/wisconsin-fish-fry.html">fish fry</a>, <a href="/wisconsin-supper-clubs.html">supper clubs</a>, <a href="/wisconsin-frozen-custard.html">custard</a>.</p>
  </section>
{chr(10).join(secs)}
  <section id="more"><h2>Other regions</h2>{region_links()}</section>
  </main>"""
    written.append(page(path, title, desc, body,
                        [article_ld(url, f"{name} fish fries, supper clubs and more", desc, PAGES_ADDED), bc,
                         item_list(f"Hand-checked places in {where}", sorted(set(ff + sc + cu + bo + rest), key=lambda p: (p.city, p.name.lower(), p.id)), url)],
                        published=PAGES_ADDED))

# ---------------------------------------------------------------- cities hub
nav, bc = crumbs([("Home", "/"), ("Cities and regions", "/cities/")])
rows = "".join(f'<tr><td><a href="{city_url(c)}">{e(c)}</a></td><td class="n">{s[1]}</td><td class="n">{s[2]}</td><td class="n">{s[3]}</td><td class="n">{s[0]:,}</td></tr>'
               for c, s in city_stats.items())
rrows = "".join(f'<tr><td><a href="/regions/{k}.html">{e(REGION_PAGES[k][0])}</a></td><td class="n">{s[1]}</td><td class="n">{s[2]}</td><td class="n">{s[3]}</td><td class="n">{s[4]}</td></tr>'
                for k, s in region_stats.items())
title = fit([f"Wisconsin Cities & Regions: Fish Fries & Supper Clubs | {BRAND}", f"Wisconsin Fish Fries & Supper Clubs by City | {BRAND}"], 50, 60)
desc = fit([f"Fish fries, supper clubs and custard stands in {len(CITY_PAGES)} Wisconsin cities and {len(REGION_PAGES)} regions, from Milwaukee to the Northwoods, each place checked open in {HAND_CHECKED}.",
            f"Fish fries, supper clubs and custard in {len(CITY_PAGES)} Wisconsin cities and {len(REGION_PAGES)} regions, each place checked open in {HAND_CHECKED}. Free, no ads."], 140, 160)
others = [p for p in CHECKED_PLACES if p.id not in LISTED]     # hand-checked places no guide, city or region page lists
more_places = (f'\n  <section id="more-places">\n    <h2>More hand-checked places</h2>\n    <p class="sub">{plural(len(others), "place")} on our hand-checked lists that aren\'t in a guide or on a city or region page, by town: icons, old favorites and shops, each checked open in {HAND_CHECKED}.</p>\n    {plist(others, short_kind)}\n  </section>'
               if others else "")
body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · by city and region</p>
    <h1>Wisconsin cities and regions</h1>
    <p class="lede">From Milwaukee to La Crosse and up to the Northwoods: {len(CITY_PAGES)} city pages and {len(REGION_PAGES)} region pages of fish fries, supper clubs and custard stands, every place checked open in {HAND_CHECKED}. A town between two cities shows up once, on the nearer city's page.</p>
  </section>
  <section id="cities">
    <h2>City pages</h2>
    <table><thead><tr><th scope="col">City</th><th scope="col" class="n">Fish fries</th><th scope="col" class="n">Supper clubs</th><th scope="col" class="n">Custard</th><th scope="col" class="n">Places on our list</th></tr></thead><tbody>{rows}</tbody></table>
  </section>
  <section id="regions">
    <h2>Region pages</h2>
    <table><thead><tr><th scope="col">Region</th><th scope="col" class="n">Fish fries</th><th scope="col" class="n">Supper clubs</th><th scope="col" class="n">Custard</th><th scope="col" class="n">Fish boils</th></tr></thead><tbody>{rrows}</tbody></table>
    <p class="fine">A region is a group of whole counties, named on its page. The statewide guides are sorted by region too: <a href="/wisconsin-fish-fry.html">fish fry</a>, <a href="/wisconsin-supper-clubs.html">supper clubs</a>, <a href="/wisconsin-frozen-custard.html">custard</a>.</p>
  </section>{more_places}
  </main>"""
written.append(page("cities/index.html", title, desc, body, [bc], published=PAGES_ADDED))


# ---------------------------------------------------------------- one page per hand-checked place
def kind_labels(p):
    """Title labels for a place, most specific first. A label the name already says ("... Supper Club") is skipped."""
    jb = "James Beard America's Classic" if p.h & 1 else "James Beard Award Winner" if p.h & 2 else "James Beard Finalist" if p.h & 4 else "James Beard Semifinalist" if p.h & 8 else None
    if p.tags & SUPPER and p.tags & FISHFRY:
        out = ["Supper Club & Friday Fish Fry", "Supper Club & Fish Fry", "Friday Fish Fry", "Fish Fry", "Supper Club"]
    elif p.tags & BOIL:
        out = ["Door County Fish Boil", "Fish Boil"]
    elif p.tags & FISHFRY and p.tags & CUSTARD:
        out = ["Fish Fry & Frozen Custard", "Fish Fry & Custard", "Friday Fish Fry"]
    elif p.tags & FISHFRY:
        out = ["Friday Fish Fry", "Fish Fry", "Wisconsin Fish Fry"]
    elif p.tags & SUPPER:
        out = ["Wisconsin Supper Club", "Supper Club"]
    elif p.tags & CUSTARD:
        out = ["Frozen Custard Stand", "Frozen Custard", "Custard"]
    else:
        out = [x for x in (jb, f"Founded in {p.founded}" if p.founded else None, "Wisconsin Icon" if p.ip is not None else None,
                           "Local Icon" if p.ip is not None else None, f"Since {p.founded}" if p.founded else None) if x]
    low = p.name.lower()
    keep = [k for k in out if not any(w in low for w in ("supper club", "custard", "fish fry", "fish boil") if w in k.lower())]
    return keep or out


def place_title(p):
    city = p.city or "Wisconsin"
    locs = [f"{p.name}, {city}", f"{p.name}, {city}, WI", f"{p.name}, {city}, Wisconsin", f"{p.name} in {city}, Wisconsin"]
    sfxs = (f" | {BRAND}", "", " | WI Eats")
    opts = [f"{loc}: {k}{sfx}" for loc in locs for k in kind_labels(p) for sfx in sfxs]   # the town matters most, then the kind, then the brand
    opts += [f"{loc}{sfx}" for loc in locs for sfx in sfxs] + [f"{p.name}: {k}{sfx}" for k in kind_labels(p) for sfx in sfxs]
    good = [o for o in opts if 50 <= len(o) <= 60 and o not in TITLES]
    if not good:
        raise ValueError(f"no title fits for {p.name} ({p.city}): {[(len(o), o) for o in opts[:6]]}")
    return good[0]


def days_phrase(p):
    ds = p.day_list()
    if not ds or ds == ["friday"]:
        return "on Fridays"
    if len(ds) == 7:
        return "every day"
    if len(ds) >= 4:
        return f"{len(ds)} days a week"
    return "on " + join_and([d.capitalize() + "s" for d in ds])


def place_desc(p):
    city = p.city or "Wisconsin"
    leads = [f"{p.name} in {city}, Wisconsin,", f"{p.name} in {city}, WI,", f"{p.name} in {city}"]
    since = f", founded in {p.founded}," if p.founded else ""      # mid-sentence
    and_since = f" and was founded in {p.founded}" if p.founded else ""   # at the end
    fish = f" ({p.fish})" if p.fish else ""
    facts = []
    if p.tags & SUPPER and p.tags & FISHFRY:
        facts += [f"is a supper club{since} with a fish fry {days_phrase(p)}{fish}", f"is a supper club{since} with a fish fry {days_phrase(p)}", "is a supper club with a Friday fish fry"]
    elif p.tags & BOIL:
        facts += [f"serves a Door County-style fish boil{and_since}", "serves a Door County fish boil"]
    elif p.tags & FISHFRY:
        facts += [f"serves a fish fry {days_phrase(p)}{fish}{and_since}", f"serves a fish fry {days_phrase(p)}{fish}",
                  f"serves a fish fry {days_phrase(p)}{and_since}", f"serves a fish fry {days_phrase(p)}"]
    elif p.tags & SUPPER:
        facts += [f"is a supper club founded in {p.founded}" if p.founded else "is a supper club", "is a Wisconsin supper club"]
    elif p.tags & CUSTARD:
        facts += [f"serves frozen custard{and_since}", "serves frozen custard"]
    else:
        jb = "a James Beard America's Classic" if p.h & 1 else "a James Beard Award winner" if p.h & 2 else "a James Beard finalist" if p.h & 4 else "a James Beard semifinalist" if p.h & 8 else None
        facts += [x for x in ((f"is {jb}" if jb else None), (f"was founded in {p.founded}" if p.founded else None), "is one of our Wisconsin icons" if p.ip is not None else None) if x]
    links = join_and([x for x in ("address", "website" if p.site else "", "phone" if p.tel else "", "directions") if x])
    tails = [f"Checked open in {HAND_CHECKED} against a 2025 or 2026 source, with {links}.", f"Checked open in {HAND_CHECKED}, with {links}.",
             f"Hand-checked open in {HAND_CHECKED}, with {links} and nearby places.", f"Checked open in {HAND_CHECKED} against a 2025 or 2026 source.",
             f"Checked open in {HAND_CHECKED}.", f"Hand-checked in {HAND_CHECKED}: {links}, plus nearby fish fries and supper clubs."]
    opts = []
    if p.note:   # the research note is the most specific thing we can say; use it when it fits
        note = p.note.rstrip(".") + "."
        opts += [f"{p.name}, {city}: {note}", f"{p.name}, {city}: {note} Checked open in {HAND_CHECKED}.", f"{p.name} in {city}: {note} Hand-checked {HAND_CHECKED}."]
    opts += [f"{lead} {f}. {t}" for t in tails for f in facts for lead in leads]
    good = [o for o in opts if 140 <= len(o) <= 160 and o not in DESCS]
    if not good:
        raise ValueError(f"no description fits for {p.name} ({p.city}): {sorted({len(o) for o in opts})}")
    return good[0]


def apple_maps(p):
    return f"https://maps.apple.com/?q={quote(p.name)}&ll={p.lat:.5f},{p.lon:.5f}" if p.lat is not None else f"https://maps.apple.com/?q={quote(p.name + ', ' + p.addr + ', ' + p.city + ', WI')}"


def directions(p):
    return f"https://maps.apple.com/?daddr={p.lat:.5f},{p.lon:.5f}&dirflg=d" if p.lat is not None else apple_maps(p)


GUIDE_OF = [(FISHFRY, "/wisconsin-fish-fry.html", "Wisconsin fish fry guide", FISH), (SUPPER, "/wisconsin-supper-clubs.html", "Wisconsin supper clubs", SUP),
            (CUSTARD, "/wisconsin-frozen-custard.html", "Wisconsin frozen custard", CUST)]
GUIDE_MEMBERS = {u: {id(p) for p in ps} for _, u, _, ps in GUIDE_OF}
for p in CHECKED_PLACES:
    path = place_path(p)
    url = DOMAIN + "/" + path
    guides = [(u, n) for bit, u, n, _ in GUIDE_OF if p.tags & bit and id(p) in GUIDE_MEMBERS[u]]
    city_pg = p.home_city if p.home_city and (p.city == p.home_city or (p.city_miles or 99) <= RADIUS["supper"]) else None
    reg = region_page_of(p)
    parent = guides[0] if guides else ((city_url(city_pg), city_pg) if city_pg and p.city == city_pg else
                                       (f"/regions/{reg}.html", REGION_PAGES[reg][0]) if reg else ("/cities/", "Cities and regions"))
    nav, bc = crumbs([("Home", "/"), (parent[1], parent[0]), (p.name, "/" + path)])
    labels = kind_labels(p)
    rows = []
    if p.tags & FISHFRY:
        bits = [f"Served {days_phrase(p)}." if p.days else "Serves a Friday fish fry.", f"Fish: {e(p.fish)}." if p.fish else "", f"Sides: {e(p.sides)}." if p.sides else ""]
        rows.append(("Fish fry", " ".join(b for b in bits if b)))
    if p.tags & SUPPER:
        rows.append(("Supper club", "Calls itself a supper club, or is widely known as one."))
    if p.tags & CUSTARD:
        rows.append(("Frozen custard", "Serves frozen custard." + (" Part of a chain with five or more Wisconsin locations, so not in the custard guide." if p.chain else "")))
    if p.tags & BOIL:
        rows.append(("Fish boil", "Serves a Door County-style fish boil."))
    if p.founded:
        rows.append(("Founded", f"{p.founded} (the year checked against the place's own history page or local news)"))
    honors = [f"James Beard: {x}" for x in p.jbf.split("; ") if x] + [x for x in p.honors.split("; ") if x]
    if honors:
        rows.append(("Honors", "<ul>" + "".join(f"<li>{e(x)}</li>" for x in honors) + "</ul>"))
    if p.cuisine and p.cuisine not in ("Other", "Restaurant"):
        rows.append(("Kind of place", e(p.cuisine)))
    facts_html = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    addr = ", ".join(x for x in (p.addr, p.city) if x) + (f", WI {p.zip}" if p.zip else ", WI")
    acts = [f'<a class="btn" href="{e(apple_maps(p))}" rel="noopener">Hours &amp; photos in Apple Maps</a>',
            f'<a class="btn btn-ghost" href="{e(directions(p))}" rel="noopener">Directions</a>']
    if p.site:
        acts.append(f'<a class="btn btn-ghost" href="{e(p.site)}" rel="noopener nofollow">Website</a>')
    if p.tel:
        acts.append(f'<a class="btn btn-ghost" href="{e(p.tel)}">Call {e(p.phone)}</a>')
    acts.append(f'<a class="btn btn-ghost" href="/explore/#p={p.id}">Open in the web app</a>')
    near = sorted(((miles((p.lat, p.lon), (q.lat, q.lon)), q) for q in CHECKED_PLACES if q is not p and q.lat is not None and p.lat is not None),
                  key=lambda x: (x[0], x[1].name.lower()))[:6]
    near_html = "".join(f'<li><a href="{place_url(q)}">{e(q.name)}</a><span>{e(q.city)} · {d:.1f} mi · {short_kind(q)}</span></li>' for d, q in near)
    more = [f'<a href="{u}#{p.slug}">{e(n)}</a>' for u, n in guides]
    if city_pg:
        more.append(f'<a href="{city_url(city_pg)}">{e(city_pg)} page</a>')
    if reg:
        more.append(f'<a href="/regions/{reg}.html">{e(REGION_PAGES[reg][0])} page</a>')
    intro = p.note or p.icon
    title = place_title(p)
    desc = place_desc(p)
    body = f"""{nav}
  <main id="main">
  <section class="hero">
    <p class="kicker">{e(labels[0])} · {e(p.city or "Wisconsin")}</p>
    <h1>{e(p.name)}</h1>
    {f'<p class="lede">{e(intro)}</p>' if intro else ""}
    <p class="addr">{e(addr)}</p>
    <div class="actions">{"".join(acts)}</div>
  </section>
  <section id="checked">
    <h2>What we checked</h2>
    <dl class="facts">{facts_html}</dl>
    <p class="fine">Checked open in {HAND_CHECKED} against a 2025 or 2026 source: the place's own site or menu, local news, or its Travel Wisconsin listing. Days and menus change, so check with {e(p.name)} before you go. Hours, photos and ratings are Apple Maps' own, in its place card. Something wrong? <a href="mailto:{EMAIL}?subject={quote('Correction: ' + p.name + ', ' + p.city)}">Tell us</a>.</p>
  </section>
  <section id="nearby">
    <h2>Nearby on our lists</h2>
    <ul class="near">{near_html}</ul>
    <p class="plinks">More: {" · ".join(more) if more else '<a href="/cities/">cities and regions</a>'}</p>
  </section>
  <section id="app" class="final">
    <h2>Save it for Friday</h2>
    <p class="sub">The free {BRAND} app has {e(p.name)} and {N_REST - 1:,} other Wisconsin places, sorted by distance from you, with Apple Maps' live hours and photos.</p>
    {cta()}
  </section>
  </main>"""
    ld = restaurant_ld(p, url)
    written.append(page(path, title, desc, body, [ld, bc], og_alt=f"{BRAND}: {p.name}, {p.city or 'Wisconsin'}", published=PAGES_ADDED))

# ---------------------------------------------------------------- web app (docs/explore/): data split + page
# Venues (gas-station counters, stadium stands: v=1) are left out: the web app has no control that shows them (the iPhone app's
# "Include non-restaurants" filter has no web equivalent). Rows are sorted by town, zip and street so the columns compress well;
# place ids are unchanged, so saved places and #p= links keep working.
os.makedirs(f"{DOCS}/data", exist_ok=True)
CORE_KEYS = ["id", "n", "c", "cu", "t", "s", "a", "z", "la", "lo", "b", "ch", "g", "hc", "ip", "f", "fish", "h", "j", "v"]
# non-restaurants stay out, except hand-picked icons (shown only in the Icons guide; explore.js checks p.v)
rows_web = sorted([r for r in D["places"] if r.get("v") != 1 or (r.get("ip") is not None and r.get("hc"))],
                  key=lambda r: (CITIES[r["c"]] if r.get("c") is not None else "", r.get("z") or "", r.get("a") or "", r["id"]))
cols = {k: [] for k in CORE_KEYS + ["gr", "sc", "in"]}
detail = []
for r in rows_web:
    for k in CORE_KEYS:
        v = r.get(k)
        cols[k].append(round(v, 4) if k in ("la", "lo") and v is not None else v)
    i = r.get("in") or {}
    cols["gr"].append(i.get("g")); cols["sc"].append(i.get("sc")); cols["in"].append(i.get("n"))
    d = {k: r[k] for k in ("note", "days", "sides", "icon", "hon", "jbf", "lic") if r.get(k)}
    if place_site(r.get("w")):
        d["w"] = place_site(r.get("w"))
    if safe_tel(r.get("ph")):
        d["ph"] = safe_tel(r.get("ph")).removeprefix("tel:")
    if i:
        d["in"] = i
    detail.append(d or None)
core = {"generated": D["generated"], "checked": HAND_CHECKED, "cities": CITIES, "cuisines": CUISINES, "brands": D["brands"], "sources": D["sources"],
        "calibration": D.get("calibration", {}), "cols": cols}
json.dump(core, open(f"{DOCS}/data/core.json", "w"), separators=(",", ":"), ensure_ascii=False)
json.dump(detail, open(f"{DOCS}/data/detail.json", "w"), separators=(",", ":"), ensure_ascii=False)
json.dump(json.load(open(f"{ROOT}/data/wi/wi_shapes.json")), open(f"{DOCS}/data/wi_shapes.json", "w"), separators=(",", ":"))
WEB_IDS = set(cols["id"])
assert all(p.id in WEB_IDS for p in CHECKED_PLACES), "every place page's #p= link must open in the web app"

EXPLORE_CSS = """
  [hidden] { display: none !important; }
  .ex-hero { padding: 24px 0 4px; }
  .ex-hero h1 { font-size: clamp(30px, 6vw, 44px); }
  .ex-hero .sub { margin-bottom: 12px; }
  .ex-controls { background: var(--bg); padding: 6px 0 8px; border-bottom: 1px solid var(--rule); }
  .ex-guides { display: flex; gap: 6px; overflow-x: auto; padding: 2px 0 8px; scrollbar-width: none; }
  .ex-guides button, .ex-view button, .ex-small, .ex-linkbtn { flex: 0 0 auto; display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px;
    border: 1px solid var(--rule); background: var(--surface); color: var(--green); border-radius: 999px; padding: 0 14px; font: 600 15px/1.2 var(--text); cursor: pointer; }
  .ex-guides button[aria-pressed="true"], .ex-view button[aria-pressed="true"] { background: var(--green); color: var(--on-green); border-color: var(--green); }
  .ex-guides button:disabled, .ex-small:disabled { cursor: default; }
  .ex-linkbtn { border-color: var(--green); margin-left: 4px; }
  .ex-row1 { display: flex; gap: 8px; align-items: center; }
  .ex-row1 input[type=search] { flex: 1; min-width: 0; min-height: 44px; font: 16px/1.3 var(--text); padding: 10px 12px; border: 2px solid var(--green); border-radius: 12px; background: var(--surface); color: var(--ink); }
  .ex-row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; align-items: center; margin-top: 8px; }
  .ex-sel select { width: 100%; min-height: 44px; font: 16px/1.2 var(--text); padding: 6px 8px; border: 1px solid var(--rule); border-radius: 10px; background: var(--surface); color: var(--ink); }
  .ex-check { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; font-size: 16px; color: var(--ink); cursor: pointer; }
  .ex-check input { width: 20px; height: 20px; margin: 0; accent-color: var(--green); }
  .ex-off { visibility: hidden; }
  .ex-view { display: flex; gap: 4px; justify-self: end; }
  @media (min-width: 700px) {
    .ex-guides { flex-wrap: wrap; overflow-x: visible; }   /* no hidden chips (Saved) off the right edge for mouse users */
    .ex-row2 { display: flex; flex-wrap: wrap; }
    .ex-sel select { width: 13em; }
    .ex-view { margin-left: auto; }
  }
  #ex-sub { margin: 6px 0 0; font-size: 14px; line-height: 1.45; min-height: 1.45em; color: var(--ink2); }
  @media (max-width: 699px) { #ex-sub { min-height: 2.9em; } }
  #ex-count { margin: 4px 0 0; font-size: 14px; line-height: 1.45; min-height: 1.45em; color: var(--muted); }
  #ex-locmsg { font-size: 13px; color: var(--muted); margin: 4px 0 0; }
  #ex-locmsg:empty { display: none; }
  #ex-locmsg:not(:empty) { min-height: 2.9em; }
  #ex-listwrap { min-height: 100vh; }
  #ex-loading { padding: 18px 4px; color: var(--ink2); margin: 0; }
  .ex-list { list-style: none; padding: 0; margin: 10px 0; }
  .ex-list li + li { border-top: 1px solid var(--rule); }
  .ex-row { width: 100%; min-height: 44px; display: flex; gap: 12px; align-items: center; text-align: left; background: none; border: 0; padding: 12px 4px; cursor: pointer; color: var(--ink); font: inherit; }
  .ex-row:hover { background: var(--surface2); }
  .ex-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .ex-main b { font-weight: 650; }
  .ex-town { font-size: 14px; color: var(--muted); }
  .ex-chips .tag { margin: 0 4px 2px 0; }
  .tag-jb { background: var(--green); color: var(--on-green); }
  .tag-plain { background: var(--surface2); color: var(--green); }
  .tag-dash { background: transparent; color: var(--muted); border: 1px dashed var(--muted); }
  .ex-metric { text-align: right; display: flex; flex-direction: column; }
  .ex-metric b { font: 800 22px/1 var(--display); color: var(--green); }
  .ex-metric small { font-size: 12px; color: var(--muted); }
  .ex-rank { flex: 0 0 34px; height: 34px; display: grid; place-items: center; font: 800 20px/1 var(--display); color: var(--green); border-radius: 8px; }
  .ex-rank.top { background: var(--gold); color: var(--on-gold); }
  .ex-empty { padding: 24px 4px; color: var(--muted); }
  #ex-more { display: flex; margin: 8px auto 24px; }
  #ex-mapwrap { position: relative; height: min(72vh, 720px); margin: 10px 0 20px; border: 1px solid var(--rule); border-radius: 16px; overflow: hidden; background: var(--water); }
  #ex-map { width: 100%; height: 100%; display: block; touch-action: none; cursor: grab; }
  .ex-zoom { position: absolute; right: 10px; top: 10px; display: flex; flex-direction: column; gap: 6px; }
  .ex-zoom button { width: 44px; height: 44px; border-radius: 10px; border: 1px solid var(--rule); background: var(--surface); color: var(--green); font: 700 22px/1 var(--text); cursor: pointer; }
  #ex-maphint { position: absolute; left: 10px; bottom: 8px; margin: 0; font-size: 13px; background: var(--surface); padding: 3px 8px; border-radius: 999px; color: var(--ink2); }
  .ex-scrim { position: fixed; inset: 0; z-index: 19; background: rgba(0,0,0,.28); }
  .ex-panel { position: fixed; z-index: 20; right: 0; top: 0; bottom: 0; width: min(440px, 100%); overflow-y: auto; background: var(--surface); border-left: 1px solid var(--rule); box-shadow: -8px 0 24px rgba(0,0,0,.12); padding: 14px 20px 40px; }
  @media (max-width: 600px) { .ex-panel { top: auto; height: 86vh; border-left: 0; border-top: 4px solid var(--gold); border-radius: 18px 18px 0 0; } }
  .ex-close { position: sticky; top: 0; float: right; width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--rule); background: var(--surface); font: 400 26px/1 var(--text); cursor: pointer; color: var(--ink); }
  .ex-kicker { margin: 0; font-size: 12px; font-weight: 700; letter-spacing: .1em; color: var(--green2); }
  .ex-panel h2 { font-size: 34px; margin: 4px 0 6px; text-transform: uppercase; overflow-wrap: anywhere; }
  .ex-addr, .ex-dist { margin: 0 0 4px; color: var(--ink2); font-size: 15px; }
  .ex-actions { margin: 14px 0 8px; display: grid; gap: 8px; }
  .ex-apple { justify-content: center; }
  .ex-act-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .ex-act-row a, .ex-act-row button { flex: 1; min-width: 88px; min-height: 44px; display: inline-flex; align-items: center; justify-content: center; text-align: center; padding: 8px 10px; border: 1px solid var(--rule); border-radius: 12px; text-decoration: none; color: var(--green); font: 600 15px/1.2 var(--text); background: var(--surface); cursor: pointer; }
  .ex-act-row button[aria-pressed="true"] { background: var(--goldsoft); color: var(--on-gold); }
  .ex-sec { margin-top: 18px; }
  .ex-sec h3 { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--rule); padding-bottom: 6px; margin-bottom: 8px; }
  .ex-sec p, .ex-sec li { font-size: 15px; color: var(--ink2); margin: 6px 0; }
  .ex-sec a { display: inline-flex; align-items: center; min-height: 44px; }
  .ex-kv { display: flex; justify-content: space-between; gap: 12px; font-size: 15px; padding: 3px 0; }
  .ex-kv span { color: var(--ink2); }
  .ex-fine { font-size: 13px !important; color: var(--muted) !important; }
  .ex-grade { display: flex; align-items: center; gap: 10px; font-weight: 600; }
  .ex-g { display: inline-grid; place-items: center; width: 40px; height: 40px; border-radius: 10px; color: #fff; font: 800 24px/1 var(--display); }
  .ex-g-A { background: #12733a; } .ex-g-B { background: #4b7a1b; } .ex-g-C { background: #f2b01e; color: #16211d; } .ex-g-D { background: #e8804f; color: #16211d; } .ex-g-F { background: #c1302f; }
  .ex-app { margin-top: 22px; font-size: 14px; color: var(--muted); }
  body.ex-open { overflow: hidden; }
  @media (min-width: 601px) { body.ex-open { overflow: auto; } }
"""
url = f"{DOMAIN}/explore/"
title = fit(["Find a Wisconsin Fish Fry or Restaurant: Map and Search", "Wisconsin Restaurant Map and Fish Fry Finder | Wisconsin Eats"], 50, 60)
desc = fit([f"Type a town, a street or a fish like perch or walleye to see which of {N_REST:,} Wisconsin places match, with {len(FISH)} checked fish fries on a free map.",
            f"Type a town, a street or a fish like perch to see which of {N_REST:,} Wisconsin places match, with {len(FISH)} hand-checked fish fries on a free map.",
            f"Look up {N_REST:,} Wisconsin places by town, street or the fish they fry, and map {len(FISH)} hand-checked fish fries and {len(SUP)} supper clubs. Free."], 140, 160)
nav, bc = crumbs([("Home", "/"), ("Search", "/explore/")])
guide_buttons = "".join(f'<button type="button" data-g="{k}" aria-pressed="{str(k == "fishfry").lower()}">{e(t)}</button>' for k, t in
                        (("fishfry", "Fish fry"), ("supper", "Supper clubs"), ("custard", "Custard"), ("icons", "Icons"), ("oldest", "Oldest"),
                         ("inspections", "Inspections"), ("all", "All restaurants"), ("saved", "Saved")))
body = f"""{nav}
  <main id="main">
  <section class="ex-hero">
    <p class="kicker">{BRAND} · web app</p>
    <h1>Wisconsin restaurant search and map</h1>
    <p class="sub">The app's data in your browser: {N_REST:,} Wisconsin restaurants, cafés, taverns and bakeries, including the {len(FISH)} Friday fish fries, {len(SUP)} supper clubs and {len(CUST)} custard stands we checked by hand. What you save stays in this browser; nothing is sent to us.</p>
  </section>
  <noscript><p>The search needs JavaScript. The guides work without it: <a href="/wisconsin-fish-fry.html">fish fry</a>, <a href="/wisconsin-supper-clubs.html">supper clubs</a>, <a href="/wisconsin-frozen-custard.html">frozen custard</a>, and <a href="/cities/">cities and regions</a>.</p></noscript>
  <div id="ex-app">
    <div class="ex-controls">
      <div class="ex-guides" role="group" aria-label="Guides">{guide_buttons}</div>
      <div class="ex-row1">
        <label class="vh" for="ex-q">Search</label>
        <input id="ex-q" type="search" placeholder="Name, town, street, zip or fish" autocomplete="off" enterkeyhint="search" disabled>
        <button type="button" id="ex-locate" class="ex-small" disabled>Near me</button>
      </div>
      <div class="ex-row2">
        <label class="ex-sel"><span class="vh">Sort</span><select id="ex-sort" disabled><option>Featured first</option></select></label>
        <label class="ex-sel"><span class="vh">Town</span><select id="ex-town" disabled><option value="">All towns</option></select></label>
        <label class="ex-sel"><span class="vh">Kind of place</span><select id="ex-cuisine" disabled><option value="">All kinds</option></select></label>
        <label class="ex-check"><input type="checkbox" id="ex-chains" disabled> Hide chains</label>
        <button type="button" id="ex-clear" class="ex-small ex-off" disabled>Clear filters</button>
        <div class="ex-view" role="group" aria-label="View"><button type="button" data-v="list" aria-pressed="true">List</button><button type="button" data-v="map" aria-pressed="false">Map</button></div>
      </div>
      <p id="ex-sub"></p>
      <p id="ex-count" aria-live="polite"></p>
      <p id="ex-locmsg"></p>
    </div>
    <div id="ex-listwrap"><p id="ex-loading" role="status">Loading Wisconsin's restaurants…</p><ol id="ex-list" class="ex-list"></ol><button type="button" id="ex-more" class="ex-small" hidden></button></div>
    <div id="ex-mapwrap" hidden>
      <canvas id="ex-map" role="img" aria-label="Map of Wisconsin with a dot for each place in the list. The list view has the same places."></canvas>
      <div class="ex-zoom"><button type="button" id="ex-zin" aria-label="Zoom in">+</button><button type="button" id="ex-zout" aria-label="Zoom out">−</button></div>
      <p id="ex-maphint"></p>
    </div>
  </div>
  </main>"""
after = f"""<div id="ex-scrim" class="ex-scrim" hidden></div>
<div id="ex-panel" class="ex-panel" role="dialog" aria-modal="true" aria-labelledby="ex-pname" hidden></div>
<script>
{open(f"{ROOT}/scripts/explore.js").read()}
</script>
"""
webapp_ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": f"{BRAND} web app", "url": url,
             "applicationCategory": "TravelApplication", "operatingSystem": "Any", "browserRequirements": "Requires JavaScript",
             "description": desc, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "publisher": {"@id": ORG_ID}, "author": {"@id": PERSON_ID}}
written.append(page("explore/index.html", title, desc, body, [webapp_ld, bc], extra_css=EXPLORE_CSS,
                    head_extra="<noscript><style>#ex-app{display:none}</style></noscript>\n", after=after))

# ---------------------------------------------------------------- landing page
shots = [("home", "Wisconsin Eats home screen: Friday Fish Fry, Supper Clubs, Frozen Custard, Wisconsin Icons, Oldest Places and Inspections guides, with a search box for restaurants statewide.", "The home screen: one card per guide."),
         ("fishfry", "Friday Fish Fry list in Wisconsin Eats, sorted by distance from downtown Milwaukee, with the fish each place serves.", "Fish fries by distance, with the fish they serve."),
         ("detail", "The Del-Bar supper club in Wisconsin Dells in Wisconsin Eats: address, a button for ratings, hours and photos in Apple Maps, and its history since 1943.", "A supper club's page, with its history."),
         ("map", "Wisconsin Eats map of Wisconsin with clustered pins for fish fries.", "Fish fry pins across the state."),
         ("icons", "Wisconsin Icons list in Wisconsin Eats: James Beard honorees and long-running institutions.", "Wisconsin Icons: James Beard honorees and old favorites.")]
shot_html = []
for name, alt, cap in shots:
    png = f"{DOCS}/img/screen-{name}.png"
    w, h = png_size(png) if os.path.exists(png) else (480, 1043)
    # the screenshots sit well below the fold at every width, so all of them load lazily
    shot_html.append(f'<li><picture><source srcset="/img/screen-{name}.webp" type="image/webp"><img src="/img/screen-{name}.png" alt="{e(alt)}" width="{w}" height="{h}" loading="lazy" decoding="async"></picture><p>{e(cap)}</p></li>')

all_dated_checked = all(p.hc for p in REST if p.founded or p.ip is not None)
north, door = region_stats["northwoods"], region_stats["door-county"]
n_north_counties = len(REGION_PAGES["northwoods"][2].split())
# Wisconsin's own questions first (Lent, the Northwoods and Door County, Dane County's inspections), then the app ones
faq = [
    ("Is there a fish fry outside Lent?", f"Yes. The places in our fish fry guide serve a regular fish fry, not a Lent-only one (a few Northwoods spots are seasonal), and {NOT_ONLY_FRIDAY} of the {len(FISH)} fry on days besides Friday too. Church and Legion fries that run only in Lent aren't listed. Lent {LENT_YEAR} begins on Ash Wednesday, {long_date(ASH_WEDNESDAY)}."),
    ("Does it cover the Northwoods and Door County?", f"Yes. The Northwoods page has {north[0]} hand-checked places across {n_north_counties} northern counties, and the Door County page has {door[0]}, fish boils included. Western and Central Wisconsin have their own pages, and the app's search works statewide."),
    ("How were the fish fries and supper clubs checked?", f"By hand, in {HAND_CHECKED}. Each fish fry, supper club and custard stand on our lists had to turn up in a 2025 or 2026 source, such as its own menu page, a dated news story or its Travel Wisconsin listing. The other places among the {N_REST:,} come from Overture Maps' open place data and the City of Milwaukee and Dane County license lists."),
    ("Do you rate the restaurants?", "Not with stars or reviews, and no list here is sorted by anyone's ratings. The one grade we give is the Dane County inspection summary, which is ours and not official. Open a place and Apple Maps' own card shows its ratings, hours, photos and directions, live from Apple."),
    ("Why do only Madison-area places have inspection grades?", "Public Health Madison & Dane County publishes its routine inspections as open data, so Dane County places get a grade from their results since January 2023, set on a curve. The grade is our own summary, not an official one. Other Wisconsin counties don't publish inspections in bulk."),
    ("Does the app track where I go?", "No. If you allow location, your iPhone or iPad uses it to list the closest places first, and it never reaches us. Skip it and the guides, search and map work the same."),
    ("A place on your list closed, or one is missing. Who do I tell?", f"Send the name and town to {EMAIL}; we correct the list in the next update."),
    ("Is there an Android app?", f"Not for now: the app is for iPhone and iPad. On an Android phone, the web app at {CUSTOM_DOMAIN or DOMAIN}/explore/ has the same guides. Asking for Android at {EMAIL} helps move it up the list."),
]
faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "@id": f"{DOMAIN}/#faq",
          "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
app_node = {"@type": "MobileApplication", "@id": f"{DOMAIN}/#app", "name": "Wisconsin Eats: Restaurants",
            "alternateName": ["Wisconsin Eats", "WI Eats", "Wisconsin Eats: Fish Fry & Supper Club Guide"],
            "description": f"A free guide to {N_REST:,} Wisconsin restaurants, with hand-checked lists of {len(FISH)} Friday fish fries, {len(SUP)} supper clubs and {len(CUST)} frozen custard stands. Sort by distance, open Apple Maps' live place card for hours and photos, and save places for Friday.",
            "url": f"{DOMAIN}/", "image": f"{DOMAIN}/og.png", "screenshot": f"{DOMAIN}/img/screen-home.png",
            "operatingSystem": "iOS, iPadOS", "applicationCategory": "TravelApplication", "applicationSubCategory": "Food & Drink",
            "inLanguage": "en", "author": {"@id": PERSON_ID}, "publisher": {"@id": ORG_ID},
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "category": "free"}}
if APP_STORE_URL:
    app_node["installUrl"] = APP_STORE_URL
    app_node["sameAs"] = [APP_STORE_URL]
app_ld = {"@context": "https://schema.org", "@graph": [app_node]}
title = fit(["Wisconsin Eats: Find a Fish Fry, Supper Club or Restaurant", "Wisconsin Eats: Fish Fry Finder and Supper Club Guide"], 50, 60)
desc = fit([f"Find a Wisconsin Friday fish fry near you: {len(FISH)} checked by hand, plus {len(SUP)} supper clubs, {len(CUST)} custard stands and {N_REST:,} restaurants. Free iPhone app.",
            f"Which tavern near you fries perch on Friday? {len(FISH)} hand-checked Wisconsin fish fries, {len(SUP)} supper clubs and {N_REST:,} restaurants, free on iPhone."], 140, 160)
city_cards = "".join(f'<li><a href="{city_url(c)}">{e(c)}</a></li>' for c in CITY_PAGES)
checked_line = (f"The {len(FISH)} fish fries, {len(SUP)} supper clubs and {len(CUST)} custard stands in the guides were each checked open in {HAND_CHECKED}"
                + (", and so was every place shown with a founding year or an honor." if all_dated_checked else "."))
body = f"""  <main id="main">
  <section class="hero">
    <p class="kicker">{BRAND} · {TAGLINE.lower()} · iPhone and iPad</p>
    <h1>Wisconsin restaurants, from Friday fish fry to supper club</h1>
    <p class="lede">Which tavern near you fries perch on Friday night? {BRAND} answers that from a hand-checked list of {len(FISH)} fish fries, with {len(SUP)} supper clubs and {len(CUST)} custard stands beside it, plus {N_REST:,} restaurants, cafés, taverns and bakeries across {N_TOWNS:,} Wisconsin towns.</p>
    {cta('<a class="btn btn-ghost" href="/explore/">Search on the web</a>')}
    <ul class="stats" aria-label="What's in the app">
      <li><b>{len(FISH)}</b><span>Friday fish fries</span></li>
      <li><b>{len(SUP)}</b><span>supper clubs</span></li>
      <li><b>{len(CUST)}</b><span>custard stands</span></li>
      <li><b>{N_REST:,}</b><span>restaurants</span></li>
    </ul>
  </section>

  <section id="what">
    <h2>Built around Friday night, not star ratings</h2>
    <p class="sub">Most restaurant apps sort by stars. This one starts from the Wisconsin calendar: fish on Friday, a supper club when there's something to celebrate, custard on a summer evening, and the taverns and bakeries that have been open for generations. {checked_line} Ratings, hours and photos are Apple Maps' own, in its live place card.</p>
  </section>

  <section id="how">
    <h2>From the couch to the fish fry line</h2>
    <ol class="steps">
      <li class="step"><div class="n" aria-hidden="true">1</div><div><h3>Choose what you're after.</h3><p>Friday Fish Fry, Supper Clubs, Frozen Custard, Wisconsin Icons or Oldest Places, or type a name, a town or a street into the search.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">2</div><div><h3>Narrow it down.</h3><p>Put the closest places first, filter by town or kind of food, or switch to the map. Fish fry entries name the fish and the days when the place lists them.</p></div></li>
      <li class="step"><div class="n" aria-hidden="true">3</div><div><h3>Head out.</h3><p>Apple Maps' card shows today's hours and photos. From there, phone ahead, start directions, or tuck the place into Saved for next Friday.</p></div></li>
    </ol>
  </section>

  <section id="screens">
    <h2>Inside the app</h2>
    <ul class="shots" tabindex="0" aria-label="Wisconsin Eats app screenshots">
      {"".join(shot_html)}
    </ul>
  </section>

  <section id="guides">
    <h2>Read the guides on the web</h2>
    <p class="sub">The hand-checked lists from the app, one page each.</p>
    <div class="grid2">
      <a class="card" href="/wisconsin-fish-fry.html"><h3>Wisconsin Friday fish fry guide</h3><p>{len(FISH)} fish fries grouped by region and town, each with its fish, days and sides when the place lists them.</p></a>
      <a class="card" href="/wisconsin-supper-clubs.html"><h3>Wisconsin supper club guide</h3><p>{len(SUP)} supper clubs by region, with the year each opened where we could pin it down.</p></a>
      <a class="card" href="/wisconsin-frozen-custard.html"><h3>Wisconsin frozen custard stands</h3><p>{len(CUST)} local stands; chains with five or more Wisconsin locations are left out.</p></a>
      <a class="card" href="/wisconsin-lent-fish-fry.html"><h3>Lent fish fry {LENT_YEAR}</h3><p>Every Friday of Lent with its date, then the perch, walleye and bluegill fries and the ones open on other days.</p></a>
      <a class="card" href="/explore/"><h3>Search the state</h3><p>Look up any of {N_REST:,} places in {N_TOWNS:,} towns by name, town, street or fish, in the browser.</p></a>
      <a class="card" href="/about.html"><h3>How the lists are made</h3><p>Where the listings come from, how a place gets hand-checked, and who is behind {BRAND}.</p></a>
    </div>
  </section>

  <section id="cities">
    <h2>Fish fry and supper clubs, city by city</h2>
    <p class="sub">Each city page gathers its fish fries, supper clubs, custard stands, icons and oldest dated places. <a href="/cities/">See every city and region</a>.</p>
    <ul class="cities">{city_cards}</ul>
    <p class="sub">Or a region, from Door County to the Northwoods:</p>
    {region_links()}
  </section>

  <section id="pricing">
    <h2>No price tag, no ads</h2>
    <p class="sub">{BRAND} costs nothing: no sign-up, no ads, nothing to buy inside it. The data ships with the app, so the lists still open on a lake road with one bar of signal.</p>
  </section>

  <section id="privacy">
    <h2>What we know about you: nothing</h2>
    <p class="sub">The app sends us no data at all. If you share your location, the phone uses it to put the closest places first, and the places you save stay on the phone too. This site has no cookies and no trackers. <a href="/privacy.html">Read how the app and this site handle data</a>.</p>
  </section>

  <section id="faq">
    <h2>Fish fry and app questions</h2>
    {faq_html}
  </section>

  <section id="download" class="final">
    <h2>Ready for Friday?</h2>
    <p class="sub">{BRAND} is free for iPhone and iPad{" on the App Store" if APP_STORE_URL else ", and on its way to the App Store. Ask for early access, or use the guides and the web app in the meantime"}.</p>
    <div class="cta-row">{store_button()}</div>
  </section>
  </main>"""
written.append(page("index.html", title, desc, body, [app_ld, faq_ld]))

# ---------------------------------------------------------------- about
cal = D.get("calibration", {})
rates = [cal.get(a, {}).get("meta_high", {}).get("official") for a in ("mke", "dane")]
rates = [round(r * 100) for r in rates if r is not None]
rate_txt = (f"{min(rates)}%" if min(rates) == max(rates) else f"{min(rates)}–{max(rates)}%") if rates else "most"
nav, bc = crumbs([("Home", "/"), ("About and sources", "/about.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <p class="kicker">About {BRAND}</p>
    <h1>Who's behind {BRAND}, and where its lists come from</h1>
    <p class="lede">{BRAND} (“WI Eats”) is {AUTHOR}'s independent app and website, a free guide to {N_REST:,} Wisconsin restaurants. Its {len(FISH)} Friday fish fries, {len(SUP)} supper clubs and {len(CUST)} custard stands were each checked by hand, and there's no account to make, no ads and no tracking.</p>
  </section>
  <section id="maker">
    <h2 id="nicholas-soderstrom">Who makes it</h2>
    <p>{AUTHOR} builds and maintains both the app and this website. {BRAND} is not affiliated with, endorsed by or operated by the City of Milwaukee, Public Health Madison &amp; Dane County, the James Beard Foundation, Apple, or any restaurant, team or chain.</p>
    <h2>How a place gets on the lists</h2>
    <p>Every fish fry, supper club, custard stand and icon on the lists was looked up by hand in {HAND_CHECKED}. Each needed a 2025 or 2026 source, such as its own website or menu, a local news story or its Travel Wisconsin listing, and its street address was checked as well. The research keeps facts and a source link for each place, never review text or anyone's ratings, and a place it finds closed is taken off.</p>
    <p>Everything else among the {N_REST:,} comes from Overture Maps' open place data, Milwaukee's list of active food dealer and tavern licenses, and Public Health Madison &amp; Dane County's list of licensed establishments. Map listings stay in only where that source proved reliable: tested against the Milwaukee and Dane County license lists, its high-confidence listings turned out to be a licensed business {rate_txt} of the time. Each website link is fetched and checked, and one that no longer leads to the place's own site is dropped.</p>
    <p>The letter grades on Dane County places are ours, set on a curve from the county's routine inspections since January 2023: a summary of its results, not an official grade. No other Wisconsin county publishes inspections in bulk, so places elsewhere have no grade. Star ratings, reviews, hours and photos in the app all come live from Apple Maps' place card; {BRAND} keeps none of them and sorts by none of them.</p>
    <h2>Updates</h2>
    <p>The restaurant data in this build dates from {long_date(BUILD_DATE)}, and the hand checks from {HAND_CHECKED}. A new build follows when the research or the open data changes, and that's when corrections land. Restaurants open and close, so call ahead before a long drive.</p>
    <h2>Sources and licenses</h2>
    <ul>
      <li><b>Overture Maps Foundation</b> (<a href="https://overturemaps.org" rel="noopener">overturemaps.org</a>): restaurant listings and websites outside the Milwaukee and Dane County license lists, filtered and reformatted for {BRAND}. Data from Meta, Microsoft, DAC and BrightQuery, available under the <a href="/licenses/CDLA-Permissive-2.0.txt">Community Data License Agreement – Permissive 2.0</a>. Data from Foursquare, © Foursquare Labs, Inc., available under the <a href="/licenses/Apache-2.0.txt">Apache License 2.0</a>; see the notice below. Data from AllThePlaces, available under CC0 1.0.</li>
      <li><b>City of Milwaukee Open Data</b>: active food dealer and tavern licenses, modified for use here. The City of Milwaukee makes no warranty as to the data's accuracy, completeness or timeliness and does not endorse {BRAND}.</li>
      <li><b>Public Health Madison &amp; Dane County</b>: licensed establishments and routine inspection results, modified for use here. Public Health Madison &amp; Dane County makes no warranty as to the data's accuracy, completeness or timeliness and does not endorse {BRAND}.</li>
      <li><b>Honors</b>: shown as plain facts, each checked by hand against its public announcement: James Beard Foundation awards, finalists, semifinalists and America's Classics, and the other honors listed with a place. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation.</li>
      <li><b>Maps</b>: county outlines © OpenStreetMap contributors and Overture Maps Foundation (ODbL). In the app, maps, place cards and directions are by Apple Maps.</li>
    </ul>
    <h2>Foursquare notice</h2>
    <div class="notice">{e(FOURSQUARE_NOTICE)}</div>
    <h2>Contact</h2>
    <p>Spotted a closed place, a missing one or a mistake? Write to <a href="mailto:{EMAIL}">{EMAIL}</a>. The <a href="/privacy.html">privacy policy</a> and <a href="/terms.html">terms of use</a> cover the rest.</p>
  </section>
  </main>"""
about_ld = {"@context": "https://schema.org", "@type": "AboutPage", "url": f"{DOMAIN}/about.html", "name": f"About {BRAND}",
            "mainEntity": {"@id": PERSON_ID}, "isPartOf": {"@id": SITE_ID}, "dateModified": modified(PAGES_ADDED)}
written.append(page("about.html", fit([f"About Wisconsin Eats: Who Makes It and Where the Data Comes From", "About Wisconsin Eats: Sources, Methods and Who Makes It"], 50, 60),
                    fit([f"Wisconsin Eats is an independent app and website by {AUTHOR}. How the hand-checked fish fry and supper club lists are built, plus sources and licenses.", f"Wisconsin Eats is an independent app and website by {AUTHOR}: how the hand-checked fish fry and supper club lists are built, and our sources."], 140, 160),
                    body, [about_ld, bc], published=PAGES_ADDED))

# ---------------------------------------------------------------- privacy and terms
nav, bc = crumbs([("Home", "/"), ("Privacy policy", "/privacy.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Privacy policy</h1>
    <p class="lede">Short version: the {BRAND} app collects nothing about you, and this website doesn't track you. Last updated {long_date(POLICY_UPDATED)}.</p>
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
    <p>{'On the App Store, the app&#39;s privacy label is &quot;Data Not Collected&quot;.' if APP_STORE_URL else 'The app&#39;s privacy answers to Apple are &quot;Data Not Collected&quot;, which is the label the App Store will show once the app is live there.'}</p>
    <h2>This website</h2>
    <p>The site is static pages hosted on GitHub Pages. It sets no cookies and loads no analytics, fonts or scripts from anyone else. GitHub may keep standard server logs, such as IP addresses, for security; see <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>.</p>
    <h2>The web app</h2>
    <ul>
      <li><b>Saved places and your last guide</b> in the web app at <a href="/explore/">/explore/</a> are kept in this browser's local storage only, under two keys: <code>we-saved</code> (the places you saved) and <code>we-guide</code> (the guide you last opened). They never leave your browser, and clearing this site's data in your browser deletes them.</li>
      <li><b>Near me.</b> The web app asks for your location only when you press Near me or choose the Nearest sort, and your browser asks you first. The location is used in the page to sort places by distance and is never sent anywhere, including to us.</li>
      <li><b>Links out.</b> Apple Maps, directions, websites and phone numbers open in Apple Maps, the place's own site or your phone, under their own privacy policies.</li>
    </ul>
    <h2>Email</h2>
    <p>If you email us, we use your message and address only to reply and to fix the listing you told us about. We don't add you to a mailing list or share your address. Mail to {EMAIL} is forwarded to our inbox by Cloudflare Email Routing, which handles it under <a href="https://www.cloudflare.com/privacypolicy/" rel="noopener">Cloudflare's privacy policy</a>.</p>
    <h2>Children</h2>
    <p>The app collects no personal information from anyone, including children.</p>
    <h2>Changes and contact</h2>
    <p>If this policy changes, the new version will be posted here with a new date. Questions: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
  </section>
  </main>"""
written.append(page("privacy.html", "Privacy Policy: Wisconsin Eats Fish Fry & Restaurant App",
                    fit(["The Wisconsin Eats privacy policy: the app collects no data, keeps your location and saved places on your device, and this website sets no cookies at all."], 140, 160),
                    body, [bc], lastmod=POLICY_UPDATED))

nav, bc = crumbs([("Home", "/"), ("Terms of use", "/terms.html")])
body = f"""{nav}
  <main id="main" class="legal">
  <section class="hero">
    <h1>Terms of use</h1>
    <p class="lede">The plain-language terms for the {BRAND} app and this website. Last updated {long_date(POLICY_UPDATED)}.</p>
  </section>
  <section>
    <h2>What the app is</h2>
    <p>{BRAND} is a free guide to restaurants in Wisconsin, made by {AUTHOR}. It is provided as is, for personal use, without charge and without warranties of any kind.</p>
    <h2>Check before you go</h2>
    <p>Restaurants open, close, change their hours and change their menus. Fish fry days, fish, sides and founding years are what each place or a named source said when we checked in {HAND_CHECKED}. We work to keep the lists right, but we can't promise that any listing is current or complete. Call the restaurant before you make the trip.</p>
    <h2>Inspection grades</h2>
    <p>Grades in the Inspections guide are our own summary, graded on a curve from Public Health Madison &amp; Dane County's routine inspection records since January 2023. They are not official grades and are not a statement by the health department. For official records, see Public Health Madison &amp; Dane County.</p>
    <h2>Other people's content</h2>
    <p>Ratings, reviews, hours and photos in each place card come from Apple Maps and are Apple's and its providers', under Apple's terms. Restaurant names and trademarks belong to their owners. {BRAND} is not affiliated with any restaurant, team, chain or government agency.</p>
    <h2>Data sources and licenses</h2>
    <ul>
      <li>Overture Maps Foundation places data: data from Meta, Microsoft, DAC and BrightQuery under the <a href="/licenses/CDLA-Permissive-2.0.txt">Community Data License Agreement, Permissive 2.0</a>; data from Foursquare (© Foursquare Labs, Inc.) under the <a href="/licenses/Apache-2.0.txt">Apache License 2.0</a>, with its <a href="/licenses/Foursquare-NOTICE.txt">notice</a>; data from AllThePlaces under CC0 1.0. County outlines under the Open Database License, © OpenStreetMap contributors, Overture Maps Foundation.</li>
      <li>City of Milwaukee Open Data: active food dealer and tavern licenses.</li>
      <li>Public Health Madison &amp; Dane County: licensed establishments and inspection records.</li>
      <li>James Beard Foundation: award, finalist and semifinalist history.</li>
      <li>Fish fries, supper clubs, custard stands and founding years: our own research, with a source recorded for every place.</li>
    </ul>
    <p>More on each source: <a href="/about.html">about {BRAND}</a>.</p>
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
                    body, [bc], lastmod=POLICY_UPDATED))

body = f"""  <main id="main">
  <section class="hero">
    <h1>This page isn't on the menu</h1>
    <p class="lede">The link may be old: a place's page comes down when the place leaves our lists. From here, try the <a href="/">{BRAND} home page</a>, the <a href="/wisconsin-fish-fry.html">Friday fish fry guide</a>, the <a href="/wisconsin-supper-clubs.html">supper club guide</a> or the <a href="/cities/">cities and regions</a>.</p>
    <p><a class="btn" href="/explore/">Search Wisconsin restaurants</a></p>
  </section>
  </main>"""
page("404.html", f"Page not found | {BRAND}", "There's no page at this address. Try the fish fry guide, the supper club guide or the restaurant search.", body, robots="noindex,follow")

# ---------------------------------------------------------------- plumbing
# pages that left the lists (a place no longer hand-checked, say) are removed, so the sitemap and the files always agree
keep = {w for w in written}
for sub in ("places", "regions", "cities"):
    for f in os.listdir(f"{DOCS}/{sub}"):
        if f.endswith(".html") and f"{sub}/{f}" not in keep:
            os.remove(f"{DOCS}/{sub}/{f}")


def order(item):
    u = item[0]
    return (u != "index.html", u.startswith("places/"), u.startswith("regions/"), u.startswith("cities/"), u)


open(f"{DOCS}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                       + "".join(f"  <url><loc>{DOMAIN}/{'' if u == 'index.html' else u.removesuffix('index.html')}</loc><lastmod>{m}</lastmod></url>\n"
                                                 for u, m in sorted(PAGES, key=order)) + "</urlset>\n")
open(f"{DOCS}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
json.dump({"name": BRAND, "short_name": "WI Eats", "description": f"{TAGLINE}, plus {N_REST:,} Wisconsin restaurants.", "start_url": f"{BASE}/", "display": "browser",
           "background_color": "#fbfaf6", "theme_color": "#203731",
           "icons": [{"src": f"{BASE}/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": f"{BASE}/icon-512.png", "sizes": "512x512", "type": "image/png"},
                     {"src": f"{BASE}/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]},
          open(f"{DOCS}/site.webmanifest", "w"), indent=2)
if CUSTOM_DOMAIN:
    open(f"{DOCS}/CNAME", "w").write(CUSTOM_DOMAIN + "\n")
elif os.path.exists(f"{DOCS}/CNAME"):
    os.remove(f"{DOCS}/CNAME")   # no custom domain yet: GitHub serves the project address
open(f"{DOCS}/.nojekyll", "w").write("")
json.dump({"generated": BUILD_DATE, "restaurants": N_REST, "towns": N_TOWNS, "fish_fry": len(FISH), "supper_clubs": len(SUP), "custard": len(CUST),
           "fish_listed": N_FISH_KNOWN, "fish_counts": dict(FISH_WORDS.most_common(12)), "not_only_friday": NOT_ONLY_FRIDAY,
           "supper_with_fish_fry": sup_fish, "supper_founded_known": len(sup_old), "supper_pre1950": sup_pre1950, "place_pages": len(CHECKED_PLACES),
           "cities": {c: dict(zip(["restaurants", "fish_fry_near", "supper_near", "custard_near"], v)) for c, v in city_stats.items()}},
          open(f"{ROOT}/playbook/site-numbers.json", "w"), indent=1)
print("wrote", len(written) + 1, "pages:", len(CHECKED_PLACES), "place pages,", len(REGION_PAGES), "regions,", len(CITY_PAGES), "cities, and",
      ", ".join(w for w in written if not w.startswith(("places/", "cities/", "regions/"))))
print(f"restaurants {N_REST:,} in {N_TOWNS} towns | fish fry {len(FISH)} | supper {len(SUP)} | custard {len(CUST)} | web app rows {len(rows_web):,}")
print("top fish:", FISH_WORDS.most_common(10))
print(f"websites: {n_sites - len(SITE_DROPS):,} of {n_sites:,} in places.json linked; left off by a later verdict: "
      + (", ".join(f"{u} ({w})" for u, w in sorted(SITE_DROPS.items())[:10]) or "none"))
