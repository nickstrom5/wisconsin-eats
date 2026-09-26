# Strategy

## The bet
A free Wisconsin restaurant app wins on the searches general apps answer badly:
- "fish fry near me" on a Friday,
- "supper clubs near [town]",
- "frozen custard [town]".

Everyone in the state knows those words, and nobody keeps a trustworthy statewide list. Yelp and Google rank by stars and can't
say who serves perch on Friday. Travel Wisconsin has listings but no fish, days or distance sort. Local apps are city-only:
Isthmus Eats covers Madison and Miltown Eats covers Milwaukee.

**Positioning:** "Every Wisconsin restaurant, and the fish fries worth the drive." The name covers every restaurant; the subtitle
and the first three guides carry the Wisconsin-only hook (Nick's call, 2026-09-26: the name implies all restaurants, and
"fish fry & supper clubs" is the tagline).

## Why free
- No paywall means no reason to hold back the web guides. The website doubles as the SEO engine and the App Store listing's
  proof, and every city page links to the app.
- The data is open-licensed, and Apple supplies ratings, hours and photos through MapKit, so there are no running costs:
  no backend, no API keys, nothing to bill.
- Later options, none of them needed to launch:
  - A tip jar.
  - A paid "Supper Club Passport" (visited check-ins and a share card).
  - Sponsored "featured fish fry" slots, clearly labelled and never mixed into the checked lists.

## What makes it trustworthy (and keeps it through App Review)
- **No Google data in the app.** The web leaderboard uses the UCSD Google Local 2021 snapshot, which carries no license. That's fine
  for a private page, but an App Store risk (guideline 5.2.2, third-party content). The app uses only:
  - Overture Maps (CDLA Permissive 2.0 / ODbL),
  - the Milwaukee and Dane County public license and inspection records,
  - our own research,
  - Apple's own place card, opened with MapKit.
- **Every guide entry has a source.** Fish fries, supper clubs and custard stands are hand-checked against a 2025–26 source.
  A map listing merely named "Supper Club" stays in the directory but not in a guide.
- **Listings are calibrated, not assumed.** Each map listing's reliability is measured against two real license lists and
  printed on the place ("listings like this matched a licensed business 75–79% of the time").
- **Nothing ranks by ratings.** Order comes from distance, verified founding year, James Beard honors and the Dane County inspection curve.

## Growth loops
1. **Web → App Store.** Three statewide guides and 13 city pages target "[city] fish fry" and "supper clubs near [city]".
   Each page lists real, checked places and has an early-access or App Store button. Lent is the annual spike.
2. **App Store search.** The name carries "Wisconsin" and "Restaurants"; the subtitle carries fish fry, supper club and guide;
   the keywords carry city names, custard, perch, walleye, Lent and the Dells (`06-app-store-listing.md`).
3. **Corrections loop.** "Report a missing or closed place" goes to hello@. Owners asking to be listed bring new verified entries,
   each needing a source.
4. **Local press.** A statewide fish fry count broken down by fish (cod, perch, walleye, haddock, bluegill) is a natural
   Lent-season story for Milwaukee, Madison and Green Bay outlets. The numbers are in `site-numbers.json`.

## Risks
| Risk | What we do |
|---|---|
| Closures make a checked list stale | Re-check before every Lent. The About screen and site say "checked Sep 2026, check before you go". Corrections email |
| App Review 4.2 (minimum functionality: "just a list") | Native map with clustering, distance sort, Spotlight, iPad split view, Apple Maps place cards, saved places. Not a web wrapper |
| App Review 5.2.2 (third-party content) | Licensed data only; attribution in About and on the terms page; review notes explain it (`09-app-store-connect.md`) |
| Name collision with "Isthmus Eats" / "Miltown Eats" | Different words; fallback name "Wisconsin Eats Guide" |
| Inspection grades read as official | Labelled everywhere as our curve, not the health department's; worst-first sorting only in the app, never on the web |
| Research search budget | Leads the research couldn't verify are kept in `data/research/app/LEADS.md` for the next pass |

## What the next version could add, and what it moves
- **Fish fry "open now" on Fridays:** time filters from Apple's hours. More Friday sessions.
- **Widgets:** "nearest fish fry" on the Home Screen on Fridays. Retention.
- **More counties' inspections,** if any publish bulk data. Differentiation.

## First 30 days
1. Domain, Pages, email, TestFlight (`04-launch-checklist.md`).
2. Submit. While in review: Search Console, sitemap, request indexing on the guides and city pages.
3. After launch, send the fish fry numbers and the city pages to three local food writers.
4. Start the Lent refresh by mid-January 2027 (Ash Wednesday is Feb 10, 2027).
