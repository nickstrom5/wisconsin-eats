"""How often is a map listing a real, licensed restaurant? Measured where official lists exist -> data/wi/calibration.json

Inside Milwaukee's city limits (City of Milwaukee active restaurant + tavern licenses) and Dane County (PHMDC licensed
restaurants), every Overture eating/drinking listing is checked against the official list: same business name nearby,
or the same street address with a distinctive name word in common. Match rates are reported by where the listing came
from and whether Google had it open in 2021, the same breakdown that was measured on Chicago.
"""
import json, math
import numpy as np, pandas as pd
from shapely.geometry import shape, Point
from shapely.prepared import prep
from common import name_sim, _stems, GENERIC, WI
import official
from listings_util import official_match

o = pd.read_pickle(f"{WI}/stage1.pkl")
F = official.load()
areas = json.load(open(f"{WI}/calib_areas.json"))
mke, dane = prep(shape(areas["Milwaukee"]).buffer(0.0003)), prep(shape(areas["Dane County"]).buffer(0.0003))
o["area"] = [("mke" if mke.contains(Point(x, y)) else "dane" if dane.contains(Point(x, y)) else None) for x, y in zip(o.lon, o.lat)]
o = o[o.area.notna() & ~o.j_junk & ~o.j_outside].reset_index(drop=True)
print("listings inside Milwaukee:", int((o.area == "mke").sum()), "| inside Dane County:", int((o.area == "dane").sum()))

res = {}
for jur in ("mke", "dane"):
    L = o[o.area == jur].reset_index(drop=True)
    R = F[(F.jur == jur) & F.active].reset_index(drop=True)
    m = official_match(L, R)          # listing index -> official index
    L["off_any"] = L.index.map(lambda i: i in m)
    L["off_rest"] = L.index.map(lambda i: i in m and R.kind.iat[m[i]] in ("restaurant", "tavern"))
    s = L.src.fillna("none")
    grp = np.select([L.closed21, L.ov_closed, (s == "meta") & L.in21, s == "meta", s.isin(["AllThePlaces", "DAC"]) & L.in21,
                     s.isin(["AllThePlaces", "DAC"]), L.in21, s == "Foursquare", s == "BrightQuery", s == "Microsoft"],
                    ["Google 2021 says closed", "Overture says closed", "Meta + open in Google 2021", "Meta only",
                     "brand feed + Google 2021", "brand feed only", "Foursquare/BrightQuery/Microsoft + Google 2021",
                     "Foursquare only", "BrightQuery only", "Microsoft only"], "other")
    L["grp"] = grp
    t = L.groupby("grp").agg(n=("id", "size"), official=("off_any", "mean"), restaurant_or_tavern=("off_rest", "mean")).sort_values("n", ascending=False)
    print(f"\n== {jur}: {len(L)} listings, {len(R)} active official records ({int(R.kind.isin(['restaurant','tavern']).sum())} restaurants/taverns)")
    print((t.assign(official=(t.official * 100).round(1), restaurant_or_tavern=(t.restaurant_or_tavern * 100).round(1))).to_string())
    # the other direction: how much of the official list do the map listings cover?
    got = set(R.biz.iloc[list(m.values())])
    Rr = R[R.kind.isin(["restaurant", "tavern"])].drop_duplicates("biz")
    cover = np.mean([b in got for b in Rr.biz])
    print(f"official restaurants/taverns (one per business) found among map listings: {cover*100:.1f}% of {len(Rr)}")
    res[jur] = {"listings": int(len(L)), "official_active": int(len(R)), "official_rest": int(len(Rr)), "coverage": round(float(cover), 3),
                "groups": {g: {"n": int(r.n), "official": round(float(r.official), 3), "rest": round(float(r.restaurant_or_tavern), 3)} for g, r in t.iterrows()}}
json.dump(res, open(f"{WI}/calibration.json", "w"), indent=1)

# ---- the App Store build uses no Google data, so it keeps listings on Overture's own confidence: measure that grouping too
o2 = pd.read_pickle(f"{WI}/stage1.pkl")
o2["area"] = [("mke" if mke.contains(Point(x, y)) else "dane" if dane.contains(Point(x, y)) else None) for x, y in zip(o2.lon, o2.lat)]
o2 = o2[o2.area.notna() & ~o2.j_junk & ~o2.j_outside & ~o2.j_closedname & ~o2.ov_closed & ~o2.nowhere].reset_index(drop=True)
conf, s2 = o2.confidence.fillna(0), o2.src.fillna("none")
o2["grp"] = np.select([(s2 == "meta") & (conf >= 0.95), (s2 == "meta") & (conf >= 0.9), s2.isin(["AllThePlaces", "DAC"]), (s2 == "BrightQuery") & (conf >= 0.95),
                       s2 == "meta"],
                      ["meta_high", "meta_mid", "brand_feed", "bq_high", "meta_low"], "other_sources")
app = {}
for jur in ("mke", "dane"):
    L = o2[o2.area == jur].reset_index(drop=True)
    R = F[(F.jur == jur) & F.active].reset_index(drop=True)
    m = official_match(L, R)
    L["hit"] = L.index.map(lambda i: i in m)
    t = L.groupby("grp").hit.agg(["size", "mean"])
    app[jur] = {g: {"n": int(r["size"]), "official": round(float(r["mean"]), 3)} for g, r in t.iterrows()}
    print(f"\n== app grouping, {jur}\n" + t.assign(mean=(t["mean"] * 100).round(1)).to_string())
json.dump(app, open(f"{WI}/calibration_app.json", "w"), indent=1)
