# Naming

**App Store name:** `Wisconsin Eats: Restaurants` (27 of 30)
**Subtitle:** `Fish Fry & Supper Club Guide` (28 of 30)
**Home Screen name** (`CFBundleDisplayName`): `WI Eats`
**Website:** https://nickstrom5.github.io/wisconsin-eats/ for now; later a state subdomain of a hub domain (see below) · **Bundle ID:** `com.wisconsineats.ios` · **Repo folder:** `wi-eats/`

## Why this name
- Nick's call (2026-09-26): the name has to cover every restaurant, not just fish fries and supper clubs;
  "fish fry & supper clubs" is the tagline. The first working name, "Fish Fry & Supper Clubs WI", became
  the subtitle.
- "Wisconsin" is the word people type. It sits in the name, the field App Store search weights most.
  "Restaurants" is the second most-typed word for this intent. With the subtitle, the indexed words are
  wisconsin, eats, restaurants, fish, fry, supper, club and guide. None of them should go in the keyword field.
- "Eats" reads as a local food guide, not a directory or a delivery app.
- The Home Screen name is short because iOS cuts labels at about 12 characters ("Wisconsin E…").

## Checks run on 2026-09-26
- **App Store** (iTunes Search API, US store):
  - No app is named "Wisconsin Eats".
  - Nearest names: Isthmus Eats and Miltown Eats, both from Isthmus Eats LLC, for Madison and Milwaukee (10 and 6 ratings).
  - Different words, but the same "<place> Eats" pattern. If Apple or that developer objects, fall back to "Wisconsin Eats Guide".
  - Fish fry guides exist for other cities: Cincinnati Fish Fry and Cleveland Fish Fry Guide, both from Patchboard, LLC. That shows demand. There is no Wisconsin one.
- **Domain (not bought, Nick's call 2026-09-28):** Verisign's RDAP answered 404 for wisconsineats.com, meaning unregistered (the control, wieats.com, answered 200). Nick is buying a hub domain instead; see the domain plan below.
- **Trademark:** not checked. Search USPTO (tmsearch.uspto.gov) for "Wisconsin Eats" in class 9 and class 43 before submitting.

## Domain plan (Nick, 2026-09-28)
One hub domain for all the state food apps: a landing page that links to every state, with a subdomain per state
(`wisconsin.<hub>`, `illinois.<hub>` …). Each state's site stays its own GitHub Pages repo, and the subdomain is a CNAME
record to `nickstrom5.github.io`. Until the hub domain is bought, the Wisconsin site is at the github.io project address.
The app and App Store Connect point there, and GitHub forwards those links once the subdomain is set.
If the state apps become a series, pick one naming pattern before the next one ships ("Illinois Eats"; the Chicago app is "Chi Ranked").

## Rejected
| Name | Why not |
|---|---|
| Fish Fry & Supper Clubs WI | Too narrow for an app that lists every restaurant; now the subtitle |
| WI Eats | Search for "wi" returns WIC, WhatsApp and Wawa; fine as the Home Screen label only |
| Eat Wisconsin | Reads like a state promotion campaign |
| Badger Eats | Sounds like a University of Wisconsin dining app |
| Dairyland Eats | Search results are all Dairy Queen |
| Supper Club Finder | Leaves out fish fries and every other restaurant |
