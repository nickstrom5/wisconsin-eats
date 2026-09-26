"""Overture address points for all of Wisconsin -> data/wi/addresses_wi.parquet (places researched addresses the map listings lack)."""
import os, time
import duckdb
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "wi")
t = time.time()
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
a = "s3://overturemaps-us-west-2/release/2026-09-23.0/theme=addresses/type=address/*.parquet"
con.execute(f"""COPY (SELECT number, street, postcode, postal_city, address_levels[1].value AS state, address_levels[-1].value AS muni,
  ST_Y(geometry) lat, ST_X(geometry) lon FROM read_parquet('{a}', hive_partitioning=1)
  WHERE country = 'US' AND bbox.xmin BETWEEN -92.95 AND -86.7 AND bbox.ymin BETWEEN 42.45 AND 47.35)
  TO '{OUT}/addresses_wi.parquet' (FORMAT PARQUET)""")
print(con.execute(f"select count(*), count(*) filter (where state='WI') from '{OUT}/addresses_wi.parquet'").fetchall(), round(time.time() - t), "s")
