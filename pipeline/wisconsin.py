"""Stage 2: the Wisconsin list -> site/wisconsin.json

Statewide base: Overture Maps listings (stage1.pkl), kept by the rule calibrate.py measured against official lists:
  - Meta listings and chain store feeds (AllThePlaces, DAC) are kept; single sources like Foursquare, BrightQuery and Microsoft
    are dropped (in Milwaukee and Dane County only 6-24% of them matched a licensed restaurant or tavern);
  - anything Google (2021) or Overture already shows as closed is dropped.
Official records: inside Milwaukee (City of Milwaukee active restaurant, tavern and retail food licenses) and Dane County
(Public Health Madison & Dane County licensed establishments), a listing that matches a license is marked official, and
licensed restaurants and taverns the map data doesn't have are added from the license list. Dane County also has inspections.
Ratings, reviews and price level: Google, Sep 2021 snapshot (UCSD Google Local). Fish fry, cheese curd and custard signals:
Google reviews written up to Sep 2021.
"""
import os, re, sys, json, math, hashlib, unicodedata, collections
import numpy as np, pandas as pd
from shapely.geometry import shape, Point
from shapely.prepared import prep
from rapidfuzz import fuzz
from common import (norm_name, nice, name_sim, cuisine, FOOD_COST, MARGIN, MARGIN_CUISINE, SPEND, GENERIC, _stems, DATA, WI, ROOT,
                    canon_city, town_key)
from brands import brand_of
import official
from listings_util import official_match
from official import street_key, street_nums

# WI_APP=1 builds the App Store data set: no Google-derived data at all (no ratings, reviews, price levels, review mentions,
# and no Google matching for inclusion). Listings are kept on Overture's own confidence instead (see calibrate.py --app).
APP = os.environ.get("WI_APP") == "1"
SITE = os.environ.get("WI_SITE") or os.path.join(ROOT, "data", "app") if APP else os.environ.get("WI_SITE") or os.path.join(ROOT, "site")
GOOD_SOURCES = {"meta", "AllThePlaces", "DAC"}
BASE = {1: 600_000, 2: 1_000_000, 3: 2_200_000, 4: 3_500_000}   # typical yearly sales by price tier (same as Chicago)
B_FIT = 0.764   # review-volume exponent fit on Chicago's published sales (chi-eats meta.model.b)
TAX_CUISINE = {
    "pizza_restaurant": "Pizza", "mexican_restaurant": "Mexican", "taco_restaurant": "Mexican", "texmex_restaurant": "Mexican",
    "sandwich_shop": "Sandwiches & Deli", "delicatessen": "Sandwiches & Deli", "bakery": "Bakery & Sweets", "donut_shop": "Bakery & Sweets",
    "dessert_shop": "Bakery & Sweets", "ice_cream_shop": "Bakery & Sweets", "bagel_shop": "Bakery & Sweets", "cupcake_shop": "Bakery & Sweets",
    "frozen_yogurt_shop": "Bakery & Sweets", "chocolatier": "Bakery & Sweets", "popcorn_shop": "Bakery & Sweets",
    "bar_and_grill_restaurant": "Bar & Pub", "gastropub": "Bar & Pub", "bar": "Bar & Pub", "brewery": "Bar & Pub", "pub": "Bar & Pub",
    "sports_bar": "Bar & Pub", "cocktail_bar": "Bar & Pub", "wine_bar": "Bar & Pub", "dive_bar": "Bar & Pub", "beer_bar": "Bar & Pub",
    "irish_pub": "Bar & Pub", "tiki_bar": "Bar & Pub", "speakeasy": "Bar & Pub", "hookah_bar": "Bar & Pub", "gay_bar": "Bar & Pub",
    "chinese_restaurant": "Chinese", "italian_restaurant": "Italian", "burger_restaurant": "Burgers",
    "breakfast_and_brunch_restaurant": "Breakfast & Diner", "diner": "Breakfast & Diner", "barbecue_restaurant": "BBQ",
    "chicken_restaurant": "Chicken & Wings", "chicken_wings_restaurant": "Chicken & Wings", "sushi_restaurant": "Japanese & Sushi",
    "japanese_restaurant": "Japanese & Sushi", "ramen_restaurant": "Japanese & Sushi", "seafood_restaurant": "Seafood", "poke_restaurant": "Seafood",
    "steakhouse": "Steakhouse", "indian_restaurant": "South Asian", "pakistani_restaurant": "South Asian", "thai_restaurant": "Thai",
    "hot_dog_restaurant": "Hot Dogs & Brats", "mediterranean_restaurant": "Mediterranean & Middle Eastern",
    "greek_restaurant": "Mediterranean & Middle Eastern", "middle_eastern_restaurant": "Mediterranean & Middle Eastern",
    "korean_restaurant": "Korean", "vietnamese_restaurant": "Vietnamese", "salad_bar": "Healthy & Vegan", "vegan_restaurant": "Healthy & Vegan",
    "vegetarian_restaurant": "Healthy & Vegan", "health_food_restaurant": "Healthy & Vegan", "coffee_shop": "Coffee & Café", "cafe": "Coffee & Café",
    "coffee_roastery": "Coffee & Café", "smoothie_juice_bar": "Healthy & Vegan", "juice_bar": "Healthy & Vegan", "bubble_tea_shop": "Coffee & Café",
    "tea_room": "Coffee & Café", "soul_food": "Soul & Southern", "southern_american_restaurant": "Soul & Southern",
    "cajun_and_creole_restaurant": "Seafood", "caribbean_restaurant": "Latin & Caribbean", "jamaican_restaurant": "Latin & Caribbean",
    "latin_american_restaurant": "Latin & Caribbean", "cuban_restaurant": "Latin & Caribbean", "puerto_rican_restaurant": "Latin & Caribbean",
    "peruvian_restaurant": "Latin & Caribbean", "african_restaurant": "African", "ethiopian_restaurant": "African",
    "french_restaurant": "German & European", "german_restaurant": "German & European", "polish_restaurant": "German & European",
    "spanish_restaurant": "German & European", "tapas_bar": "German & European", "noodles_restaurant": "Chinese",
    "belgian_restaurant": "German & European", "russian_restaurant": "German & European", "fondue_restaurant": "German & European",
    "scandinavian_restaurant": "German & European", "european_restaurant": "German & European", "eastern_european_restaurant": "German & European",
    "hungarian_restaurant": "German & European", "british_restaurant": "German & European", "dutch_restaurant": "German & European",
}


def curated_matcher(frame):
    """A researched place -> row of frame: same street number and street with a similar name; else a near-exact name in the same town;
    else a near-exact name that's unique statewide (the research uses the real municipality, the listings the mailing town)."""
    by_key = {}
    for i, a in enumerate(frame.street):
        sk = street_key(a)[1]
        for n in street_nums(a):
            if sk:
                by_key.setdefault((n, sk), []).append(i)
    towns = [canon_city(c).lower() if isinstance(c, str) else "" for c in frame.city]
    ks = list(frame.k.fillna(""))

    def match(c):
        keys = {norm_name(m) for m in (c.get("match_names") or [])} | {norm_name(c["name"])}
        keys.discard("")
        _, sk = street_key(c.get("address") or "")
        cands = set()
        for n in street_nums(c.get("address") or ""):
            cands.update(by_key.get((n, sk), []))
        best, bs = None, 0
        for i in cands:
            s_ = max((fuzz.token_set_ratio(m, ks[i]) for m in keys), default=0)
            if s_ >= 60 and s_ > bs:
                best, bs = i, s_
        if best is None and not c.get("chain"):
            ctown = (canon_city(c.get("city") or "") or "").lower()
            sim = [max(fuzz.ratio(m, k) for m in keys) if k else 0 for k in ks]
            hits = [i for i, s_ in enumerate(sim) if s_ >= 90 and towns[i] == ctown] or [i for i, s_ in enumerate(sim) if s_ >= 95]
            if len(hits) == 1:
                best = hits[0]
        return best
    return match


def pct(s):
    return (s.rank(pct=True) * 100).round(1)


o = pd.read_pickle(f"{WI}/stage1.pkl")
G = pd.read_pickle(f"{WI}/google21.pkl")
if APP:   # the App Store build ignores every Google 2021 match
    o["in21"] = False; o["closed21"] = False; o["gi"] = np.nan
calib = json.load(open(f"{WI}/calibration.json"))
areas = json.load(open(f"{WI}/calib_areas.json"))
AREA = {"mke": prep(shape(areas["Milwaukee"]).buffer(0.0003)), "dane": prep(shape(areas["Dane County"]).buffer(0.0003))}
o["area"] = [next((a for a, p in AREA.items() if p.contains(Point(x, y))), None) for x, y in zip(o.lon, o.lat)]

# ---------------------------------------------------------------- official records inside Milwaukee and Dane County
F = official.load()
F = F[F.active].reset_index(drop=True)
o["off"] = np.nan
for jur in ("mke", "dane"):
    sel = o.index[o.area == jur]
    L = o.loc[sel].reset_index(drop=True)
    R = F[F.jur == jur]
    m = official_match(L, R.reset_index(drop=True))
    for i, j in m.items():
        o.at[sel[i], "off"] = R.index[j]
o["official"] = o.off.notna()
print("listings matched to an active license:", int(o.official.sum()))

# ---------------------------------------------------------------- keep rule (see calibrate.py / calibration.json)
base_ok = ~o.j_junk & ~o.j_closedname & ~o.j_outside & ~o.j_far & ~o.ov_closed & ~(o.nowhere & ~o.in21)
CUR = json.load(open(f"{DATA}/curated.json")) if os.path.exists(f"{DATA}/curated.json") else []


def load_research():
    """data/research/app/*.json: hand-verified fish fries, supper clubs, custard stands (facts only, each with sources).
    An entry for a place already in curated.json adds its kinds and notes there; the rest become curated-style entries."""
    import glob
    out, by = [], {(norm_name(c["name"]), (canon_city(c.get("city")) or "").lower()): c for c in CUR}
    for f in sorted(glob.glob(f"{DATA}/research/app/*.json")):
        for e in json.load(open(f)):
            if e.get("open") is False or not e.get("name"):
                continue
            extra = {"tags": [k.lower() for k in (e.get("kinds") or [])], "fish": e.get("fish") or [], "fry_days": e.get("fish_fry_days") or [],
                     "sides": e.get("sides") or [], "note": e.get("note"), "website": e.get("website"), "rsources": e.get("sources") or []}
            key = (norm_name(e["name"]), (canon_city(e.get("city")) or "").lower())
            c = by.get(key)
            if c is None:
                c = {"name": e["name"], "address": e.get("address"), "city": e.get("city"), "zip": e.get("zip"), "chain": False,
                     "match_names": [e["name"].upper()], "founded": e.get("founded"), "open": True, "tags": [], "research_only": True}
                by[key] = c; out.append(c)
            c["tags"] = list(dict.fromkeys((c.get("tags") or []) + extra["tags"]))
            for k in ("fish", "fry_days", "sides", "rsources"):
                c[k] = list(dict.fromkeys((c.get(k) or []) + extra[k]))
            for k in ("note", "website"):
                c[k] = c.get(k) or extra[k]
            if not c.get("founded") and e.get("founded"):
                c["founded"] = e["founded"]
    return out


CUR = CUR + load_research()
print("verified places: curated", sum(1 for c in CUR if not c.get("research_only")), "+ research-only", sum(1 for c in CUR if c.get("research_only")))
_m = curated_matcher(o[base_ok].reset_index())
_bo = o.index[base_ok]
verified = pd.Series(False, index=o.index)
for c in CUR:
    if c.get("open") is not False:
        j = _m(c)
        if j is not None:
            verified[_bo[j]] = True
keep = base_ok & (~o.closed21 | o.official | verified) & (o.src.isin(GOOD_SOURCES) | o.official | verified)
if APP:
    # measured against Milwaukee's and Dane County's license lists (calibration_app.json): Meta listings with Overture confidence >= 0.95
    # matched a licensed business 75-79% of the time, Meta 0.90-0.95 38-48%, chain store feeds 29-56%; lower-confidence Meta 22-24%,
    # BrightQuery >= 0.95 27-31% and everything else 10-12% are dropped
    conf = o.confidence.fillna(0)
    keep = base_ok & (o.official | verified | ((o.src == "meta") & (conf >= 0.9)) | o.src.isin(["AllThePlaces", "DAC"]))
print("hand-verified places kept despite the source rule:", int((verified & ~(base_ok & (~o.closed21 | o.official) & (o.src.isin(GOOD_SOURCES) | o.official))).sum()))
print("kept listings:", int(keep.sum()), "of", len(o), "| dropped single-source (Foursquare/BrightQuery/Microsoft):",
      int((base_ok & ~o.src.isin(GOOD_SOURCES) & ~o.official).sum()), "| closed per Google 2021:", int((base_ok & o.closed21 & ~o.official).sum()))
o = o[keep].reset_index(drop=True)

# ---------------------------------------------------------------- duplicate listings of one place
o["biz"] = o.off.map(lambda j: F.biz.iat[int(j)] if j == j else np.nan)
o["rank"] = o.official.astype(int) * 8 + o.in21.astype(int) * 4 + o.src.isin(GOOD_SOURCES).astype(int) * 2 + o.confidence.fillna(0)
o = o.sort_values("rank", ascending=False).reset_index(drop=True)
cell, drop = {}, set()
for i, r in o.iterrows():
    key = (round(r.lat / 0.001), round(r.lon / 0.0013))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in cell.get((key[0] + dy, key[1] + dx), []):
                d_ = math.hypot((o.lat.iat[j] - r.lat) * 111000, (o.lon.iat[j] - r.lon) * 79000)
                same_biz = r.biz == r.biz and r.biz == o.biz.iat[j] and name_sim(r.k, o.k.iat[j]) >= 80
                if same_biz or (d_ < 80 and (r.k == o.k.iat[j] or (fuzz.token_set_ratio(r.k, o.k.iat[j]) >= 92 and r.st & o.st.iat[j]))) or (
                        d_ < 150 and isinstance(r.brand_n, str) and r.brand_n == o.brand_n.iat[j]):
                    drop.add(i); break
            if i in drop: break
        if i in drop: break
    if i not in drop:
        cell.setdefault(key, []).append(i)
o = o.drop(index=list(drop)).reset_index(drop=True)
akey = [(b if isinstance(b, str) else k, n, c) if n and isinstance(c, str) else None for b, k, n, c in zip(o.brand_n, o.k, o.num, o.city)]
seen, dup = set(), []
for a in akey:   # o is sorted best-first, so the better-sourced copy survives
    dup.append(a is not None and a in seen)
    if a is not None:
        seen.add(a)
has_addr = o.num.notna()
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    with_a, without = grp[has_addr[grp.index]], grp[~has_addr[grp.index]]
    for i, r in without.iterrows():
        if len(with_a) and (np.hypot((with_a.lat - r.lat) * 111, (with_a.lon - r.lon) * 79) < 1.5).any():
            dup[i] = True
o = o[~np.array(dup)].reset_index(drop=True)
near_dup = set()
for (k, c), grp in o[o.brand_n.isna() & o.k.fillna("").str.len().ge(4) & o.city.notna()].groupby(["k", "city"]):
    if len(grp) < 2 or not (_stems(k) - GENERIC):
        continue
    idx = list(grp.index)   # already best-first
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if idx[b] in near_dup or idx[a] in near_dup:
                continue
            if math.hypot((o.lat[idx[a]] - o.lat[idx[b]]) * 111000, (o.lon[idx[a]] - o.lon[idx[b]]) * 79000) < 500 and not (o.official[idx[a]] and o.official[idx[b]]):
                near_dup.add(idx[b])
for (k, c), grp in o[o.brand_n.isna() & o.k.fillna("").str.len().ge(4) & o.city.notna()].groupby(["k", "city"]):
    if len(grp) < 2 or not (_stems(k) - GENERIC):
        continue
    good = grp[grp.in21 | grp.official]
    for i in grp.index[~(grp.in21 | grp.official)]:
        if len(good) and (np.hypot((good.lat - o.lat[i]) * 111, (good.lon - o.lon[i]) * 79) < 1.5).any():
            near_dup.add(i)
o = o.drop(index=list(near_dup)).reset_index(drop=True)
print("after merging duplicate listings:", len(o), "(dropped", len(drop) + sum(dup) + len(near_dup), "; same name within 500 m:", len(near_dup), ")")
confirmed = ((o.src == "meta") & (o.confidence.fillna(0) >= 0.95)) if APP else o.in21
o["tier"] = np.where(o.official, "official", np.where(confirmed, "both", "listing"))

# ---------------------------------------------------------------- licensed places the map listings don't have
found = set(o.biz.dropna())
add = F[F.kind.isin(["restaurant", "tavern"]) & ~F.biz.isin(found)].copy()
add["pri"] = add.kind.map({"restaurant": 0, "tavern": 1})
add = add.sort_values("pri").drop_duplicates("biz")
print("licensed restaurants/taverns not in the map listings:", len(add), add.jur.value_counts().to_dict())

# Dane County records have no coordinates: place them on Overture's address points (number + street, same town if possible)
ap = pd.read_parquet(f"{WI}/addresses_dane.parquet")
ap["sk"] = ap.number.astype(str) + " " + ap.street.fillna("")
ap["key"] = [street_key(a)[1] for a in ap.sk]
ap["muni"] = ap.address_levels.map(lambda L: re.sub(r"^(?:City|Village|Town) of ", "", L[-1]["value"]) if len(L) else None)
apk = {}
for n, k, la, lo, pc, pz, mu in zip(ap.number.astype(str), ap.key, ap.lat, ap.lon, ap.postal_city, ap.postcode, ap.muni):
    apk.setdefault((n, k), []).append((la, lo, pc, pz, mu))


def geocode(num, st, city):
    pts = apk.get((num, st), [])
    if not pts:
        return None
    same = [p for p in pts if city and p[4] and p[4].lower() == city.lower()]
    pts = same or pts
    la, lo = np.median([p[0] for p in pts]), np.median([p[1] for p in pts])
    if max(math.hypot((p[0] - la) * 111, (p[1] - lo) * 79) for p in pts) > 1.0:
        return None   # the same street address in two towns: don't guess
    return la, lo, pts[0][2], pts[0][3]


canon_town = canon_city


rows = []
for _, f in add.iterrows():
    lat, lon, city, zip5 = f.lat, f.lon, f.city, None
    if f.jur == "dane":
        g = geocode(f.num, f.street, canon_town(f.city))
        if g:
            lat, lon, city, zip5 = g[0], g[1], g[2], g[3]
        else:
            city = canon_town(f.city)
    rows.append({"id": f.lic, "name": f["name"], "street": f.addr, "city": city, "zip": zip5, "lat": lat, "lon": lon, "cat": "bar" if f.kind == "tavern" else "restaurant",
                 "tax": None, "confidence": np.nan, "brand": None, "src": "official", "official": True, "off": f.name, "biz": f.biz, "tier": "official",
                 "in21": False, "closed21": False, "dom": None, "area": f.jur})
A = pd.DataFrame(rows)
print("added from license lists:", len(A), "| without a map location:", int(A.lat.isna().sum()))


def clean_official(n):
    n = re.split(r"\s*;\s*", n or "")[0]
    n = re.sub(r"^(?:Restaurant|Food|Tavern) Operations?\s*[-–:]\s*", "", n, flags=re.I)
    n = re.sub(r"\s*#\s*\d+\w*.*$|\s*\(#?[A-Z]?\d+\)|\s+\d{3,}\s*$", "", n or "")
    n = re.sub(r",?\s+(?:INC|LLC|L\.L\.C|CORP|CORPORATION|LTD)\.?\s*$", "", n, flags=re.I)
    n = re.split(r"\s*/\s*", n)[0] if len(n) > 34 and "/" in n else n
    n = n.strip(" -,&/")
    return nice(n) if n.isupper() or n.islower() else n


A["name"] = A.name.map(clean_official)
A["k"] = A.name.map(norm_name)
A["st"] = A.k.map(lambda k: _stems(k) - GENERIC if k else set())
A["num"] = A.street.map(lambda a: (re.match(r"\s*(\d+)", a or "") or [None, None])[1])
A["brand_n"] = A.k.map(brand_of)

# Google 2021 listings for the added rows (the ones no map listing took)
taken = set(o.gi.dropna().astype(int))
grid = {}
for i, (la, lo) in enumerate(zip(G.latitude, G.longitude)):
    grid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(i)
pairs = []
for ai, r in ([] if APP else A.iterrows()):
    if not r.k or r.lat != r.lat:
        continue
    gy, gx = round(r.lat / 0.0015), round(r.lon / 0.002)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for gi in grid.get((gy + dy, gx + dx), []):
                if gi in taken or not G.k.iat[gi] or G.closed21.iat[gi]:
                    continue
                dist = math.hypot((G.latitude.iat[gi] - r.lat) * 111000, (G.longitude.iat[gi] - r.lon) * 79000)
                if dist > 200:
                    continue
                s = name_sim(r.k, G.k.iat[gi])
                same_num = r.num is not None and G.num.iat[gi] == r.num
                if same_num and r.st & G.st.iat[gi]:
                    s = max(s, 80)
                if s < 95 and not r.st & G.st2.iat[gi]:
                    continue
                if (s >= 88 and dist < 150) or (s >= 75 and same_num):
                    pairs.append((s + (10 if same_num else 0) - dist / 25, ai, gi))
A["gi"] = np.nan
ta, tg = set(), set()
for sc, ai, gi in sorted(pairs, key=lambda t: -t[0]):
    if ai in ta or gi in tg:
        continue
    ta.add(ai); tg.add(gi); A.at[ai, "gi"] = gi
A["in21"] = A.gi.notna()
# Dane records with no address point: use the matched Google listing's location, else they can't be mapped
nog = A.lat.isna() & A.gi.notna()
A.loc[nog, "lat"] = A.loc[nog, "gi"].map(lambda g: G.latitude.iat[int(g)])
A.loc[nog, "lon"] = A.loc[nog, "gi"].map(lambda g: G.longitude.iat[int(g)])
print("added rows matched to Google 2021:", int(A.in21.sum()), "| still unmapped:", int(A.lat.isna().sum()))
# a licensed place the address match missed can sit on top of its own map listing under a slightly different name or the other
# street of a corner ("Savoy's" / "Savoy's Night Club", "Noodles & Company" on Sligo Dr / Mineral Point Rd): merge it into that listing,
# unless the listing already matched a license of its own (Centro Cafe and Bar Centro are neighbors, not one place)
from listings_util import _close_words
kgrid = {}
for j, (la, lo) in enumerate(zip(o.lat, o.lon)):
    kgrid.setdefault((round(la / 0.0015), round(lo / 0.002)), []).append(j)
merge, same_lic = {}, set()
o_addr = {}
for j, a in enumerate(o.street):
    sk = street_key(a)[1]
    for n in street_nums(a):
        if sk:
            o_addr.setdefault((n, sk), []).append(j)
for ai, r in A.iterrows():
    if not r.k:
        continue
    if r.lat != r.lat:   # no coordinates (a Dane County record with no address point): the same street address and a similar name
        sk = street_key(r.street)[1]
        for n in street_nums(r.street):
            for j in o_addr.get((n, sk), []):
                s = name_sim(r.k, o.k.iat[j]) if o.k.iat[j] else 0
                if s >= 60 or bool(r.st & o.st.iat[j]):
                    (same_lic.add(ai) if o.official.iat[j] else merge.setdefault(ai, j))
        continue
    best, bs = None, -1
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in kgrid.get((round(r.lat / 0.0015) + dy, round(r.lon / 0.002) + dx), []):
                if j in merge.values():
                    continue
                dist = math.hypot((o.lat.iat[j] - r.lat) * 111000, (o.lon.iat[j] - r.lon) * 79000)
                s = name_sim(r.k, o.k.iat[j]) if o.k.iat[j] else 0
                if o.official.iat[j]:   # a listing with its own license: only the same business's second license (Uppa Yard's tavern license)
                    if dist <= 80 and s >= 95:
                        same_lic.add(ai)
                    continue
                shared = bool(r.st & o.st.iat[j]) or _close_words(r.st, o.st.iat[j])
                if (dist <= 60 and (s >= 88 or (shared and s >= 60))) or (dist <= 25 and s >= 75):
                    if s - dist / 10 > bs:
                        best, bs = j, s - dist / 10
    if best is not None:
        merge[ai] = best
for ai, j in merge.items():
    for c in ("official", "off", "biz", "tier", "area"):
        o.at[o.index[j], c] = A.at[ai, c]
A = A.drop(index=list(set(merge) | same_lic)).reset_index(drop=True)
print("second licenses of places already on the list:", len(same_lic - set(merge)))
print("license rows merged into a map listing on the second pass:", len(merge), "| license rows added:", len(A))
# food trucks and caterers licensed at a shared kitchen: 5+ license-only places at one address
akey = [(n, st) for n, st in zip(A.num, A.street.map(lambda a: street_key(a)[1]))]
shared_n = collections.Counter(akey)
A["lic_shared"] = [shared_n[k] >= 5 and not g for k, g in zip(akey, A.in21)]
print("license-only places at shared kitchens (hidden with non-restaurants):", int(A.lic_shared.sum()))
o = pd.concat([o, A], ignore_index=True)
# one spelling per town across map listings, license lists and address points
o["city"] = o.city.map(canon_city)
main = o.city.dropna().groupby(o.city.dropna().map(town_key)).agg(lambda x: x.mode().iat[0])
o["city"] = o.city.map(lambda c: main.get(town_key(c), c) if isinstance(c, str) else c)
o["street"] = o.street.map(lambda a: re.sub(r"\bAV\b", "Ave", re.sub(r"\bBND\b", "Bend", a)) if isinstance(a, str) else a)
# hand-verified open places the map listings don't have as a place to eat (inns, a bowling-alley supper club, a resort dining room):
# placed with their Google listing. Ratings come along only when Google files that listing as a restaurant, not as the hotel or lanes.
import gzip
_m = curated_matcher(o)
missing = [c for c in CUR if c.get("open") is not False and not c.get("chain") and _m(c) is None]
added = []
if not APP:
    FULL = []
    with gzip.open(f"{DATA}/meta-Wisconsin.json.gz", "rt") as f:
        for line in f:
            d = json.loads(line)
            if d.get("latitude") and not (d.get("state") or "").startswith("Permanently closed"):
                FULL.append(d)
    fk = [norm_name(d["name"]) for d in FULL]
HOSTCAT = re.compile(r"hotel|inn\b|resort|lodge|motel|bowling|museum|store|shop|market|cheese|farm|grocery|bed & breakfast|campground|marina|winery", re.I)
SHOPCAT = r"store|shop|market|manufacturer|farm|butcher|creamery|wholesale|supplier|outlet"
if APP:
    # the App Store build places them with Overture's own listing of the business (any category: inn, bowling alley, shop), else an address point
    import duckdb
    OV = duckdb.connect().execute(f"""SELECT name, street, city, zip, lat, lon, cat, tax FROM '{WI}/overture_wi_bbox.parquet'
                                      WHERE region = 'WI' AND name IS NOT NULL""").df()
    OV["k"] = OV.name.map(norm_name); OV["town"] = OV.city.map(lambda c: (canon_city(c) or "").lower())
    ov_by_town = {t: g for t, g in OV.groupby("town")}
    GEOCACHE = json.load(open(f"{DATA}/research/geocode_census.json")) if os.path.exists(f"{DATA}/research/geocode_census.json") else {}
    GEO_TODO = []

    def geo_key(c):
        a, t = (c.get("address") or "").strip(), (c.get("city") or "").strip()
        return f"{a}, {t}, WI {c.get('zip') or ''}".strip() if re.match(r"\s*\d", a) and t else None
    AP = pd.read_parquet(f"{WI}/addresses_wi.parquet") if os.path.exists(f"{WI}/addresses_wi.parquet") else None
    if AP is not None:
        AP = AP[AP.state == "WI"].copy()
        AP["key"] = [street_key(f"{n} {s}")[1] for n, s in zip(AP.number.astype(str), AP.street.fillna(""))]
        AP["town"] = [(canon_city(re.sub(r"^(?:City|Village|Town) of ", "", m or "")) or "").lower() for m in AP.muni]
        AP["ptown"] = AP.postal_city.map(lambda c: (canon_city(c) or "").lower())
        ap_by = {k: g for k, g in AP.groupby(["number", "key"])}
for c in missing:
    keys = {norm_name(m) for m in (c.get("match_names") or [])} | {norm_name(c["name"])}
    keys.discard("")
    nums = street_nums(c.get("address") or "")
    town = (canon_city(c.get("city") or "") or "").lower()
    if APP:
        spot = None
        g = ov_by_town.get(town)
        if g is not None:
            sims = [max(fuzz.ratio(m, k) for m in keys) if isinstance(k, str) and k else 0 for k in g.k]
            j = int(np.argmax(sims)) if len(sims) else -1
            if j >= 0 and sims[j] >= 88:
                h = g.iloc[j]
                spot = (h["lat"], h["lon"], (h["zip"] or "")[:5] or c.get("zip"), str(h["cat"] or "") + " " + str(h["tax"] or ""))
        if spot is None and AP is not None:
            _, sk = street_key(c.get("address") or "")
            for n in nums:
                cand = ap_by.get((n, sk))
                if cand is not None:
                    same = cand[(cand.town == town) | (cand.ptown == town)]
                    cand = same if len(same) else cand
                    if len(cand) and (cand.lat.max() - cand.lat.min()) < 0.01:
                        spot = (cand.lat.median(), cand.lon.median(), cand.postcode.iloc[0] or c.get("zip"), ""); break
        if spot is None:
            # last resort: the US Census geocoder's match for the verified street address (pipeline/geocode_research.py fills the cache)
            gq = geo_key(c)
            hit = GEOCACHE.get(gq) if gq else None
            if hit:
                spot = (hit["lat"], hit["lon"], hit.get("zip") or c.get("zip"), "")
            else:
                if gq:
                    GEO_TODO.append(gq)
                continue
        la, lo, zp, catx = spot
        added.append({"id": "research-" + c["name"], "name": c["name"], "street": c.get("address"), "city": canon_city(c.get("city")), "zip": zp,
                      "lat": la, "lon": lo, "cat": "restaurant", "tax": None, "confidence": np.nan, "brand": None, "src": "research",
                      "official": False, "off": np.nan, "biz": np.nan, "tier": "both", "in21": False, "closed21": False, "dom": None, "area": None,
                      "gi": np.nan, "k": norm_name(c["name"]), "st": _stems(norm_name(c["name"])) - GENERIC,
                      "num": (re.match(r"\s*(\d+)", c.get("address") or "") or [None, None])[1], "brand_n": None, "venue": False, "web": c.get("website"),
                      "shop": bool(re.search(SHOPCAT, catx, re.I)) and not re.search(r"TAVERN|RESTAURANT|SUPPER|INN|GRILL|BAR\b|CAFE", norm_name(c["name"]))})
        continue
    best, bs = None, 0
    for i, k in enumerate(fk):
        if not k or not any(fuzz.ratio(m, k) >= 88 or (len(m.split()) >= 2 and fuzz.token_set_ratio(m, k) >= 95) for m in keys):
            continue
        addr = FULL[i].get("address") or ""
        hit_num = any(re.search(rf"\b{n}\b", addr) for n in nums)
        hit_town = bool(town) and town in addr.lower()
        if not (hit_num or hit_town):
            continue
        sc = 2 * hit_num + hit_town + math.log1p(FULL[i].get("num_of_reviews") or 0) / 10
        if sc > bs:
            best, bs = i, sc
    if best is None:
        continue
    d = FULL[best]
    cats = d.get("category") or []
    host = bool(cats) and bool(HOSTCAT.search(cats[0]))
    G.loc[len(G)] = {**{c_: None for c_ in G.columns}, "name": d["name"], "address": d.get("address"), "gmap_id": d.get("gmap_id"),
                     "latitude": d["latitude"], "longitude": d["longitude"], "category": [] if host else cats,
                     "avg_rating": None if host else d.get("avg_rating"), "num_of_reviews": None if host else d.get("num_of_reviews"),
                     "price": None if host else d.get("price"), "state": d.get("state"), "description": d.get("description"),
                     "k": norm_name(d["name"]), "st": set(), "closed21": False}
    zm = re.search(r"\bWI (5[34]\d{3})", d.get("address") or "")
    added.append({"id": "research-" + c["name"], "name": c["name"], "street": c.get("address"), "city": canon_city(c.get("city")), "zip": zm.group(1) if zm else None,
                  "lat": d["latitude"], "lon": d["longitude"], "cat": "restaurant", "tax": None, "confidence": np.nan, "brand": None, "src": "research",
                  "official": False, "off": np.nan, "biz": np.nan, "tier": "both", "in21": True, "closed21": False, "dom": None, "area": None,
                  "gi": len(G) - 1, "k": norm_name(c["name"]), "st": _stems(norm_name(c["name"])) - GENERIC, "num": (re.match(r"\s*(\d+)", c.get("address") or "") or [None, None])[1],
                  "brand_n": None, "venue": False,
                  "shop": bool(cats) and bool(re.search(SHOPCAT, cats[0], re.I)) and not re.search(r"TAVERN|RESTAURANT|SUPPER|INN|GRILL|BAR\b|CAFE", norm_name(c["name"]))})
if added:
    o = pd.concat([o, pd.DataFrame(added)], ignore_index=True)
if APP:
    json.dump(sorted(set(GEO_TODO)), open(f"{DATA}/research/geocode_todo.json", "w"), indent=1)
    print("verified addresses waiting for the Census geocoder:", len(set(GEO_TODO)), "(run pipeline/geocode_research.py, then rebuild)")
print("hand-verified places added (not in the map listings as a place to eat):", len(added), "of", len(missing), "| not placed:",
      [c["name"] for c in missing if not any(a["name"] == c["name"] for a in added)])


# towns that share a name in different corners of the state (Scott in Burnett and Brown counties) are two towns
from shapely.geometry import Polygon
from shapely.ops import unary_union as _uu
_cty = [(c["name"], prep(_uu([Polygon(r) for r in c["c"] if len(r) >= 4]).buffer(0.01))) for c in json.load(open(f"{WI}/wi_shapes.json"))["counties"]]
o["county"] = [next((n for n, p in _cty if la == la and p.contains(Point(lo, la))), None) for la, lo in zip(o.lat, o.lon)]
split = 0
for c, grp in o[o.city.notna() & o.county.notna()].groupby("city"):
    if grp.county.nunique() < 2:
        continue
    med = grp.groupby("county")[["lat", "lon"]].median()
    far = max(math.hypot((a.lat - b.lat) * 111, (a.lon - b.lon) * 79) for _, a in med.iterrows() for _, b in med.iterrows())
    if far > 40:
        o.loc[grp.index, "city"] = [f"{c} ({n.replace(' County', '')} Co.)" for n in grp.county]
        split += 1
print("same-name towns split by county:", split)

# ---------------------------------------------------------------- fields
gi = [int(v) if v == v and v is not None else None for v in o.gi]
o["rating"] = [G.avg_rating.iat[i] if i is not None else np.nan for i in gi]
o["reviews"] = [G.num_of_reviews.iat[i] if i is not None else np.nan for i in gi]
o["gprice"] = [len(G.price.iat[i]) if i is not None and isinstance(G.price.iat[i], str) else np.nan for i in gi]
o["gcats"] = ["|".join(G.category.iat[i] or []) if i is not None else "" for i in gi]
o["gmap_id"] = [G.gmap_id.iat[i] if i is not None else None for i in gi]
o["gdesc"] = [(G.description.iat[i] or "") if i is not None else "" for i in gi]
o["name_out"] = [b if isinstance(b, str) and fuzz.ratio(norm_name(n), norm_name(b)) >= 88 else nice(n) if n.isupper() or n.islower() else n
                 for n, b in zip(o.name, o.brand_n)]
from common import CUISINE_RULES


def pick_cuisine(tax, k, gcats, raw):
    for c, pat in CUISINE_RULES[:-1]:          # a specific word in the name wins ("Mickey-Lu Bar-B-Q", "Paul's Pelmeni")
        if pat.search(k or ""):
            return c
    if isinstance(tax, str) and tax in TAX_CUISINE:
        return TAX_CUISINE[tax]
    return cuisine(k, gcats, raw)              # "bar"-type names, then Google's categories


o["cuisine"] = [pick_cuisine(t, k, gc, n) for t, k, gc, n in zip(o.tax, o.k, o.gcats, o.name)]
first_cat = o.gcats.str.split("|").str[0].fillna("")
cafe_tax = o.tax.isin(["cafe", "coffee_shop"]) & o.cuisine.eq("Coffee & Café") & first_cat.ne("") & ~first_cat.str.contains(r"Coffee|Cafe|Café|Espresso|Tea|Bakery|Donut|Dessert|Ice cream|Juice|Breakfast")
o.loc[cafe_tax, "cuisine"] = [cuisine(k, g, "") for k, g in zip(o.loc[cafe_tax, "k"], o.loc[cafe_tax, "gcats"])]
o.loc[o.cat.isin(["bar", "brewery"]) & (o.cuisine == "American & Other"), "cuisine"] = "Bar & Pub"
o.loc[o.cat.isin(["coffee_shop", "cafe"]) & (o.cuisine == "American & Other"), "cuisine"] = "Coffee & Café"
o.loc[o.city.fillna("") == "", "city"] = None


# brand sanity: a brand rule that matched a name prefix must agree with the listing's website, Overture's brand feed, or its kind of food
def mode(x):
    return x.mode().iat[0]


bdom = {}
for b, grp in o[o.brand_n.notna()].groupby("brand_n"):
    d = grp.dom.dropna()
    if len(d) >= 3:
        top, n = collections.Counter(d).most_common(1)[0]
        if n >= 0.5 * len(d):
            bdom[b] = top
FAMILY = {"Chicken & Wings": "quick", "Burgers": "quick", "Hot Dogs & Brats": "quick", "Sandwiches & Deli": "cafe", "Pizza": "pizza",
          "Mexican": "mex", "Latin & Caribbean": "mex", "Coffee & Café": "cafe", "Bakery & Sweets": "cafe", "Frozen Custard": "cafe",
          "Breakfast & Diner": "cafe", "Healthy & Vegan": "cafe", "Steakhouse": "sitdown", "Supper Club": "sitdown", "Seafood": "sea",
          "Bar & Pub": "bar", "Italian": "italian", "Chinese": "asian", "Japanese & Sushi": "asian", "Thai": "asian", "Korean": "asian",
          "Vietnamese": "asian", "South Asian": "sasian", "Mediterranean & Middle Eastern": "med", "German & European": "sitdown", "BBQ": "bbq",
          "Soul & Southern": "soul", "African": "african"}
brand_cuisine = o[o.brand_n.notna()].groupby("brand_n").cuisine.agg(mode)


def core(k):
    w = [x for x in k.split() if x not in GENERIC and x not in ("RESTAURANT", "RESTAURANTS", "CAFE", "STORE")]
    return " ".join(w) or k


def brand_ok(b, dm, cu, tax, obrand, name, src):
    if not isinstance(b, str):
        return None
    dm = dm if isinstance(dm, str) else None
    nk, bk = norm_name(name), norm_name(b)
    if src not in ("AllThePlaces", "DAC") and brand_of(nk) != b:
        return None                                 # only Overture's label says so ("Golden Chicken" labeled Golden Chick)
    ob = norm_name(obrand) if isinstance(obrand, str) else ""
    brand_feed = src in ("AllThePlaces", "DAC")
    label = bool(ob) and fuzz.token_set_ratio(ob, bk) >= 80
    related = brand_feed or fuzz.partial_ratio(bk, nk) >= 60 or (label and fuzz.partial_ratio(ob, nk) >= 60)
    if not related:
        return None
    squashed = re.sub(r"[^a-z]", "", b.lower())
    own_site = dm and (bdom.get(b) == dm or dm.split(".")[0].replace("-", "") in (squashed, squashed + "s"))
    exact = fuzz.ratio(core(nk), core(bk)) >= 90 or (label and fuzz.ratio(core(nk), core(ob)) >= 90) \
        or (len(bk) >= 6 and (nk == bk or nk.startswith(bk + " ")))
    if exact or own_site or (label and brand_feed):
        return b
    if dm and b in bdom and src != "BrightQuery":
        return None
    want = brand_cuisine.get(b)
    if isinstance(tax, str) and tax in TAX_CUISINE and want and FAMILY.get(cu) and FAMILY.get(want) and FAMILY[cu] != FAMILY[want]:
        return None
    return b


old_brand = o.brand_n.copy()
o["brand_n"] = [brand_ok(b, dm, cu, t, ob, n, sr) for b, dm, cu, t, ob, n, sr in zip(o.brand_n, o.dom, o.cuisine, o.tax, o.brand, o.name, o.src)]
rej = o[old_brand.notna() & o.brand_n.isna()]
print("brand matches rejected:", len(rej), collections.Counter(old_brand[rej.index]).most_common(10))
o.loc[o.brand_n.notna(), "name_out"] = [b if fuzz.ratio(norm_name(n), norm_name(b)) >= 80 or len(norm_name(n)) <= len(norm_name(b)) + 2 else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]


def chain_mode(x):
    real = x[x != "American & Other"]
    return (real if len(real) else x).mode().iat[0]


CHAIN_CUISINE = {"Culver's": "Burgers", "Kopp's Frozen Custard": "Frozen Custard", "Freddy's": "Burgers", "Noodles & Company": "Healthy & Vegan",
                 "Cousins Subs": "Sandwiches & Deli", "Toppers Pizza": "Pizza", "Pizza Ranch": "Pizza", "Perkins": "Breakfast & Diner",
                 "George Webb": "Breakfast & Diner", "Dairy Queen": "Bakery & Sweets", "Cold Stone Creamery": "Bakery & Sweets",
                 "Baskin-Robbins": "Bakery & Sweets", "Chocolate Shoppe Ice Cream": "Bakery & Sweets", "Einstein Bros. Bagels": "Bakery & Sweets",
                 "Big Apple Bagels": "Bakery & Sweets", "Panera Bread": "Sandwiches & Deli", "Caribou Coffee": "Coffee & Café",
                 "Taco John's": "Mexican", "A&W": "Burgers", "Hardee's": "Burgers", "HuHot Mongolian Grill": "Chinese",
                 "Famous Dave's": "BBQ", "Dickey's Barbecue Pit": "BBQ", "Texas Roadhouse": "Steakhouse", "Tropical Smoothie Cafe": "Healthy & Vegan",
                 "Jamba": "Healthy & Vegan", "Smoothie King": "Healthy & Vegan", "Forage Kitchen": "Healthy & Vegan", "Erbert & Gerbert's": "Sandwiches & Deli",
                 "Milio's Sandwiches": "Sandwiches & Deli", "Starbucks": "Coffee & Café", "Dunkin'": "Coffee & Café", "Cracker Barrel": "American & Other",
                 "Golden Corral": "American & Other", "Charcoal Grill & Rotisserie": "American & Other"}
allc = o.loc[o.brand_n.notna(), ["brand_n", "cuisine"]]
all_brand_cuisine = allc.groupby("brand_n").cuisine.agg(chain_mode)
o.loc[o.brand_n.notna(), "cuisine"] = o.loc[o.brand_n.notna(), "brand_n"].map(lambda b: CHAIN_CUISINE.get(b) or all_brand_cuisine.get(b))

# price: Google price level, else the chain's usual level, else the cuisine's usual level (both from Wisconsin's own Google data)
o["price"] = o.gprice
o["price_est"] = o.price.isna().astype(int)
bp = o[o.gprice.notna()].groupby("brand_n").gprice.median()
o.loc[o.price.isna() & o.brand_n.notna(), "price"] = o.brand_n.map(bp)
cp = o[o.gprice.notna()].groupby("cuisine").gprice.median()
o.loc[o.price.isna(), "price"] = o.cuisine.map(cp)
o["price"] = o.price.fillna(2).round().clip(1, 4).astype(int)

# chain size statewide. Unbranded same-name places count as one chain only when they share a website ("Corner Tap" x5 isn't a chain)
bc = o.brand_n.value_counts()
o["chain_n"] = o.brand_n.map(lambda b: int(bc.get(b, 0)) if isinstance(b, str) else 1)
STORE_DOMS_ALL = {"caseys.com", "kwiktrip.com", "speedway.com", "hy-vee.com", "walmart.com", "samsclub.com", "picknsave.com", "target.com", "costco.com",
                  "festfoods.com", "woodmans-food.com", "metromarket.net", "meijer.com", "holidaystationstores.com", "fleetfarm.com", "menards.com"}
first_stem = o.k.fillna("").map(lambda k: next((w for w in k.split() if w not in GENERIC and len(w) >= 3), None))
grpkey = pd.Series([(d, s) if isinstance(d, str) and isinstance(s, str) and not isinstance(b, str) and d not in STORE_DOMS_ALL else None for d, s, b in zip(o.dom, first_stem, o.brand_n)], index=o.index)
gsize = grpkey.dropna().value_counts()
member = [g is not None and gsize.get(g, 0) >= 2 for g in grpkey]
o.loc[member, "chain_n"] = [int(gsize[g]) for g, m in zip(grpkey, member) if m]
o["ckey"] = grpkey.map(lambda g: "|".join(g) if g else None)
chain_dom = set(o.ckey[member])
grp_cuisine = o[member].groupby("ckey").cuisine.agg(chain_mode)
o.loc[member, "cuisine"] = [grp_cuisine.get(k) for k in o.loc[member, "ckey"]]
sib = o.gprice.notna()
for key, sel in (("brand_n", o.brand_n.notna()), ("ckey", pd.Series(member, index=o.index))):
    med = o[sel & sib].groupby(key).gprice.median()
    fill = sel & (o.price_est == 1) & o[key].isin(med.index)
    o.loc[fill, "price"] = o.loc[fill, key].map(med).round().clip(1, 4).astype(int)
print("name-based chains:", len(chain_dom), "|", int(sum(member)), "locations")

o["bar"] = o.cat.isin(["bar", "brewery"]) | (o.cuisine == "Bar & Pub")
o["name_out"] = o.name_out.map(lambda n: re.sub(r"\b(?:Tcby|Ihop|Bj's|Bjs)\b", lambda m: {"tcby": "TCBY", "ihop": "IHOP"}.get(m.group(0).lower(), "BJ's"), n))
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]+")
CJK = r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff\uff00-\uffef]"
TAILWORDS = re.compile(r"^(?:best|award|voted|magazine|official|order|delivery|takeout|take out|catering|now open|open|to go|curbside|franchise|inside .*|"
                       r"(?:(?:ice cream|chocolates?|fudge|coffee|cafe|café|restaurant|bar|grill|pizza|shawarma|hookah lounge|juicy seafood|latin tavern|"
                       r"bakery|deli|sandwiches|tacos|gifts?|shopping|treats|sweets|full bar|food|game room|drinks|spirits|live music|events|patio|"
                       r"lodging|rooms|resort|motel|campground|cocktails|beer|wine|burgers|wings|craft beer|sports bar|and|&|,|-|\s)+))$", re.I)


def tidy(n, brand):
    """Emoji and non-Latin duplicates of an English name, LLC in the middle, marketing tails, notes in parentheses."""
    n = unicodedata.normalize("NFKC", n)   # "𝗖𝗼𝘄𝗹𝗶𝗰𝗸𝘀" (math bold letters) -> "Cowlicks"
    if re.search(r"[ÃÂâð][\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013-\u203a\u20ac\u2122]", n):
        for enc in ("cp1252", "latin-1"):   # UTF-8 read as Windows-1252 ("COLOMBIANAðŸ‡¨ðŸ‡´")
            try:
                n = n.encode(enc).decode("utf-8"); break
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    n = re.sub(r"[®™©]", "", EMOJI.sub("", n))
    if re.search(r"[A-Za-z]{3,}", re.sub(CJK, "", n)):
        n = re.sub(r"\s*\([^()]*" + CJK + r"[^()]*\)", "", n)   # "Red Maple MKE (赤いカエデMKE)"
    latin = re.sub(CJK + "+", " ", n)
    if re.search(r"[A-Za-z]{3,}", latin) and re.search(CJK, n):
        n = re.sub(r"\(\s*\)", "", latin)
    m = re.match(r"^(.*?)[,\s]+(?:LLC|Inc)\.?\s*-{1,2}\s*(.+)$", n, flags=re.I)
    if m:
        n = m.group(2) if len(m.group(2).split()) >= 2 and len(m.group(1).split()) <= 2 else m.group(1)
    n = re.sub(r"[,\s]+(?:LLC|L\.L\.C|Inc|Corp)\.?(?=\s|$|,)", "", n, flags=re.I)
    n = re.sub(r"\s*\([^()]*\)\s*$", "", n) if re.sub(r"\s*\([^()]*\)\s*$", "", n).strip() else n   # "(Official Page)", "(Seasonal ...)", "(To-Go)"
    n = re.sub(r",?\s+(?:WI|Wis\.?|Wisconsin)\s*$", "", n)                                                   # "Shady Grove Restaurant, WI"
    parts = re.split(r"\s+[-–]{1,2}\s+|--", n)
    if len(parts) > 1:
        tail = " ".join(parts[1:])
        if TAILWORDS.match(tail.strip()) or re.search(r"\b(?:Best|Award|Magazine|Voted|20\d\d)\b", tail):
            n = parts[0]
    if isinstance(brand, str):
        n = re.sub(r"\s*#\s*\d+\s*$", "", n)
    n = re.sub(r"\s+", " ", n).strip(" -–,") or n
    return nice(n) if n.isupper() and len(n) > 4 else n


o["name_out"] = [tidy(n, b) for n, b in zip(o.name_out, o.brand_n)]
# a chain location labeled with its town or mall ("Portillo's Madison, Wisconsin - West Towne") shows the brand
o.loc[o.brand_n.notna(), "name_out"] = [b if norm_name(n).startswith(norm_name(b)) and len(norm_name(b)) >= 3 else n
                                        for n, b in zip(o.loc[o.brand_n.notna(), "name_out"], o.loc[o.brand_n.notna(), "brand_n"])]
o["spell"] = o.name_out.map(lambda n: re.sub(r"[^a-z0-9]", "", n.lower()))
o["name_out"] = o.groupby("spell").name_out.transform(lambda s: s.mode().iat[0] if len(s) > 1 else s.iat[0])
# names that aren't a business: a street address, "closed"/"retired", a town or "Village of X", a lone generic word, no Latin letters
towns_l = set(o.city.dropna().str.lower())
nm = o.name_out.fillna("")
junk = (nm.str.match(r"(?i)^\d+\s+(?:[NSEW]\.?\s+)?[\w.' ]+?\b(?:St|Street|Ave|Avenue|Dr|Drive|Rd|Road|Blvd|Ln|Lane|Way|Ct|Pl|Hwy|Pkwy|Trl)\b\.?(?:\s*#\s*\w+)?(?:\s*,.*|\s+[A-Z][a-z]+,\s*WI\b.*)?$")
        | nm.str.contains(r"(?i)(?:\bclosed|\bretired)\s*\)?\s*$") | (nm.str.lower().str.strip().isin(towns_l) & o.brand_n.isna())
        | nm.str.match(r"(?i)^(?:village|city|town) of ") | nm.str.strip().str.lower().isin(["kitchen", "bar", "pub", "tavern", "grill", "deli", "pizza", "bakery", "coffee", "diner", "restaurant", "cafe", "café"])
        | ~nm.str.contains(r"[A-Za-z]"))
print("junk names dropped:", int(junk.sum()), nm[junk].head(12).tolist())
o = o[~junk].reset_index(drop=True)
# ---------------------------------------------------------------- not restaurants (hidden unless "include non-restaurants" is on)
# Checked on the cleaned display name, so a street in a store label ("Barriques University Ave") doesn't hide a café.
STORE = re.compile(r"^(?:CASEYS(?: GENERAL STORE)?|KWIK (?:TRIP|STAR)|HOLIDAY STATION\w*|SPEEDWAY|BP|MOBIL|SHELL|CITGO|MARATHON|PDQ|EXXON|CENEX|"
                   r"FLEET FARM|MENARDS|WALMART\b.*|COSTCO\b.*|TARGET|PICK N SAVE|METRO MARKET|FESTIVAL FOODS|WOODMANS|PIGGLY WIGGLY|"
                   r"SENDIKS|ALDI|MEIJER|DASHMART|7 ELEVEN)$|\b(?:SAMS CLUB|HY ?VEE|BIMBO BAKERIES|BAKERIES USA|BAKERY OUTLET|THRIFT STORE|HUNT BROTHERS|"
                   r"HOT STUFF (?:PIZZA|FOODS|KITCHEN)|KRISPY KRUNCHY|CHESTERS (?:FRIED )?CHICKEN|CHAMPS CHICKEN|CITGO|SHELL STATION|GAS STATION|"
                   r"TRAVEL (?:CENTER|PLAZA)|TRUCK STOP|TRUCKSTOP|FARMERS FRIDGE|GRINDS COFFEE POUCHES|MRBEAST|MR BEAST|ITS JUST WINGS|BURGER DEN|"
                   r"BANDA BURRITO|TENDERFIX|PARDON MY CHEESESTEAK|THE MELTDOWN|WOW BAO|GHOST KITCHEN|VIRTUAL KITCHEN|LIQUORS? (?:STORE|MART|DEPOT|OUTLET)|LIQUORS?$|"
                   r"GENTLEM[AE]NS CLUB|SHOWGIRLS|SILK EXOTIC|HEART ?BREAKERS|TRAMPOLINE|INDOOR PLAYGROUND|"
                   r"(?<!MACARONI )CHEESE (?:STORE|MART|SHOP|OUTLET|FACTORY|CASTLE|CHALET|HAUS|COUNTER|CORNER|DEPOT|BARN|COMPANY|CO|CELLARS?)|MARS CHEESE|"
                   r"CHEESE AND SAUSAGE|MEAT MARKET|MEATS$|BUTCHER|SAUSAGE (?:KITCHEN|COMPANY|SHOP)|VENDING|COMMISSARY|FOOD PANTRY|"
                   r"WINE (?:MERCHANTS?|SHOP|STORE|DEPOT|OUTLET)|WINE AND SPIRITS|AND SPIRITS$|JELLY BELLY|LINDT|ROCKY MOUNTAIN CHOCOLATE)\b")
STORE_DOMS = {"caseys.com", "kwiktrip.com", "speedway.com", "huntbrotherspizza.com", "hotstuffpizza.com", "krispykrunchy.com", "champschicken.com",
              "chesters.com", "hy-vee.com", "walmart.com", "samsclub.com", "picknsave.com", "metromarket.net", "festfoods.com", "woodmans-food.com",
              "holidaystationstores.com", "fleetfarm.com", "menards.com", "target.com", "costco.com", "farmersfridge.com", "mrbeastburger.com"}
REALFOOD = re.compile(r"\b(?:SUPPER ?CLUB|RESTAURANT|GRILL|BAR|PUB|TAVERN|PIZZA|CAFE|KITCHEN|STEAK|BISTRO|DINER|BREWING|BREWERY|TAP|SALOON|CUSTARD|"
                      r"TAPROOM|LOUNGE|INN|EATERY|BURGERS?|BBQ|TACOS?|DRIVE IN|DELI|COFFEE|ICE CREAM|CREAMERY|BAKERY|DAIRY|MALT|SODA FOUNTAIN|DONUTS?)\b")
# retail candy, fudge and popcorn shops and shake-and-tea "nutrition" clubs (not the parlors and cafés that also sell candy)
CANDY = re.compile(r"\b(?:CANDY|CANDIES|FUDGE|POPCORN|CONFECTION\w*|CHOCOLATES?|CHOCOLATIER|TRUFFLES?|SWEETS? SHOPPE?|KETTLE CORN|NUTRITION)\b")
CHEESY = re.compile(r"\bCHEESE\b")
CHEESE_OK = re.compile(r"\b(?:MACARONI|GRILLED|CURDS?|STEAK|BURGER)\b")
# a company that runs the kitchen, a stadium or airport, a campus: hidden whatever the name says
HARD = re.compile(r"\b(?:AIRPORT|TERMINAL|CONCOURSE|FISERV FORUM|AMERICAN FAMILY FIELD|CAMP RANDALL|KOHL CENTER|SUMMERFEST|STATE FAIR|FAIRGROUNDS?|"
                  r"LEVY|AVIANDS|SODEXO|ARAMARK|DELAWARE NORTH|CENTERPLATE|COMPASS GROUP|CHARTWELLS|BON APPETIT|HMSHOST|EUREST|GUCKENHEIMER|TAHER|"
                  r"DAVIANS|SSP AMERICA|DELTA SKY CLUB|COMMISSARY|DINING HALL|UNIVERSITY DINING|CORRECTIONAL|PRISON|EXACT SCIENCES|ROCKWELL AUTOMATION|"
                  r"FULL COMPASS|MADISON COLLEGE|CATHOLIC HOME|SENIOR DINING|TRUCK ENTRANCE|CAREERS|BREWERS GUILD|SHELL ROTELLA|MILLER COORS|"
                  r"BOTTLEHOUSE|MILLER COMPRESSING|EPIC WILD WILD WEST|HARLEY DAVIDSON$)\b")
# words that usually mean a venue, unless the place is plainly a bar, café or restaurant or has a real following
SOFT = re.compile(r"\b(?:STADIUM|ARENA|FESTIVAL|CONCESSIONS?|FOOD ?SERVICES?|UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|ELEMENTARY|STUDENT|CAMPUS|"
                  r"HOSPITAL|MEDICAL CENTER|CLINIC|HEALTH CENTER|SENIOR|RETIREMENT|ASSISTED LIVING|NURSING|CARE CENTER|REHAB|CHURCH|PARISH|"
                  r"CONGREGATION|TEMPLE|SYNAGOGUE|MOSQUE|MINISTR(?:Y|IES)|VFW|AMERICAN LEGION|AMVETS|EAGLES CLUB|FRATERNAL ORDER|ELKS LODGE|"
                  r"MOOSE LODGE|KNIGHTS OF COLUMBUS|FALCONS|COUNTRY CLUB|GOLF CLUB|GOLF COURSE|YACHT CLUB|ATHLETIC CLUB|SOCIAL CLUB|TURNERS|"
                  r"SPORTSMEN'?S CLUB|ROD AND GUN|CONSERVATION CLUB|CATERING|CATERERS?|BANQUETS?|BANQUET HALL|EVENT (?:CENTER|VENUE|SPACE)|"
                  r"CONVENTION CENTER|CONFERENCE CENTER|MUSEUM|ZOO|THEATER|THEATRE|CINEMAS?|MARCUS|BOWLING|LANES|CASINO|POTAWATOMI|HO CHUNK|"
                  r"HOTEL|MOTEL|INN AND SUITES|SUITES|MARRIOTT|HILTON|HYATT|SHERATON|WESTIN|HOLIDAY INN|HAMPTON INN|FAIRFIELD INN|RESIDENCE INN|"
                  r"COURTYARD|SPRINGHILL|RADISSON|BEST WESTERN|COMFORT INN|SUPER 8|RED ROOF|DAYS INN|AMERICINN|KALAHARI|GREAT WOLF|WILDERNESS RESORT|"
                  r"CORPORATE|EMPLOYEE|CAFETERIA|MOBILE|FOOD TRUCK|KIOSK|GYM|FITNESS|YMCA|YWCA|BOYS AND GIRLS CLUB|DAYCARE|DAY CARE|CHILD CARE|"
                  r"CHILDCARE|LEARNING CENTER|JAIL|MILITARY|NATIONAL GUARD|BUILDING)\b")
kd = o.name_out.map(norm_name).fillna("")
k_ = o.k.fillna("")
busy = o.reviews.fillna(0) >= 200
gfirst = o.gcats.fillna("").str.split("|").str[0]
plainly_food = kd.str.contains(REALFOOD) | o.cat.isin(["bar", "brewery", "coffee_shop", "cafe"]) \
    | gfirst.str.contains(r"\b(?:Bar|Pub|Restaurant|Cafe|Café|Coffee|Tavern|Grill|Brewery|Diner|Bakery)\b", regex=True)
brand_store = o.brand_n.isin(["Kwik Trip", "Casey's", "7-Eleven", "Hunt Brothers Pizza", "Hot Stuff Pizza", "Krispy Krunchy Chicken", "Chesters Chicken",
                              "Champs Chicken", "Farmer's Fridge", "MrBeast Burger", "It's Just Wings", "Burger Den", "The Meltdown", "Banda Burrito",
                              "Tenderfix", "Pardon My Cheesesteak"])
store = kd.str.contains(STORE) | k_.str.contains(r"\b(?:SHELL STATION|GAS STATION)\b") | brand_store \
    | (o.dom.isin(STORE_DOMS) & ~plainly_food) \
    | (kd.str.contains(CANDY) & ~kd.str.contains(REALFOOD) & ~busy) \
    | (kd.str.contains(CHEESY) & ~kd.str.contains(CHEESE_OK) & ~kd.str.contains(REALFOOD) & ~o.cat.isin(["bar", "brewery"]))
venue = kd.str.contains(HARD) | k_.str.contains(HARD) | o.name.fillna("").str.upper().str.contains(r"\(T-?\d|\bGATE [A-Z]?\d", regex=True) \
    | (kd.str.contains(SOFT) & ~(busy | plainly_food))
LICENSE_ONLY_NONREST = re.compile(r"\b(?:APARTMENTS?|POOLS?|SWIM|AQUATIC|ARCHERY|BOWHUNTERS|SPORTSM[AE]NS?|GUN CLUB|ASSOCIATION|ATTN|C O|EVENTS?|STUDIOS?|"
                                  r"BOATS|SPORTS CENTER|HOSPITALITY GROUP|KNIGHTS|HEALTH|ECONO|CABELAS|CONDOMINIUMS?|HOMEOWNERS|NEIGHBORHOOD|COMMUNITY|"
                                  r"PARKS AND REC|RECREATION|CAMP|BIBLE|FOUNDATION|SOCIETY|COUNCIL|LEAGUE|UNION|INSTITUTE|CENTER$|FARMS?|AMUSEMENT|PREP|"
                                  r"EDUCATIONAL|ENTERTAINMENT|SERVICE AMERICA|PROMEGA|CORPORATION|HOLDINGS|MANAGEMENT|VENTURES|FIELD)\b")
lic_only = o.src.eq("official")
club = kd.str.contains(r"\bCLUB\b") & ~kd.str.contains(r"SUPPER ?CLUB|NIGHT ?CLUB|CLUB 51|CLUB TAVERN")
venue |= lic_only & (kd.str.contains(LICENSE_ONLY_NONREST) | club) & ~busy
VENUE_ADDR = {("201", "46TH"), ("1", "BREWERS"), ("5300", "HOWELL"), ("200", "HARBOR"), ("100", "HARBOR"), ("1111", "VEL R PHILLIPS"),
              ("1440", "MONROE"), ("1919", "ALLIANT ENERGY CENTER"), ("640", "84TH"), ("1265", "LOMBARDI"), ("4000", "INTERNATIONAL"),
              ("917", "MIFFLIN")}
vaddr = pd.Series([bool(street_nums(a) & {n for n, s2 in VENUE_ADDR if s2 == s_}) for a, s_ in
                   zip(o.street, o.street.map(lambda a: street_key(a)[1]))], index=o.index)
# a stadium's year-round restaurant with a real following (1919 Kitchen & Tap at Lambeau) stays; airport and festival stands don't
airport = o.street.fillna("").str.upper().str.contains(r"^(?:5300 S HOWELL|4000 INTERNATIONAL)")
vaddr &= ~((o.reviews.fillna(0) >= 300) & ~airport)
venue |= vaddr
print("stadium / airport / fairground addresses:", int(vaddr.sum()))
o["venue"] = store | venue | o.get("lic_shared", pd.Series(False, index=o.index)).fillna(False).astype(bool)
print("non-restaurants flagged:", int(o.venue.sum()), "| stores:", int(store.sum()), "| venues:", int((venue & ~store).sum()))



# ---------------------------------------------------------------- Wisconsin signals from 2021 reviews: fish fry, cheese curds, custard, supper clubs
sig = pd.read_parquet(f"{WI}/review_signals.parquet").set_index("gmap_id")
for k in ("fishfry", "curds", "custard", "supper", "boil", "oldfash"):
    o["n_" + k] = o.gmap_id.map(sig["n_" + k]).fillna(0).astype(int)
    o["r_" + k] = o.gmap_id.map(sig["r_" + k])
share = lambda k: o["n_" + k] / o.reviews.clip(lower=1)
o["t_supper"] = (o.cuisine == "Supper Club") | ((o.n_supper >= 5) & (share("supper") >= 0.04) & ~o.venue & o.cuisine.isin(
    ["Supper Club", "Steakhouse", "American & Other", "Bar & Pub", "Seafood", "German & European", "Italian"]))
o.loc[o.t_supper & ~o.brand_n.notna(), "cuisine"] = "Supper Club"
o["t_fishfry"] = o.n_fishfry >= 3
o["t_curds"] = o.n_curds >= 3
o["t_custard"] = (o.n_custard >= 3) | (o.cuisine == "Frozen Custard") | o.brand_n.isin(["Culver's", "Kopp's Frozen Custard", "Freddy's"])
o["t_boil"] = o.n_boil >= 2
print("tags: supper clubs", int(o.t_supper.sum()), "| fish fry", int(o.t_fishfry.sum()), "| cheese curds", int(o.t_curds.sum()),
      "| custard", int(o.t_custard.sum()), "| fish boil", int(o.t_boil.sum()))

# ---------------------------------------------------------------- honors (hand-verified, data/curated.json)
cur = CUR
for col in ("jbf", "honors", "icon", "founded", "cur_tags", "cur_price", "rev_reported", "rev_year", "rev_label", "fish", "fry_days", "sides", "rnote", "rsite"):
    o[col] = None
match_curated = curated_matcher(o)
o["hc"] = False   # hand-checked: matched to an open entry in curated.json or data/research/app (each has a 2025-26 source)
matched_cur, unmatched = 0, []
for c in cur:
    if c.get("open") is False:
        continue
    best = match_curated(c)
    if best is None:
        unmatched.append(c["name"] + " (" + (c.get("city") or "") + ")")
        continue
    matched_cur += 1
    i = o.index[best]
    o.at[i, "hc"] = True
    for col, vals in (("jbf", c.get("james_beard")), ("honors", c.get("other_honors")), ("cur_tags", c.get("tags"))):
        if vals:
            have = [x for x in (o.at[i, col] or "").split("; ") if x]
            o.at[i, col] = "; ".join(have + [v for v in dict.fromkeys(vals) if v not in have])
    for col, v in (("icon", c.get("iconic_reason")), ("cur_price", c.get("price_tier")), ("founded", c.get("founded"))):
        if v and not o.at[i, col]:
            o.at[i, col] = v
    for col, v in (("fish", c.get("fish")), ("fry_days", c.get("fry_days")), ("sides", c.get("sides"))):
        if v and not o.at[i, col]:
            o.at[i, col] = ", ".join(v)
    if c.get("note") and not o.at[i, "rnote"]:
        o.at[i, "rnote"] = c["note"]
    if c.get("website") and not o.at[i, "rsite"]:
        o.at[i, "rsite"] = c["website"]
    if c.get("reported_revenue_usd") and not o.at[i, "rev_reported"]:
        o.at[i, "rev_reported"], o.at[i, "rev_year"], o.at[i, "rev_label"] = c["reported_revenue_usd"], c.get("revenue_year"), c.get("revenue_source")
print(f"curated entries matched: {matched_cur}/{len(cur)}; unmatched ({len(unmatched)}): {unmatched}")
# places the research verified as closed (with a source) come off the list, whatever the map listings say
closed_v = json.load(open(f"{DATA}/research/closed.json")) if os.path.exists(f"{DATA}/research/closed.json") else []
gone = [(c["name"], o.name_out.iat[b]) for c in closed_v for b in [match_curated(c)] if b is not None]
drop_closed = {o.index[b] for c in closed_v for b in [match_curated(c)] if b is not None}
o = o.drop(index=list(drop_closed)).reset_index(drop=True)
print("verified closed, removed:", len(drop_closed), gone)
tags_c = o.cur_tags.fillna("").str.lower()
o["t_supper"] |= tags_c.str.contains("supper club")
o.loc[tags_c.str.contains("supper club") & o.brand_n.isna(), "cuisine"] = "Supper Club"
o["t_fishfry"] |= tags_c.str.contains("fish fry")
o["t_curds"] |= tags_c.str.contains("cheese curd")
o["t_custard"] |= tags_c.str.contains("custard")
o["t_boil"] |= tags_c.str.contains("fish boil")
o["honored"] = o.jbf.notna() | o.icon.notna()
shop = o.get("shop", pd.Series(False, index=o.index)).fillna(False).astype(bool)
o.loc[o.honored & ~shop, "venue"] = False
o.loc[shop, "venue"] = True   # a famous cheese store or sausage maker is an icon, but not a restaurant
o["cur_price"] = pd.to_numeric(o.cur_price, errors="coerce")
o.loc[o.price_est.eq(1) & o.cur_price.notna(), "price"] = o.cur_price.round().clip(1, 4)
o["bar"] = o.cat.isin(["bar", "brewery"]) | (o.cuisine == "Bar & Pub")
# places re-filed as supper clubs take the supper clubs' usual price level when Google had none
cp2 = o[o.gprice.notna()].groupby("cuisine").gprice.median()
refile = (o.price_est == 1) & o.brand_n.isna() & o.cur_price.isna() & (o.cuisine == "Supper Club")
o.loc[refile, "price"] = int(round(cp2.get("Supper Club", 2)))

# ---------------------------------------------------------------- Dane County inspections (PHMDC), since Jan 2023
ins = official.phmdc_inspections_all()
v = official.phmdc_violations()
o["lic"] = o.off.map(lambda j: F.lic.iat[int(j)] if j == j else None)
o["lics"] = o.biz.map(lambda b: [x for x in F.lic[F.biz == b] if x.startswith("PHMDC-")] if b == b else [])
insp = official.inspection_record(ins, v)
cols_i = ["n_insp", "n_reinsp", "n_susp", "viol_per", "rf_per", "n_pest", "n_repeat", "last_date", "last_reinsp", "clean"]
# the matched license's own inspections; a sibling license of the same business only when it has the same name
# (a hotel's license is not its bar's: Palette Bar & Grill vs Hotel Indigo at one address)
lic_keys = dict(zip(F.lic, F["keys"]))
recs = []
for lic, ls, k in zip(o.lic, o.lics, o.k):
    cand = [lic] if isinstance(lic, str) and lic in insp.index else []
    if not cand and ls:
        cand = [x for x in ls if x in insp.index and any(name_sim(k or "", kk) >= 85 for kk in lic_keys.get(x, []))]
    if not cand:
        recs.append([np.nan] * len(cols_i)); continue
    r = insp.loc[cand].sort_values("n_insp", ascending=False).iloc[0]
    recs.append([r[c] for c in cols_i])
o[cols_i] = pd.DataFrame(recs, index=o.index, columns=cols_i)
has = o.n_insp.fillna(0) >= 1
mean_clean = o.loc[has, "clean"].mean()
o["clean_adj"] = ((o.n_insp * o.clean + 2 * mean_clean) / (o.n_insp + 2)).round(0)
# graded on a curve: Madison inspectors write up more items per visit than Chicago's, so Chicago's fixed cut points would fail a
# quarter of the county. Instead the county's scores are split in the same shares as Chicago's grades (A 39%, B 35%, C 15%, D 8%, F 3%).
q = o.loc[has, "clean_adj"].quantile([0.03, 0.11, 0.26, 0.61]).tolist()
CUTS = [-1, q[0], q[1], q[2], q[3], 101]
g = pd.cut(o.clean_adj, CUTS, right=False, labels=list("FDCBA")).astype(str)
g = g.where(~((g == "F") & (o.n_reinsp.fillna(0) == 0) & (o.n_pest.fillna(0) == 0) & (o.n_susp.fillna(0) == 0)), "D")
g = g.where(~((g == "A") & (o.n_reinsp.fillna(0) > 0)), "B")
o["grade"] = g.where(has & o.clean_adj.notna(), None).replace("nan", None)
print("Dane County places with inspections since 2023:", int(has.sum()), "| grades:", o.grade.value_counts().to_dict())

# ---------------------------------------------------------------- sales / profit: the Chicago model
auv = {a["brand"]: a for a in json.load(open(f"{DATA}/chain_auv.json")) + json.load(open(f"{DATA}/chain_auv_wi_extra.json")) if a.get("auv_usd")}
auv = {("Chipotle" if b == "Chipotle" else b): a for b, a in auv.items()}
ALIAS = {"Domino's": "Domino's", "Noodles & Company": "Noodles & Company", "Freddy's": "Freddy's Frozen Custard & Steakburgers",
         "A&W": "A&W Restaurants", "Perkins": "Perkins", "Kopp's Frozen Custard": None}
for mine, theirs in ALIAS.items():
    if theirs and theirs in auv and mine not in auv:
        auv[mine] = auv[theirs]
med_rev = o[o.reviews.notna() & (o.chain_n < 5)].groupby("price").reviews.median()
rel = (o.reviews + 10) / (o.price.map(med_rev) + 10)
bump = np.where(o.bar, 1.15, 1.0)
o["rev"] = (o.price.map(BASE) * bump * rel.fillna(0.6) ** B_FIT).clip(100_000, 40_000_000)
o["rev_src"] = np.where(o.reviews.notna(), "model", "model-low")
n_auv = 0
for b, a in auv.items():
    sel = o.brand_n == b
    if not sel.any():
        continue
    n_auv += 1
    med = o.loc[sel, "reviews"].median()
    r_ = (o.loc[sel, "reviews"] / med) ** 0.35 if med == med else pd.Series(np.nan, index=o.index[sel])
    o.loc[sel, "rev"] = a["auv_usd"] * r_.fillna(0.85).clip(0.6, 1.5)
    o.loc[sel, "rev_src"] = "chain"
has_rep = o.rev_reported.notna()
o.loc[has_rep, "rev"] = o.loc[has_rep, "rev_reported"].astype(float)
o.loc[has_rep, "rev_src"] = "reported"
o.loc[o.venue & o.rev_src.isin(["model", "model-low"]), "rev_src"] = "venue"
m_rat = o.rating.mean()
o["bayes"] = (o.reviews * o.rating + 40 * m_rat) / (o.reviews + 40)
margin = o.price.map(MARGIN)
margin = o.cuisine.map(MARGIN_CUISINE).fillna(margin) * (0.8 + 0.4 * pct(o.bayes).fillna(40) / 100)
o["margin"] = margin.round(4)
o["profit"] = o.rev * o.margin
o["food_cost"] = o.cuisine.map(FOOD_COST).fillna(30)
o["value_raw"] = o.bayes - 0.18 * (o.price - 1)
# iconic points: honors + history (verified founding year) + how many people know it
jb = o.jbf.fillna("")
acc = (jb.str.contains("America's Classic") * 35 + jb.str.contains(r"\bwinner\b") * 22
       + (jb.str.contains("finalist") & ~jb.str.contains(r"\bwinner\b")) * 12 + (jb.str.contains("semifinalist") & ~jb.str.contains(r"finalist\b(?<!semifinalist)")) * 5
       + o.icon.notna() * 24 + o.honors.notna() * 6).clip(upper=48)
years = (2026 - pd.to_numeric(o.founded, errors="coerce")).clip(lower=0)
o["s_icon"] = np.where(o.honored, (acc + years.fillna(0).clip(upper=60) / 60 * 32 + pct(np.log1p(o.reviews)).fillna(0) / 100 * 20).clip(upper=100), np.nan)

# ---------------------------------------------------------------- export
def r(x, n=0):
    if x is None or (isinstance(x, float) and x != x):
        return None
    return int(round(float(x))) if n == 0 else round(float(x), n)


o = o[o.lat.notna() | o.official].reset_index(drop=True)
def clean_url(u):
    """Website links without tracking parameters (Reserve with Google tokens, utm_*, click ids)."""
    base, _, q = u.partition("?")
    keep = [kv for kv in q.split("&") if kv and not re.match(r"(rwg_token|utm_[a-z]+|fbclid|gclid|y_source)=", kv)]
    return base + ("?" + "&".join(keep) if keep else "")


if APP:
    # ---- App Store data set: licensed sources only (Overture places, license lists, Dane inspections, our own research)
    TAGS = ["supper", "fishfry", "curds", "custard", "boil"]
    nv = o[~o.venue]
    CITIES = sorted(o.city.dropna().unique().tolist()); CUIS = sorted(o.cuisine.unique().tolist()); BRANDS = sorted(o.brand_n.dropna().unique().tolist())
    ci, cu, br = {c: i for i, c in enumerate(CITIES)}, {c: i for i, c in enumerate(CUIS)}, {c: i for i, c in enumerate(BRANDS)}
    TIER = {"listing": 0, "both": 1, "official": 2}
    JUR = {"mke": 1, "dane": 2}
    SRCS = ["official", "meta", "AllThePlaces", "DAC", "research", "BrightQuery", "Foursquare", "Microsoft"]
    places, seen_ids = [], set()
    for i, x in o.iterrows():
        # a stable id (name + ~100 m cell, or the license number) so saved places survive a data refresh
        idsrc = f"{norm_name(x.name_out)}|{round(float(x.lat), 3)}|{round(float(x.lon), 3)}" if x.lat == x.lat else f"{norm_name(x.name_out)}|{x.get('lic') or x.get('id')}"
        p = {"id": hashlib.md5(idsrc.encode()).hexdigest()[:12], "n": x.name_out, "c": ci.get(x.city) if isinstance(x.city, str) else None,
             "cu": cu[x.cuisine], "t": TIER[x.tier], "s": SRCS.index(x.src) if x.src in SRCS else 1}
        if isinstance(x.street, str): p["a"] = nice(x.street, addr=True)
        if isinstance(x.zip, str) and re.match(r"^5[34]\d{3}", x.zip): p["z"] = x.zip[:5]
        if x.lat == x.lat: p["la"], p["lo"] = round(float(x.lat), 5), round(float(x.lon), 5)
        if isinstance(x.brand_n, str): p["b"] = br[x.brand_n]
        if x.chain_n and int(x.chain_n) > 1: p["ch"] = int(x.chain_n)
        if x.official and isinstance(x.area, str): p["j"] = JUR.get(x.area, 0)
        if x.venue: p["v"] = 1
        if x.bar: p["bar"] = 1
        tags = sum(1 << bi for bi, tg in enumerate(TAGS) if bool(x["t_" + tg]))
        if tags: p["g"] = tags
        if x.hc: p["hc"] = 1
        if x.honored:
            jb = x.jbf or ""
            p["h"] = (1 if "America's Classic" in jb else 0) | (2 if re.search(r"\bwinner\b", jb) else 0) | (4 if re.search(r"(?<!semi)finalist", jb) else 0) \
                | (8 if "semifinalist" in jb else 0) | (16 if isinstance(x.icon, str) else 0)
            p["ip"] = round(float(x.s_icon), 1)
            for k, v in (("icon", x.icon), ("jbf", x.jbf), ("hon", x.honors)):
                if isinstance(v, str): p[k] = v
        if x.founded == x.founded and x.founded is not None: p["f"] = int(float(x.founded))
        for k, col in (("fish", "fish"), ("days", "fry_days"), ("sides", "sides"), ("note", "rnote")):
            if isinstance(x[col], str) and x[col]: p[k] = x[col]
        web = x.rsite if isinstance(x.rsite, str) else (x.web if isinstance(x.get("web"), str) else None)
        if web: p["w"] = clean_url(web)
        if isinstance(x.get("phone"), str) and x.phone: p["ph"] = x.phone
        if x.official:
            lic = x.lic if isinstance(x.lic, str) else (x.id if isinstance(x.id, str) and x.id.startswith(("MKE-", "PHMDC-")) else None)
            if lic: p["lic"] = lic.split("-", 1)[1]
        if isinstance(x.grade, str):
            p["in"] = {"g": x.grade, "sc": r(x.clean_adj), "n": r(x.n_insp), "re": r(x.n_reinsp), "vp": r(x.viol_per, 2), "rf": r(x.rf_per, 2),
                       "pe": r(x.n_pest), "rp": r(x.n_repeat), "su": r(x.n_susp), "ld": x.last_date, "lr": r(x.last_reinsp)}
            p["in"] = {k: v for k, v in p["in"].items() if v is not None}
        while p["id"] in seen_ids:   # two same-name places in one ~100 m cell
            p["id"] = p["id"] + "x"
        seen_ids.add(p["id"])
        places.append(p)
    calib_app = json.load(open(f"{WI}/calibration_app.json")) if os.path.exists(f"{WI}/calibration_app.json") else {}
    out = {"v": 1, "generated": "2026-09-26", "cities": CITIES, "cuisines": CUIS, "brands": BRANDS, "tags": TAGS, "sources": SRCS,
           "count": len(places), "count_restaurants": int(len(nv)), "calibration": calib_app, "places": places}
    os.makedirs(SITE, exist_ok=True)
    json.dump(out, open(f"{SITE}/places.json", "w"), separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)
    json.dump(json.load(open(f"{WI}/wi_shapes.json")), open(f"{SITE}/wi_shapes.json", "w"), separators=(",", ":"))
    print("APP: wrote", len(places), "places (", len(nv), "restaurants ) |", os.path.getsize(f"{SITE}/places.json") // 1024, "KB | tiers:",
          nv.tier.value_counts().to_dict(), "| tags:", {tg: int(nv["t_" + tg].sum()) for tg in TAGS}, "| honored:", int(nv.honored.sum()))
    sys.exit(0)
CITIES = sorted(o.city.dropna().unique().tolist()); CUIS = sorted(o.cuisine.unique().tolist()); BRANDS = sorted(o.brand_n.dropna().unique().tolist())
ci, cu, br = {c: i for i, c in enumerate(CITIES)}, {c: i for i, c in enumerate(CUIS)}, {c: i for i, c in enumerate(BRANDS)}
SRC = {"model": 0, "model-low": 1, "chain": 2, "reported": 3, "venue": 4}
TIER = {"listing": 0, "both": 1, "official": 2}
JUR = {None: 0, "mke": 1, "dane": 2}
TAGS = ["supper", "fishfry", "curds", "custard", "boil"]
# columnar: one array per field; decimals stored as integers (lat 43.0731 -> 430731) and scaled back in the page
SCALE = {"lat": 10000, "lon": 10000, "rating": 10, "margin": 1000, "value_raw": 1000}
SRCS = ["official", "meta", "AllThePlaces", "DAC", "research", "BrightQuery", "Foursquare", "Microsoft"]
C = collections.OrderedDict((c, []) for c in ["name", "addr", "city", "zip", "lat", "lon", "cuisine", "brand", "chain_n", "rating", "reviews", "price",
                                               "price_est", "rev_k", "rev_src", "margin", "value_raw", "tier", "jur", "bar", "venue", "tags", "src"])
# sparse fields: [row, values...] for the few places that have them
SP = {"ff": [], "cc": [], "cs": [], "sc": [], "hon": [], "insp": []}
extra = {}
for i, x in o.iterrows():
    tags = sum(1 << b for b, t in enumerate(TAGS) if bool(x["t_" + t]))
    z = int(x.zip[:5]) if isinstance(x.zip, str) and re.match(r"^5[34]\d{3}", x.zip) else None
    vals = {"name": x.name_out, "addr": nice(x.street, addr=True) if isinstance(x.street, str) else None,
            "city": ci.get(x.city) if isinstance(x.city, str) else None, "zip": z, "lat": x.lat, "lon": x.lon, "cuisine": cu[x.cuisine],
            "brand": br.get(x.brand_n) if isinstance(x.brand_n, str) else None, "chain_n": int(x.chain_n), "rating": x.rating, "reviews": r(x.reviews),
            "price": int(x.price), "price_est": int(x.price_est), "rev_k": int(round(x.rev / 1000)), "rev_src": SRC[x.rev_src], "margin": x.margin,
            "value_raw": x.value_raw, "tier": TIER[x.tier], "jur": JUR.get(x.area if x.official and isinstance(x.area, str) else None, 0), "bar": int(bool(x.bar)),
            "venue": int(bool(x.venue)), "tags": tags, "src": SRCS.index(x.src) if x.src in SRCS else 1}
    for key, n, rr in (("ff", x.n_fishfry, x.r_fishfry), ("cc", x.n_curds, x.r_curds), ("cs", x.n_custard, x.r_custard)):
        if n:
            SP[key].append([i, int(n), int(round(rr * 100)) if rr == rr and rr is not None else None])
    if x.n_supper:
        SP["sc"].append([i, int(x.n_supper)])
    if x.honored:
        jb = x.jbf or ""
        flags = (1 if "America's Classic" in jb else 0) | (2 if re.search(r"\bwinner\b", jb) else 0) | (4 if re.search(r"(?<!semi)finalist", jb) else 0) \
            | (8 if "semifinalist" in jb else 0) | (16 if isinstance(x.icon, str) else 0)
        SP["hon"].append([i, int(round(x.s_icon * 10)), flags])
    if isinstance(x.grade, str):
        SP["insp"].append([i, r(x.clean_adj), x.grade, r(x.n_insp), r(x.n_reinsp)])
    for c, v in vals.items():
        if c in SCALE:
            v = None if v is None or v != v else int(round(float(v) * SCALE[c]))
        elif isinstance(v, float):
            v = None if v != v else v
        C[c].append(v.item() if hasattr(v, "item") else v)
    e = {}
    if x.honored:
        e.update({k: v for k, v in (("jbf", x.jbf), ("honors", x.honors), ("icon", x.icon), ("founded", r(x.founded)),
                                    ("rev_year", r(x.rev_year)), ("rev_label", x.rev_label)) if v is not None and v == v})
    if x.official:
        e["lic"] = x.lic if isinstance(x.lic, str) else (x.id if isinstance(x.id, str) and x.id.startswith(("MKE-", "PHMDC-")) else None)
        e["found"] = "list" if x.src == "official" else "match"
    if isinstance(x.grade, str):
        e.update({"grade": x.grade, "clean": r(x.clean_adj), "n_insp": r(x.n_insp), "n_reinsp": r(x.n_reinsp), "n_susp": r(x.n_susp),
                  "viol_per": r(x.viol_per, 2), "rf_per": r(x.rf_per, 2), "n_pest": r(x.n_pest), "n_repeat": r(x.n_repeat),
                  "last_date": x.last_date, "last_reinsp": r(x.last_reinsp)})
    e = {k: v for k, v in e.items() if v is not None and not (isinstance(v, float) and v != v)}
    if e:
        extra[i] = e
nv = o[~o.venue]
meta = {"generated": "2026-09-25", "cities": CITIES, "cuisines": CUIS, "brands": BRANDS, "src": list(SRC), "tiers": list(TIER), "tags": TAGS,
        "food_cost": {k: v for k, v in FOOD_COST.items()}, "spend": SPEND, "count": len(o), "count_restaurants": int(len(nv)),
        "count_official": int(nv.official.sum()), "count_both": int((nv.tier == "both").sum()), "count_listing": int((nv.tier == "listing").sum()),
        "n_cities": int(nv.city.nunique()), "overture_release": "2026-09-23.0", "rating_mean": round(float(m_rat), 3),
        "model": {"b": B_FIT, "n_chains": n_auv}, "grade_cuts": [round(float(x), 1) for x in CUTS[1:5]], "grade_mean": round(float(mean_clean), 1), "calibration": calib, "n_honored": int(o.honored.sum())}
meta["srcs"] = SRCS
for _k, _v in list(C.items()) + list(SP.items()):
    _bad = [j for j, x in enumerate(_v) if (isinstance(x, float) and x != x) or (isinstance(x, list) and any(isinstance(y, float) and y != y for y in x))]
    if _bad: print("NaN in", _k, len(_bad), _v[_bad[0]])
json.dump({"n": len(o), "scale": SCALE, "cols": C, "sparse": SP, "meta": meta},
          open(f"{SITE}/wisconsin.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
# drawer-only details (honors text, license numbers, inspection breakdown): loaded the first time a drawer opens
json.dump({"n": len(o), "extra": {str(k): v for k, v in extra.items()}}, open(f"{SITE}/wi_detail.json", "w"), separators=(",", ":"), allow_nan=False, default=str)
json.dump(json.load(open(f"{WI}/wi_shapes.json")), open(f"{SITE}/wi_shapes.json", "w"), separators=(",", ":"))
o.to_pickle(f"{WI}/stage2.pkl")
print("wrote", len(o), "places (", int(len(nv)), "restaurants ) in", nv.city.nunique(), "towns;", os.path.getsize(f"{SITE}/wisconsin.json") // 1024,
      "KB | tiers:", nv.tier.value_counts().to_dict(), "| top towns:", nv.city.value_counts().head(8).to_dict())
