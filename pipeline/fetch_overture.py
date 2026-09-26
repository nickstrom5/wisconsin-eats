"""Download the Overture Maps extracts that wisconsin.py reads -> data/wi/

- overture_wi_bbox.parquet     every place in Wisconsin's bounding box (name, category, address, point)
- overture_wi_sources.parquet  which datasets each Wisconsin eating/drinking listing came from (Meta, Foursquare, ...)
- wi_shapes.json               simplified state and county outlines for the map

Reads the public Overture bucket over S3 with DuckDB (no account needed). Takes several minutes.
"""
import os, json, time
import duckdb

RELEASE = "2026-09-23.0"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "wi")
# Wisconsin, including the Apostle Islands and Washington Island, plus a margin for border towns
BBOX = "bbox.xmin BETWEEN -92.95 AND -86.2 AND bbox.ymin BETWEEN 42.45 AND 47.35"
EAT = "('restaurant','casual_eatery','bar','fast_food_restaurant','coffee_shop','cafe','smoothie_juice_bar','brewery','food_court')"
os.makedirs(OUT, exist_ok=True)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
places = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=places/type=place/*.parquet"

t = time.time()
if not os.path.exists(f"{OUT}/overture_wi_sources.parquet"):
  con.execute(f"""
COPY (
  SELECT id, names.primary AS name, basic_category AS cat, taxonomy.primary AS tax, taxonomy.hierarchy AS hier, confidence,
         operating_status AS status, brand.names.primary AS brand, addresses[1].freeform AS street, addresses[1].locality AS city,
         addresses[1].postcode AS zip, addresses[1].region AS region, ST_Y(geometry) AS lat, ST_X(geometry) AS lon, websites[1] AS web,
         phones[1] AS phone
  FROM read_parquet('{places}', hive_partitioning=1) WHERE {BBOX}
) TO '{OUT}/overture_wi_bbox.parquet' (FORMAT PARQUET)""")
  print("places in bbox", round(time.time() - t), "s")
  con.execute(f"""
COPY (
  SELECT id, list_transform(sources, x -> x.dataset) AS ds, list_transform(sources, x -> x.update_time) AS ut,
         len(socials) AS n_soc, len(websites) AS n_web, len(phones) AS n_ph
  FROM read_parquet('{places}', hive_partitioning=1)
  WHERE {BBOX} AND addresses[1].region = 'WI' AND basic_category IN {EAT}
) TO '{OUT}/overture_wi_sources.parquet' (FORMAT PARQUET)""")
  print("sources", round(time.time() - t), "s")

areas = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=divisions/type=division_area/*.parquet"
water = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=base/type=water/*.parquet"
from shapely import wkb
from shapely.geometry import mapping
from shapely.ops import unary_union
from shapely.geometry import Polygon
rows = con.execute(f"""
  SELECT subtype, names.primary AS name, ST_AsWKB(geometry) AS g
  FROM read_parquet('{areas}', hive_partitioning=1)
  WHERE country = 'US' AND region = 'US-WI' AND subtype IN ('region', 'county') AND class = 'land'
    AND bbox.xmin > -93.5 AND bbox.xmax < -86 AND bbox.ymin > 42 AND bbox.ymax < 47.5""").fetchall()
# Overture's state and county areas run out into Lakes Michigan and Superior: cut the lakes out (their islands come back as land)
lakes = con.execute(f"""
  SELECT ST_AsWKB(geometry) FROM read_parquet('{water}', hive_partitioning=1)
  WHERE subtype = 'lake' AND names.primary IN ('Lake Michigan', 'Lake Superior')
    AND bbox.xmin < -84 AND bbox.xmax > -93 AND bbox.ymin < 47.5 AND bbox.ymax > 41.5""").fetchall()
lake = unary_union([wkb.loads(bytes(g[0])) for g in lakes]).buffer(0)
print("lakes:", len(lakes), round(time.time() - t), "s")
# big inland lakes (Winnebago, Mendota, Petenwell, Geneva...) are cut from the map outline too, but not from the state test
inland = con.execute(f"""
  SELECT ST_AsWKB(geometry) FROM read_parquet('{water}', hive_partitioning=1)
  WHERE subtype IN ('lake', 'reservoir') AND bbox.xmin > -93.0 AND bbox.xmax < -86.8 AND bbox.ymin > 42.45 AND bbox.ymax < 47.1
    AND (bbox.xmax - bbox.xmin) * (bbox.ymax - bbox.ymin) > 0.004 AND ST_Area(geometry) > 0.003""").fetchall()
inland = unary_union([wkb.loads(bytes(g[0])).buffer(0) for g in inland]).buffer(0)
print("inland lakes cut from the map:", len(getattr(inland, "geoms", [inland])), round(time.time() - t), "s")

def rings(geom, tol, min_area, holes=False):
    """Outer rings, or with holes=True one list per polygon: [outer, hole, hole...] (the page fills even-odd, so lakes stay water)."""
    geom = geom.simplify(tol, preserve_topology=True)
    polys = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "Polygon" and p.area >= min_area]
    r = lambda ring: [[round(x, 3), round(y, 3)] for x, y in ring.coords]
    if holes:
        return [[r(p.exterior)] + [r(h) for h in p.interiors if abs(Polygon(h).area) >= min_area] for p in polys]
    return [r(p.exterior) for p in polys]

out = {"state": None, "counties": []}
for sub, name, g in rows:
    geom = wkb.loads(bytes(g)).buffer(0).difference(lake)
    if sub == "region":
        json.dump(mapping(geom.simplify(0.0005, preserve_topology=True)), open(f"{OUT}/wi_state_detail.geojson", "w"))
        # the drawn shoreline: fine enough that lakefront places sit on land when the map zooms to a town
        # slivers where the state line and the lake shore disagree (a few meters wide) are dropped from the drawing
        out["state"] = rings(geom.difference(inland).buffer(-0.0007).buffer(0.0007), 0.0012, 0.00015, holes=True)
    else:
        out["counties"].append({"name": name, "c": rings(geom.difference(inland).buffer(-0.0007).buffer(0.0007), 0.005, 0.0008)})
json.dump(out, open(f"{OUT}/wi_shapes.json", "w"), separators=(",", ":"))
print("outlines: state", len(out["state"]), "rings +", len(out["counties"]), "counties;", round(time.time() - t), "s total")
