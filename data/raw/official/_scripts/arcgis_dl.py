"""Polite, paginated ArcGIS FeatureServer/MapServer layer downloader.

Usage:
    python arcgis_dl.py <layer_url> <out_basename> [where]

Writes <out_basename>.geojson (WGS84, outSR=4326), <out_basename>.csv
(attributes + lon/lat for point layers; dates converted to ISO), and
<out_basename>.layer.json (the layer's metadata as served).
"""
import json
import sys
import time

import pandas as pd
import requests

UA = "Mozilla/5.0 (Macintosh) wi-eats-research/0.1 (polite bulk download of public open data)"
S = requests.Session()
S.headers["User-Agent"] = UA


def get(url, params):
    for attempt in range(4):
        try:
            r = S.get(url, params=params, timeout=90)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(d["error"])
            return d
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            print("  retry after error:", e, file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def download(layer_url, out, where="1=1"):
    meta = get(layer_url, {"f": "json"})
    with open(out + ".layer.json", "w") as fh:
        json.dump(meta, fh, indent=1)
    page = min(int(meta.get("maxRecordCount") or 1000), 2000)
    total = get(layer_url + "/query", {"where": where, "returnCountOnly": "true", "f": "json"})["count"]
    oid = meta.get("objectIdField") or next(
        (f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeOID"), None
    )
    date_fields = [f["name"] for f in meta["fields"] if f["type"] == "esriFieldTypeDate"]
    is_table = meta.get("type") == "Table" or not meta.get("geometryType")
    print(f"{meta.get('name')}: {total} rows, page={page}, oid={oid}")
    feats = []
    offset = 0
    while offset < total:
        params = {
            "where": where,
            "outFields": "*",
            "resultOffset": offset,
            "resultRecordCount": page,
            "orderByFields": oid,
            "f": "geojson" if not is_table else "json",
        }
        if not is_table:
            params["outSR"] = 4326
        d = get(layer_url + "/query", params)
        batch = d.get("features", [])
        if not batch:
            break
        feats.extend(batch)
        offset += len(batch)
        print(f"  got {offset}/{total}")
        time.sleep(1.0)
    if is_table:
        rows = [f["attributes"] for f in feats]
        gj = None
    else:
        gj = {"type": "FeatureCollection", "features": feats}
        with open(out + ".geojson", "w") as fh:
            json.dump(gj, fh)
        rows = []
        for f in feats:
            p = dict(f.get("properties") or {})
            g = f.get("geometry")
            if g and g.get("type") == "Point" and len(g.get("coordinates") or []) >= 2:
                p["lon"], p["lat"] = g["coordinates"][0], g["coordinates"][1]
            elif g and g.get("type") in ("Polygon", "MultiPolygon"):
                # approximate centroid = mean of outer-ring vertices (good enough for a building/parcel)
                rings = [g["coordinates"][0]] if g["type"] == "Polygon" else [pp[0] for pp in g["coordinates"]]
                pts = [pt for ring in rings for pt in ring]
                if pts:
                    p["lon_centroid_approx"] = sum(pt[0] for pt in pts) / len(pts)
                    p["lat_centroid_approx"] = sum(pt[1] for pt in pts) / len(pts)
                p["geometry_type"] = g.get("type")
            elif g and g.get("type") != "Point":
                p["geometry_type"] = g.get("type")
            rows.append(p)
    df = pd.DataFrame(rows)
    for c in date_fields:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], unit="ms", errors="coerce")
    df.to_csv(out + ".csv", index=False)
    print(f"wrote {len(df)} rows -> {out}.csv")
    if len(df) != total:
        print(f"WARNING: count mismatch {len(df)} vs {total}", file=sys.stderr)
    return df


if __name__ == "__main__":
    download(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "1=1")
