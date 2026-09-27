"""Geocodes the verified street addresses the app build couldn't place from Overture (data/research/geocode_todo.json)
with the US Census Bureau's public geocoder, and caches the answers in data/research/geocode_census.json.
Only exact Wisconsin matches are kept. Usage: python geocode_research.py   (then rebuild with WI_APP=1)"""
import json, os, time, urllib.parse, urllib.request

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "research")
todo = json.load(open(f"{DATA}/geocode_todo.json"))
cache_path = f"{DATA}/geocode_census.json"
cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
misses = cache.pop("_misses", [])
for q in todo:
    if q in cache or q in misses:
        continue
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urllib.parse.urlencode(
        {"address": q, "benchmark": "Public_AR_Current", "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": "wisconsin-eats-pipeline (https://wisconsineats.com)"})
    try:
        res = json.load(urllib.request.urlopen(req, timeout=30))["result"]["addressMatches"]
    except Exception as e:
        print("error", q, e); time.sleep(2); continue
    wi = [m for m in res if m["addressComponents"].get("state") == "WI"]
    if len(wi) == 1 or (wi and len({(round(m["coordinates"]["y"], 3), round(m["coordinates"]["x"], 3)) for m in wi}) == 1):
        m = wi[0]
        cache[q] = {"lat": round(m["coordinates"]["y"], 6), "lon": round(m["coordinates"]["x"], 6),
                    "zip": m["addressComponents"].get("zip"), "matched": m["matchedAddress"]}
        print("ok  ", q, "->", m["matchedAddress"])
    else:
        misses.append(q)
        print("miss", q, f"({len(wi)} WI matches)")
    time.sleep(0.5)
cache["_misses"] = sorted(set(misses))
json.dump(cache, open(cache_path, "w"), indent=1, sort_keys=True)
print(len(cache) - 1, "cached,", len(misses), "unmatched")
