"""Checks every website link the app ships before it ships, because map listings carry stale and hijacked domains.

Chicago found about 3% of its listing websites redirected to gambling, betting or adult sites, including a starred restaurant's.
A link survives only if:
  - the final response is 2xx,
  - it stays on the same registered domain (or the page plainly belongs to the place),
  - the page mentions a distinctive word of the place's name,
  - and nothing looks like gambling spam, adult content, a parked or for-sale domain, an expired account or "coming soon".
A site that blocks the check, times out or errors is dropped too: no link beats a wrong link. The one exception is a chain's own
domain (mcdonalds.com for McDonald's): when its sample pages refuse the check (403, 429, connection refused), the links stay, because
the domain plainly belongs to the brand.

Polite by design: an honest user agent, one request at a time per host, and three sample pages for a chain's own domain (5+ places,
80%+ one brand). Shared hosts (Square, Wix, Linktree, Instagram) carry many unrelated places, so every link there is checked on its own.
Never bypasses bot protection.

Usage: ../.venv/bin/python check_websites.py [--recheck-ok | --rescan-cached]   (reads data/wi/website_candidates.json and the manual verdicts in
data/wi/website_overrides.json) → data/wi/website_check.json ({url: {"ok": bool, "why": str, "final": str}})
The app export (wisconsin.py, WI_APP=1) drops every link that isn't ok. Re-run before each App Store submission.
"""
import collections
import json
import os
import re
import threading
import sys
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import gzip
import hashlib

import requests

import injection

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = f"{ROOT}/data/wi/website_check.json"
# verdicts a person made (with evidence) that no re-run may undo: {url: {"ok": false, "why": ..., "source": ...}}
OVERRIDES = f"{ROOT}/data/wi/website_overrides.json"
UA = "WisconsinEatsLinkCheck/1.0 (+https://wisconsin.eatsranked.com/)"
GENERIC = set("""the and of a an at on in restaurant restaurants bar bars grill grille cafe caffe coffee pizza pizzeria pub tavern house
supper club inn lounge kitchen bistro eatery diner bakery deli market express food foods co company inc llc ltd corp wi wisconsin
milwaukee madison family original new old north south east west st saint mt sports place spot shop shoppe taproom brewing brewery
tap taps bbq barbecue burger burgers chicken subs sub sandwich sandwiches tacos taco mexican chinese thai sushi asian italian
american cuisine catering events""".split())
# Hijacked domains carry Indonesian slot and lottery spam, Turkish betting pages or porn links: any of these marks a page.
SPAM = re.compile(r"slot ?gacor|situs (?:slot|judi|togel)|slot online|\bslot ?88\b|\btogel\b|judi (?:online|bola|slot|qq|poker)|perjudian|"
                  r"bandar ?(?:slot|qq|togel)|\bmaxwin\b|\brtp slot|\bsbobet\b|\bbahis|casino siteleri|\b1win\b|watch porn|free porn|"
                  r"porn videos?|\bpornhub\b|\bxvideos\b|\bxnxx\b|escort service|adult dating|sex cam|camgirl", re.I)
BLOBS = re.compile(r"[A-Za-z0-9+/=_-]{100,}")   # base64 images and tokens: random letters spell anything
# Words a real casino's restaurant or a brewery near the sportsbook uses too: they count only in the page title or description,
# or repeated in the body, and never on a casino's own page.
BETTING = re.compile(r"online casino|casino online|deposit bonus|sportsbook|\bbaccarat\b|bet365|no deposit", re.I)
HEAD = re.compile(r"<title[^>]*>(.*?)</title>|<meta[^>]+name=.description.[^>]+content=\"([^\"]*)", re.S)
CASINO_PLACE = re.compile(r"casino|gaming|potawatomi|ho-?chunk|oneida|menominee|mohican|north ?star|lake of the torches|"
                          r"st\.? ?croix|bad river|legendary waters|isle vista|grindstone", re.I)
PARKED = re.compile(r"domain (?:is|may be) for sale|buy this domain|this domain is parked|parked free|sedoparking|hugedomains|"
                    r"afternic|domain has expired|this domain name has expired|account (?:has been )?suspended|website coming soon|"
                    r"site (?:is )?coming soon|future home of|launching soon|godaddy\.com/domainsearch|dan\.com", re.I)
# directories, listings, review sites, shorteners and fundraisers: not the place's own page
BAD_HOSTS = ("business.site", "negocio.site", "google.com", "goo.gl", "g.co/", "share.google", "yelp.com", "tripadvisor.",
             "facebook.com/pages", "doordash.com", "grubhub.com", "ubereats.com", "seamless.com", "allmenus.com", "menupix.com",
             "zmenu.com", "restaurantji.com", "yellowpages.com", "superpages.com", "whitepages.com", "chamberofcommerce.com",
             "cortera.com", "dandb.com", "bizapedia.com", "city-data.com", "mapquest.com", "citysearch.com", "yahoo.com", "hub.biz",
             "edan.io", "poi.place", "placeweb.site", "jany.io", "lany.io", "keeq.io", "restoguides.com", "dinehere.us", "foodspot.com",
             "gastrobars.com", "indulgery.com", "clubplanet.com", "restaurant.com", "groupon.com", "seatgeek.com", "opentable.com",
             "menuism.com", "barfinder.com", "friendseat.com", "local.com", "usplaces.com", "foodeist.com", "jmaps.net", "kwickmenu.com",
             "tinyurl.com", "bit.ly", "forms.gle", "gofund.me", "gofundme.com", "cash.app", "tiktok.com", "reverbnation.com")
SHADY = re.compile(r"(?:^|\.)food\d+\.com$|\.top$")   # food73.com-style listing farms, .top redirect farms
# a brand that moved its stores to a short domain
ALIASES = {"burgerking.com": "bk.com"}
BLOCKED = re.compile(r"^(?:http 40[39]|http 429|error: (?:ConnectionError|ConnectTimeout|ReadTimeout))$")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s.replace("'", "")).strip()


def regdom(host):
    parts = host.lower().removeprefix("www.").split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def bad_host(url):
    """Matches a listed site by its host, not as a substring: "restaurant.com" must not catch madersrestaurant.com
    (that bug dropped 171 restaurants' own links). Entries with a path ("facebook.com/pages", "g.co/") match host + path."""
    u = urllib.parse.urlparse(url if "//" in url else "https://" + url)
    host = u.netloc.lower().split("@")[-1].split(":")[0].removeprefix("www.")
    for b in BAD_HOSTS:
        if "/" in b:
            bh, bp = b.split("/", 1)
            if (host == bh or host.endswith("." + bh)) and u.path.lower().lstrip("/").startswith(bp):
                return True
        elif b.endswith("."):   # "tripadvisor." = any tripadvisor domain
            if host.startswith(b) or ("." + b) in ("." + host):
                return True
        elif host == b or host.endswith("." + b):
            return True
    return bool(SHADY.search(regdom(host)))


def words(name):
    return [w for w in norm(name).split() if len(w) >= 4 and w not in GENERIC]


host_locks = collections.defaultdict(threading.Lock)
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "text/html,*/*;q=0.5", "Accept-Language": "en-US"})


CACHE = f"{ROOT}/data/wi/pagecache"   # git-ignored: one gzip per fetched page, first line the final URL


def cache_put(url, final, body):
    os.makedirs(CACHE, exist_ok=True)
    with gzip.open(f"{CACHE}/{hashlib.md5(url.encode()).hexdigest()}.html.gz", "wt", encoding="utf-8") as f:
        f.write(final + "\n" + body)


def cache_get(url):
    p = f"{CACHE}/{hashlib.md5(url.encode()).hexdigest()}.html.gz"
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        final, _, body = f.read().partition("\n")
    return final, body


def check(url, name, cached=None):
    u = url if url.startswith("http") else "https://" + url
    host = urllib.parse.urlparse(u).netloc.lower()
    if bad_host(u):
        return {"ok": False, "why": "directory or Google link", "final": u}
    if cached:   # --rescan-cached: today's rules on the page as fetched last time
        final, body = cached
    else:
        with host_locks[regdom(host)]:
            try:
                r = session.get(u, timeout=(8, 15), allow_redirects=True, stream=True)
                body = r.raw.read(400_000, decode_content=True).decode(r.encoding or "utf-8", "ignore") if r.ok else ""
                final = r.url
                r.close()
            except Exception as e:
                return {"ok": False, "why": "error: " + type(e).__name__, "final": u}
            finally:
                time.sleep(0.3)
        if not r.ok:
            return {"ok": False, "why": f"http {r.status_code}", "final": final}
        cache_put(u, final, body)
    text = BLOBS.sub(" ", body).lower()
    head = " ".join(a or b for a, b in HEAD.findall(text[:60_000]))
    casino = CASINO_PLACE.search(name) or CASINO_PLACE.search(urllib.parse.urlparse(final).netloc)
    if SPAM.search(text) or SPAM.search(final) or (not casino and (BETTING.search(head) or len(BETTING.findall(text)) >= 2)):
        return {"ok": False, "why": "gambling or adult content", "final": final}
    # planted links and spam (casino, betting, adult, pharma, link farms; visible, hidden or off-screen): injection.py
    reasons = injection.scan(body, host, final, name)
    if reasons:
        rule, evidence = reasons[0]
        return {"ok": False, "why": "hacked: " + rule, "final": final, "evidence": evidence[:300]}
    pk = injection.parked(body, final)
    if pk:
        return {"ok": False, "why": "parked, expired or coming soon", "final": final, "evidence": pk[1][:300]}
    if PARKED.search(text[:60_000]):
        return {"ok": False, "why": "parked, expired or coming soon", "final": final}
    if bad_host(final):
        return {"ok": False, "why": "redirects to a directory", "final": final}
    ws = words(name)
    page = norm(re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S)) + " " + norm(final)
    mentions = not ws or any(w in page for w in ws)
    same = regdom(urllib.parse.urlparse(final).netloc) in (regdom(host), ALIASES.get(regdom(host)))
    if not mentions:
        return {"ok": False, "why": "page doesn't mention the place", "final": final}
    if not same and not any(w in norm(urllib.parse.urlparse(final).netloc) for w in ws):
        return {"ok": False, "why": "moved to another domain", "final": final}
    return {"ok": True, "why": "ok", "final": final}


def main():
    # every link the export considered (written by wisconsin.py, WI_APP=1), so a link dropped last time gets another chance
    cands = json.load(open(f"{ROOT}/data/wi/website_candidates.json"))
    jobs = collections.defaultdict(list)   # registered domain -> [(url, name)]
    for w, name in cands.items():
        u = w if w.startswith("http") else "https://" + w
        jobs[regdom(urllib.parse.urlparse(u).netloc)].append((w, name))
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
    over = json.load(open(OVERRIDES)) if os.path.exists(OVERRIDES) else {}
    if "--recheck-ok" in sys.argv:   # fetch every passing page again (after a new rule, before a submission)
        prev = {u: v for u, v in prev.items() if not v["ok"]}
    # chain verdicts are recomputed every run; host rules may have grown since a page was fetched
    # ("hacked" too: the detector's rules change, and the first version flagged margin-left layouts like Murray's On Main)
    prev = {u: v for u, v in prev.items() if not v["why"].startswith(("chain domain", "brand's own", "hacked"))
            and v["why"] not in ("moved to another domain", "gambling or adult content", "directory or Google link", "redirects to a directory")}
    todo, chain_hosts, brand_of = [], {}, {}
    for dom, items in jobs.items():
        uniq = list(dict.fromkeys(items))
        top, n = collections.Counter(name for _, name in uniq).most_common(1)[0]
        if len(uniq) >= 5 and n >= 0.8 * len(uniq):   # a chain's own domain: three samples stand for all
            chain_hosts[dom] = [u for u, _ in uniq]
            brand_of[dom] = top
            todo += uniq[:3]
        else:
            todo += uniq
    for u, v in prev.items():   # host rules apply to cached pages too, no request needed
        if v["ok"] and (bad_host(u) or bad_host(v["final"])):
            prev[u] = {"ok": False, "why": "redirects to a directory", "final": v["final"]}
    if "--rescan-cached" in sys.argv:   # no requests: re-judge every cached page with the current rules
        for u, n in todo:
            c = cache_get(u if u.startswith("http") else "https://" + u) or cache_get(u)
            if c and u not in over:
                prev[u] = check(u, n, cached=c)
    todo = [(u, n) for u, n in todo if u not in prev and u not in over]
    print(f"{sum(len(v) for v in jobs.values())} links, {len(jobs)} domains, {len(chain_hosts)} chain domains; checking {len(todo)}")
    results, done = dict(prev), 0
    lock = threading.Lock()

    def run(item):
        nonlocal done
        res = check(*item)
        with lock:
            results[item[0]] = res
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{len(todo)}", flush=True)
                json.dump(results, open(OUT + ".tmp", "w"))
                os.replace(OUT + ".tmp", OUT)

    with ThreadPoolExecutor(max_workers=24) as ex:
        list(ex.map(run, todo))
    for dom, urls in chain_hosts.items():
        samples = [results.get(u) for u in urls[:3] if results.get(u)]
        verdict = bool(samples) and sum(s["ok"] for s in samples) >= 2
        why = "chain domain " + ("ok" if verdict else "failed its samples")
        own = any(w in norm(dom) for w in words(brand_of[dom]))
        if not verdict and own and samples and all(s["ok"] or BLOCKED.match(s["why"]) for s in samples):
            verdict, why = True, "brand's own site (blocked the check)"
            for u in urls[:3]:
                results[u] = {**results[u], "ok": True, "why": why}
        for u in urls[3:]:
            results[u] = {"ok": verdict, "why": why, "final": u}
    for u, v in over.items():
        results[u] = {"ok": bool(v["ok"]), "why": "manual: " + v["why"], "final": v.get("final", u)}
    tmp = OUT + ".tmp"   # write then rename: a stopped run never leaves a half-written file
    json.dump(results, open(tmp, "w"), indent=0)
    os.replace(tmp, OUT)
    c = collections.Counter(v["why"] if not v["ok"] else "ok" for v in results.values())
    print("results:", c.most_common())


if __name__ == "__main__":
    main()
