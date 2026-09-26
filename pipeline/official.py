"""Official records: City of Milwaukee licenses and Public Health Madison & Dane County (PHMDC) establishments + inspections.

load() returns one table of official food/alcohol licensees with a normalized name key, street number and street key,
coordinates where the source has them, the jurisdiction and the license kind. The Wisconsin-wide state (DATCP) list has
no public bulk download, so outside these two areas there are no official records to use.
"""
import os, re
import numpy as np, pandas as pd
from common import norm_name, RAW

OFF = os.path.join(RAW, "official")
DIRS = {"N": "N", "S": "S", "E": "E", "W": "W", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
TYPES = set("ST STREET AVE AV AVENUE BLVD RD ROAD DR DRIVE LN LANE CT PL PKWY TER TRL TRAIL WAY HWY CIR PLZ SQ MALL BND PASS XING RUN ROW WALK RDG".split())


def road(a):
    """One spelling for numbered roads: 'US HIGHWAY 51' = 'US-51' = 'Hwy 51'; 'STATE HIGHWAY 113' = 'WI-113'; 'COUNTY RD M' = 'CTH M'."""
    a = re.sub(r"(\d)\s*&\s*(\d)", r"\1-\2", a.upper())
    a = re.sub(r"\b(US|WI|STH|CTH|CR|I)-(\w)", r"\1 \2", a)
    a = re.sub(r"\b(?:US|U S)\s+(?:HIGHWAY|HWY)\b", "US", a)
    a = re.sub(r"\b(?:STATE (?:HIGHWAY|HWY|ROAD|RD)|STH|WIS|WI HIGHWAY|WI HWY|WISCONSIN HIGHWAY)\b", "WI", a)
    a = re.sub(r"\b(?:COUNTY (?:HIGHWAY|HWY|ROAD|RD|TRUNK HIGHWAY|TRUNK HWY|TRUNK)|CO (?:HIGHWAY|HWY|RD|ROAD)|CTY (?:HWY|RD)|CTH|CR)\b", "CO", a)
    a = re.sub(r"\bHIGHWAY\b", "HWY", a)
    return re.sub(r"\b(US|WI|CO|HWY) (\w+)\s*-\s*\w+", r"\1 \2", a)   # "US 51 & 138": the first route


def street_key(a):
    """'2505 Monroe St' -> ('2505', 'MONROE'); '733 N MILWAUKEE ST K117' -> ('733', 'MILWAUKEE'); 'W 1st Ave' keeps '1ST'."""
    if not isinstance(a, str):
        return None, None
    a = re.sub(r"[.,#]", " ", road(a))
    m = re.match(r"^\s*((?:[NSEW]\d+)?[NSEW]?\d+)[A-Z]?(?:\s*-\s*\d+[A-Z]?)?\s+(.*)$", a)   # also Wisconsin grid numbers: W3176, N44W33013
    if not m:
        return None, None
    words = [w for w in m.group(2).split() if w]
    while words and words[0] in DIRS:
        words = words[1:]
    core = []
    for w in words:
        if w in TYPES and core:
            break
        core.append(w)
    core = [{"FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD", "FOURTH": "4TH", "FIFTH": "5TH", "SIXTH": "6TH"}.get(w, w) for w in core]
    return m.group(1), " ".join(core[:3]) or None


def street_nums(a):
    """'157-159 W Main St' -> {'157', '159'}; '2505 Monroe St' -> {'2505'}."""
    if not isinstance(a, str):
        return set()
    a = road(a)
    g = re.match(r"^\s*((?:[NSEW]\d+)?[NSEW]\d+)\s", a.upper() + " ")   # Wisconsin grid address: "W3176 Springfield Dr", "N44W33013 ..."
    if g:
        return {g.group(1)}
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*(\d+)[A-Z]?)?\s", a.upper() + " ")
    if not m:
        return set()
    lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:   # "1500-02"
        hi = int(str(lo)[: len(str(lo)) - len(m.group(2))] + m.group(2)) if m.group(2) else lo
    return {str(x) for x in range(lo, hi + 1, 2 if (hi - lo) % 2 == 0 else 1)} if 0 <= hi - lo <= 12 else {str(lo)}


def _names(*vals):
    out = []
    for v in vals:
        if not isinstance(v, str):
            continue
        for part in re.split(r"\s*/\s*|\s+\bdba\b\s+|\s+&\s+(?=[A-Z][a-z])", v, flags=re.I):
            k = norm_name(re.sub(r"\b(?:LLC|INC|CORP|CORPORATION|LTD|CO)\b\.?", "", part, flags=re.I))
            if k and k not in out:
                out.append(k)
    return out


def load():
    rows = []
    # City of Milwaukee: active licenses (restaurant, retail food, taverns), with coordinates
    f = pd.read_csv(f"{OFF}/milwaukee/mke_food_licenses_active.csv", dtype=str)
    a = pd.read_csv(f"{OFF}/milwaukee/mke_alcohol_licenses_active.csv", dtype=str)
    for df, kind_of in ((f, {"FREST": "restaurant", "FOOD": "retail"}), (a, {"BTAVN": "tavern", "BBEER": "tavern", "CWINE": "tavern"})):
        for _, r in df.iterrows():
            kind = kind_of.get(r.LIC_TYPE_ABBR)
            if not kind:
                continue
            num, st = street_key(r.ENTITY_ADDRESS)
            rows.append({"jur": "mke", "lic": "MKE-" + str(r.LICENSE_ID), "name": r.TRADE_NAME if isinstance(r.TRADE_NAME, str) else r.CORP_NAME,
                         "keys": _names(r.TRADE_NAME, r.CORP_NAME), "addr": r.ENTITY_ADDRESS, "city": "Milwaukee", "num": num, "street": st,
                         "lat": float(r.lat) if isinstance(r.lat, str) else np.nan, "lon": float(r.lon) if isinstance(r.lon, str) else np.nan,
                         "kind": kind, "active": True, "cap": r.TOT_CAP, "since": r.GRANTED_DATE})
    # Public Health Madison & Dane County: every licensed establishment (active and recently expired), no coordinates
    e = pd.read_csv(f"{OFF}/madison_dane/phmdc_establishments.csv", dtype=str)
    kinds = {"Primarily Restaurant": "restaurant", "Retail Food Establishment": "retail"}
    for _, r in e.iterrows():
        kind = kinds.get(r.EstablishmentType)
        if not kind:
            continue
        addr = " ".join(x for x in [r.AddrStreetNo, r.AddrStreetDir, r.AddrStreetName, r.AddrStreetType] if isinstance(x, str))
        num, st = street_key(addr)
        rows.append({"jur": "dane", "lic": "PHMDC-" + r.LicenseNbr, "name": r.DoingBusinessAsName, "keys": _names(r.DoingBusinessAsName),
                     "addr": addr, "city": r.AddrCity.title() if isinstance(r.AddrCity, str) else None, "num": num, "street": st,
                     "lat": np.nan, "lon": np.nan, "kind": kind,
                     "active": r.LicenseAppStatus in ("Active", "About to Expire", "Health Inspection Complete") or r.LicExpirationStatus == "Active",
                     "cap": None, "since": None})
    df = pd.DataFrame(rows)
    # one business can hold several licenses (a restaurant license and a tavern license): same address and a name in common
    from common import name_sim, _stems, GENERIC
    df["biz"] = np.arange(len(df))
    for (jur, num, st), g in df[df.num.notna() & df.street.notna()].groupby(["jur", "num", "street"]):
        idx = list(g.index)
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                ka, kb = df.at[idx[a], "keys"], df.at[idx[b], "keys"]
                same = any(name_sim(x, y) >= 85 or ((_stems(x) - GENERIC) & (_stems(y) - GENERIC)) for x in ka for y in kb)
                if same:
                    old, new = df.at[idx[b], "biz"], df.at[idx[a], "biz"]
                    df.loc[df.biz == old, "biz"] = new
    return df


def phmdc_inspections():
    """Per license: routine inspections, re-inspections required ("DENIED" = the visit found violations needing a re-check), since 2023."""
    i = pd.read_csv(f"{OFF}/madison_dane/phmdc_inspections.csv", dtype=str)
    i = i[i.InspecDispositionStatus == "Insp Completed"].copy() if "Insp Completed" in set(i.InspecDispositionStatus) else i
    i["d"] = pd.to_datetime(i.InspectionDate, errors="coerce")
    return i


def phmdc_inspections_all():
    i = pd.read_csv(f"{OFF}/madison_dane/phmdc_inspections.csv", dtype=str)
    i["d"] = pd.to_datetime(i.InspectionDate, errors="coerce")
    i["lic"] = "PHMDC-" + i.LicenseNbr
    return i


def phmdc_violations():
    v = pd.read_csv(f"{OFF}/madison_dane/phmdc_violations_guidesheet_2023plus.csv", dtype=str)
    return v[v.GUIDE_TYPE.fillna("").str.contains(r"IONN 2017|GRP 2017")].copy()


def inspection_record(ins, v, since="2023-01-01"):
    """Per PHMDC license, routine food inspections since Jan 2023:
    - a routine visit that ends "Reinspection Required" found violations serious enough to need a return visit (our "failed" visit);
    - violations per visit from the inspection guide sheets; risk-factor items (IONN: the foodborne-illness interventions) count
      separately, like Chicago's items 1-29; pest items; repeat violations; immediate suspensions.
    The score mirrors Chicago's: 100 minus penalties, shrunk toward the county mean for places with few visits (done by the caller)."""
    rec = ins[(ins.d >= since) & (ins.InspectionType == "Routine Inspection") & (ins.InspecResultStatus != "Cancelled")].copy()
    vv = v.groupby("InspectionNbr").agg(n_viol=("GUIDE_TYPE", "size"),
                                        n_rf=("GUIDE_TYPE", lambda s: s.str.contains("IONN").sum()),
                                        pest=("GUIDE_ITEM_TEXT", lambda s: int((s.fillna("").str.contains("PEST") & ~s.fillna("").str.contains("PESTICIDE")).any())),
                                        rep=("RepeatViolation", lambda s: s.fillna("").str.upper().isin(["CHECKED", "Y", "YES", "TRUE", "1"]).sum()))
    rec = rec.join(vv, on="InspectionNbr")
    for c in ("n_viol", "n_rf", "pest", "rep"):
        rec[c] = rec[c].fillna(0)
    rec["reinsp"] = (rec.InspecResultType == "DENIED").astype(int)
    susp = ins[(ins.d >= since) & (ins.InspecResultStatus == "Immediate Suspension")].groupby("lic").size()
    g = rec.groupby("lic")
    r = pd.DataFrame({"n_insp": g.size(), "n_reinsp": g.reinsp.sum(), "viol_per": g.n_viol.mean(), "rf_per": g.n_rf.mean(),
                      "n_pest": g.pest.sum(), "n_repeat": g.rep.sum()})
    last = rec.sort_values("d").groupby("lic").tail(1).set_index("lic")
    r["last_date"] = last.d.dt.strftime("%Y-%m-%d").reindex(r.index)
    r["last_reinsp"] = last.reinsp.reindex(r.index)
    r["n_susp"] = susp.reindex(r.index).fillna(0).astype(int)
    rate = r.n_reinsp / r.n_insp
    penalty = (40 * rate + 3 * r.viol_per.clip(upper=10) + 8 * r.rf_per.clip(upper=3) + 25 * r.n_pest / r.n_insp
               + 8 * r.last_reinsp + 15 * (r.n_susp > 0))
    r["clean"] = (100 - penalty).clip(0, 100).round(1)
    return r
