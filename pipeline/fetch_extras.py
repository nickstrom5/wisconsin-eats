"""Two small Overture extracts -> data/wi

- calib_areas.json         Milwaukee city limits, Madison city limits and Dane County (unsimplified), for calibrate.py and wisconsin.py
- addresses_dane.parquet   Overture address points in Dane County's box, to place license records that have no coordinates
"""
import os, json
import duckdb
from shapely import wkb
from shapely.geometry import mapping

RELEASE = "2026-09-23.0"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "wi")
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
areas = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=divisions/type=division_area/*.parquet"
rows = con.execute(f"""SELECT class, names.primary, ST_AsWKB(geometry) FROM read_parquet('{areas}', hive_partitioning=1)
  WHERE country = 'US' AND region = 'US-WI' AND ((subtype = 'locality' AND names.primary IN ('Milwaukee', 'Madison'))
        OR (subtype = 'county' AND names.primary = 'Dane County'))""").fetchall()
json.dump({name: mapping(wkb.loads(bytes(g))) for cls, name, g in rows if cls == "land"}, open(f"{OUT}/calib_areas.json", "w"))
addr = f"s3://overturemaps-us-west-2/release/{RELEASE}/theme=addresses/type=address/*.parquet"
con.execute(f"""COPY (SELECT number, street, unit, postcode, postal_city, address_levels, ST_Y(geometry) lat, ST_X(geometry) lon
  FROM read_parquet('{addr}', hive_partitioning=1)
  WHERE country = 'US' AND bbox.xmin BETWEEN -89.85 AND -89.0 AND bbox.ymin BETWEEN 42.84 AND 43.30)
  TO '{OUT}/addresses_dane.parquet' (FORMAT PARQUET)""")
print("wrote calib_areas.json and addresses_dane.parquet")
