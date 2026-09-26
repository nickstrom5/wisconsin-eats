# Sources: every number and where it comes from

Checked 2026-09-26. Site numbers are written to `playbook/site-numbers.json` by `scripts/make-site.py`; the listing
(`06-app-store-listing.md`) must match them.

## Counts (app and site)
| Number | Where it appears | How it's computed |
|---|---|---|
| 16,379 restaurants | Home header, site hero, App Store description | Places in `data/app/places.json` that aren't flagged non-restaurants (`v`) |
| 828 towns | Same | Distinct towns among those restaurants |
| 395 Friday fish fries | Home card, fish fry guide, site, listing | Hand-checked (`hc`) places tagged fish fry |
| 209 supper clubs | Same | Hand-checked places tagged supper club. Another 64 listings merely *named* "Supper Club" aren't counted |
| 28 custard stands | Same | Hand-checked places tagged custard, not chains with 5+ Wisconsin locations |
| Fish counts (cod 213, perch 146, walleye 121, haddock 78, bluegill 49) | Fish fry guide | Among the 309 fish fries that list their fish; each fish counted once per place |
| 37 serve fish fry on other days too | Fish fry guide | `days` is not just Friday |
| 144 of 209 supper clubs also fry fish; 94 have a verified founding year; 44 opened before 1950 | Supper club guide | Same data |
| 75–79% | About screen, place notes | Share of Meta listings with confidence ≥ 0.95 that matched an active license: Dane 75%, Milwaukee 79% (`data/wi/calibration_app.json`, n = 1,119 and 1,126) |
| 1,013 inspected places, A–F grades | Inspections guide | Dane County places with at least 2 routine inspections since Jan 2023, graded on a curve (`pipeline/wisconsin.py`) |

## Data sources and licenses
| Source | Used for | License / terms | URL |
|---|---|---|---|
| Overture Maps Foundation, release 2026-09-23.0 | Places statewide; state and county outlines; water | Places: CDLA Permissive 2.0 (Meta, Microsoft, AllThePlaces CC0, Foursquare Apache 2.0). Divisions and base: ODbL. Attribution: "© OpenStreetMap contributors, Overture Maps Foundation" | https://overturemaps.org |
| City of Milwaukee Open Data | Active food dealer and tavern licenses, with coordinates | Public records, open data | https://data.milwaukee.gov |
| Public Health Madison & Dane County | Licensed establishments, inspections, violations | Public records (city of Madison open data tables) | https://www.publichealthmdc.com |
| James Beard Foundation | Award, finalist and semifinalist history | Facts from the foundation's award search | https://www.jamesbeard.org/awards/search-past-awards |
| US Census Bureau geocoder | Placing 8 hand-checked places Overture didn't have | Public domain API | https://geocoding.geo.census.gov |
| Our research (`data/curated.json`, `data/research/app/*.json`) | Fish fries, supper clubs, custard, fish boils, icons, founding years | Our own facts. Each entry records the URLs it came from: the place's own site or menu, dated news, or Travel Wisconsin | — |
| Apple Maps (MapKit) | Ratings, hours, photos and directions in the place card, shown live | Apple's terms; nothing stored | — |

**Not used in the app or its website:** UCSD Google Local 2021 (ratings, reviews, price, review text), Yelp, Tripadvisor,
or any review site. The web leaderboard artifact does use Google Local 2021, labelled as such, and that stays private.

## Research coverage (September 2026)
| File | Places | Evidence from 2026 | Evidence from 2025 |
|---|---|---|---|
| `data/research/app/southwest_central.json` | 189 | 151 | 38 |
| `data/research/app/southeast.json` | 146 | 135 | 11 |
| `data/research/app/northeast_north.json` | 157 | 139 | 18 |

Plus the 203 icons in `data/curated.json`. Leads the research couldn't verify are in `data/research/app/LEADS.md`.
The research used facts only: no review text and no ratings, and blocked sites were never bypassed.

## Dates
- Ash Wednesday 2027: February 10, 2027 (Easter is March 28, 2027).
- Domain check: Verisign RDAP returned 404 for wisconsineats.com on 2026-09-26.
