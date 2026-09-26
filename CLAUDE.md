# Wisconsin Eats (wi-eats) — notes for Claude Code sessions

Two products share this repo and one data pipeline:
- **The iOS/iPadOS app** "Wisconsin Eats: Restaurants" (SwiftUI, iOS 18+), plus its website in `docs/` (wisconsineats.com).
- **The web leaderboard** (`site/`), published as a private claude.ai Artifact. It uses Google 2021 ratings; the app never does.

Read `README.md` and `playbook/01-strategy.md` first. Never modify anything in `../chi-eats/`.

## Data rules (the app's promise)
- The App Store build ships **no Google-derived data**: no ratings, reviews, price levels, review-text mentions or Google matching.
  `WI_APP=1` switches `pipeline/wisconsin.py` into that mode and writes `data/app/places.json`. Copy it to
  `WisconsinEats/Resources/places.json` after every rebuild. Ratings, hours and photos come live from Apple Maps' own place card.
- The Fish Fry, Supper Clubs and Custard guides list only **hand-checked** places (`hc: 1` in places.json). Each one matches an
  open entry in `data/curated.json` or `data/research/app/*.json` with a 2025–26 source. A listing merely *named* "… Supper Club"
  keeps its tag and stays in the directory, but it is not in a guide. Copy that promises "checked open" must stay true.
- Research records facts only: no review text, no ratings from anyone, and a source URL for every entry. Never bypass bot protection
  (403s, bot checks, logins). DATCP's search site blocks automated access, so don't touch it.
- Places the research finds closed go in `data/research/closed.json` (with a source) or get `"open": false` in `curated.json`.
- Verified addresses Overture can't place: run `pipeline/geocode_research.py` (US Census geocoder), then rebuild.

## Build the app
- The Xcode project is **generated**: `xcodegen generate`. Never commit `WisconsinEats.xcodeproj`.
- Build: `xcodebuild build -project WisconsinEats.xcodeproj -scheme WisconsinEats -destination 'platform=iOS Simulator,name=<an iPhone>' -derivedDataPath ./DerivedData CODE_SIGNING_ALLOWED=NO`
- Tests: same with `test -only-testing:WisconsinEatsTests`. CI (`.github/workflows/build.yml`) runs exactly this on `macos-26`.
- Screens: launch with `-screenshot <home|fishfry|supper|detail|map|inspections|icons|saved|about>`. That fixes the location to downtown
  Milwaukee and seeds saved places (`WisconsinEats/App/ScreenshotMode.swift`). On iPad each shot also selects a place for the detail column.
  `scripts/capture-screenshots.sh "<sim>"` writes `docs/screenshots/<name>.png`; `PREFIX=ipad-` for the iPad set.
  App Store sizes come from the "WI Eats 6.9" (iPhone 17 Pro Max, 1320×2868) and "WI Eats iPad 13" (2064×2752) simulators.
  Use those two for builds and tests too. Other sessions (e.g. the Chicago app) run tests on the shared booted iPhone 17 Pro,
  and two test runs on one simulator stall.
- Brand images: `swift scripts/make-brand.swift` (cheese-wedge icon, `og.png`, favicons). Colors are sRGB brand tokens:
  green #203731, gold #FFB612.
- The Home Screen label is `WI Eats` (`CFBundleDisplayName`); the App Store name is set in App Store Connect, not in the project.

## Website (`docs/`)
- Generated: `.venv/bin/python scripts/make-site.py` writes every page, `sitemap.xml`, `robots.txt`, `site.webmanifest`, `CNAME`,
  and `playbook/site-numbers.json`. **Never hand-edit `docs/*.html`**; change the generator and re-run it.
- It asserts title 50–60 and description 140–160 characters and a single `<h1>`, and fails loudly if a variant doesn't fit.
- Site screenshots in `docs/img/`: 480px copies of `docs/screenshots/{home,fishfry,detail,map,icons}.png`, quantized PNG plus `cwebp -q 84`.
- QA: serve `docs/` locally and check every sitemap page with headless Chrome (Python Playwright, `channel="chrome"`) at 375 and
  1280 px wide, with no horizontal scroll, no console errors, no broken internal links and valid JSON-LD. Don't drive the user's own browser.
- No analytics, no third-party scripts, no `aggregateRating`, no reviews in JSON-LD.

## Public vs private
- `docs/` is the published website; only site files go there. Strategy, listing copy and launch notes live in `playbook/`.
- Commits are local only (no remote, no push):
  `git -c user.name="Nick Soderstrom" -c user.email="nicholas.soderstrom@insidesuccess.com" commit`.
