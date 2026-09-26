# App Store listing (ASO)

Numbers here must match `site-numbers.json`, which `scripts/make-site.py` rewrites from the data on every run. Current:
395 fish fries, 209 supper clubs, 28 custard stands, 16,379 restaurants in 828 towns. Update this file after a data refresh.

## Name (30 max)
`Wisconsin Eats: Restaurants` (27)

## Subtitle (30 max)
`Fish Fry & Supper Club Guide` (28)

Together, the name and subtitle index: wisconsin, eats, restaurants, fish, fry, supper, club, guide. Apple also combines them with
the keyword field, so "milwaukee" plus "restaurants" matches "milwaukee restaurants".

## Keywords (100 max, commas, no spaces, no words already in the name or subtitle)
`milwaukee,madison,green bay,custard,friday,lent,dinner,tavern,perch,walleye,door county,dells,bar` (97)

- City names are the biggest win. Appleton, Oshkosh and La Crosse didn't fit; rotate them in after a month of Search Console
  and App Store Connect search-term data.
- "lent" catches the February–April spike.
- Plurals are unnecessary; Apple matches singular and plural.

## Promotional text (170 max, editable any time without review)
Launch:
`395 Friday fish fries, 209 supper clubs and 28 custard stands, each checked open by hand. Plus every restaurant in Wisconsin, sorted by how close it is to you.` (159)

Lent (switch on Ash Wednesday, Feb 10, 2027):
`Lent is here. Find a Friday fish fry near you: 395 checked across Wisconsin, with the fish they serve (cod, perch, walleye, bluegill) and the nights they fry.` (158)

## Description
The first three lines show before "more", so they carry the pitch.

```
Every Wisconsin restaurant, and the fish fries worth the drive.

Wisconsin Eats is a free guide to eating in Wisconsin: 395 Friday fish fries, 209 supper clubs and 28 frozen custard stands we checked by hand, plus 16,379 restaurants, cafés, taverns and bakeries in 828 towns. No account, no ads.

WISCONSIN GUIDES
• Friday Fish Fry: which fish each place serves (cod, perch, walleye, haddock, bluegill), the nights it fries and the sides.
• Supper Clubs: relish trays, old fashioneds and prime rib, with founding years.
• Frozen Custard: local stands, not the big chains.
• Wisconsin Icons: James Beard Award winners, finalists and semifinalists, and long-running institutions.
• Oldest Places: verified founding years, oldest first.
• Inspections: Dane County health inspection results, graded on a curve (our summary, not official grades).

FIND IT FAST
• Sort by distance, or browse the map by fish fry, supper club or custard.
• Search by name, town, street or dish: "perch green bay", "supper club dells".
• Filter by town or cuisine, hide chains.
• Save places for Friday.
• Find fish fries, supper clubs and icons from iPhone search (Spotlight).

LIVE DETAILS FROM APPLE MAPS
Tap "Ratings, hours & photos" on any place to open Apple Maps' own place card, with current hours, photos, ratings and directions.

HOW THE LISTS ARE BUILT
Every fish fry, supper club and custard stand was confirmed open in September 2026 on its own website or menu, in local news, or on its Travel Wisconsin listing. The rest of the restaurants come from Overture Maps open data and the City of Milwaukee and Public Health Madison & Dane County license lists, checked for reliability against those official lists. Nothing is ranked by star ratings.

PRIVATE BY DESIGN
No account, no tracking, no ads. Your location, if you share it, only sorts lists on your device. Saved places stay on your device.

Places open and close, so check before you go. Spot a mistake? Email hello@wisconsineats.com.

Not affiliated with any restaurant, team, chain or government agency. Map data © OpenStreetMap contributors, Overture Maps Foundation.
```

## What's New (1.0)
`First release. Friday fish fries, supper clubs, custard stands and every restaurant in Wisconsin.`

## Screenshots
Upload in this order; the first three show in search results.

| # | File (iPhone 6.9" / iPad 13") | Caption to overlay (optional) |
|---|---|---|
| 1 | `home.png` / `ipad-home.png` | Every Wisconsin restaurant |
| 2 | `fishfry.png` / `ipad-fishfry.png` | Friday fish fry, nearest first |
| 3 | `detail.png` / `ipad-detail.png` | Live hours & photos from Apple Maps |
| 4 | `map.png` / `ipad-map.png` | The map, by fish fry or supper club |
| 5 | `supper.png` / `ipad-supper.png` | 209 supper clubs, checked by hand |
| 6 | `icons.png` / `ipad-icons.png` | James Beard honorees & institutions |
| 7 | `inspections.png` / `ipad-inspections.png` | Dane County inspections |
| 8 | `saved.png` / `ipad-saved.png` | Save it for Friday |

The raw simulator captures are App Store–legal as they are. Captions are optional; if you add them, keep them in the green/gold brand
and repeat no claim the app can't back.

## Category
Primary Food & Drink, secondary Travel.

## Review notes
See `09-app-store-connect.md` §8.
