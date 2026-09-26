"""Wisconsin signals from Google reviews written up to Sep 2021 (UCSD Google Local, review-Wisconsin.json.gz)
-> data/wi/review_signals.parquet

For each Google listing: how many reviews mention a fish fry, cheese curds, frozen custard, a supper club, a fish boil or
a brandy old fashioned, and the average star rating of just those reviews. That's what the fish fry / curds / custard boards rank.
"""
import os, re, gzip, json, time, collections
import pandas as pd
from common import DATA, WI

SIG = {
    "fishfry": re.compile(r"\bfish ?fr(?:y|ies)\b|\bfriday (?:night )?fish\b|\bfish on fridays?\b"),
    "curds": re.compile(r"\bcheese ?curds?\b|\bcurds\b"),
    "custard": re.compile(r"\bcustard\b"),
    "supper": re.compile(r"\bsupper ?clubs?\b"),
    "boil": re.compile(r"\bfish ?boils?\b"),
    "oldfash": re.compile(r"\bold[- ]?fashioneds?\b"),
}
PRE = re.compile(r"fish ?fr|friday|fish on|curd|custard|supper ?club|fish ?boil|old[- ]?fashion", re.I)

t = time.time()
cnt = collections.defaultdict(lambda: collections.Counter())
n = hit = 0
with gzip.open(os.path.join(DATA, "review-Wisconsin.json.gz"), "rt") as f:
    for line in f:
        n += 1
        if not PRE.search(line):
            continue
        d = json.loads(line)
        txt = (d.get("text") or "").lower()
        if not txt:
            continue
        g, rt = d.get("gmap_id"), d.get("rating")
        for k, rx in SIG.items():
            if rx.search(txt):
                c = cnt[g]; c[k] += 1
                if rt:
                    c[k + "_sum"] += rt
                hit += 1
        if n % 2_000_000 == 0:
            print(n, "reviews", round(time.time() - t), "s")
rows = []
for g, c in cnt.items():
    row = {"gmap_id": g}
    for k in SIG:
        row["n_" + k] = c[k]
        row["r_" + k] = round(c[k + "_sum"] / c[k], 3) if c[k] else None
    rows.append(row)
pd.DataFrame(rows).to_parquet(os.path.join(WI, "review_signals.parquet"))
print("reviews read:", n, "| mentions:", hit, "| listings with a mention:", len(rows), "|", round(time.time() - t), "s")
