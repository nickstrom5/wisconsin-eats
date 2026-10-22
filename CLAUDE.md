# Wisconsin Eats (wi-eats) — notes for Claude Code sessions

Two products share this repo and one data pipeline:
- **The iOS/iPadOS app** "Wisconsin Eats: Restaurants" (SwiftUI, iOS 18+), plus its website in `docs/` (https://wisconsin.eatsranked.com/, GitHub Pages from `main` /docs; the old https://nickstrom5.github.io/wisconsin-eats/ links forward there).
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
- Tracking tags: the app export strips `ref=google`, `referrer=google_food_ordering`, `cn_channel`, `utm_*`, `fbclid`, Yext `cid=RF:YXT…`
  and similar from every outbound link (`pipeline/tracking_params.py`, the same in every state; store ids and locations stay). The site
  reads the app export, and a unit test fails if a tracked link is bundled (QA 2026-10-19, P1 #13).
- `check_websites.py --retry-transient` re-fetches 429s and connection errors after a busy run, and `CHECK_WORKERS=4` slows a run;
  `--recheck-ok` skips pages re-checked in the last 2 days, so a stopped run resumes (2026-10-21). `injection.py` is the master copy
  for every state's checker: change it here, then copy it (and `test_injection.py`) to the others.
- Website links: `pipeline/check_websites.py` fetches every link politely and the export drops any that isn't plainly the place's own
  live page (spam, parked, directory, moved, dead or blocked). It reads `data/wi/website_candidates.json`, which the export writes, so
  the order is: rebuild, check, rebuild. Blocked hosts match by domain, never as substrings ("restaurant.com" once dropped 171 real
  sites). Without `website_check.json` the export ships no links (fail closed). Only http/https links ship.
  Hacked sites hide casino links off-screen for search engines (Club Oasis, Sparta, 2026-10-12): the checker also fails pages that
  link out to gambling hosts, put casino words in links to other sites, use casino words in another language, or hide links to other
  sites off-screen (`injected()`). Manual verdicts with evidence go in `data/wi/website_overrides.json`, which no re-run undoes.
  `--recheck-ok` fetches every passing page again; run it after a new rule and before each submission. Saves are atomic.
- Corrections to map listings go in `data/research/app_fixes.json` (name, street, city, zip or drop, matched by name + town, each
  with a source). Place ids come from the name *before* fixes, so a corrected name keeps people's saved places.
- The export merges duplicates (same name and address; same name within 400 m, 150 m for a name-"chain" of 2; same phone and
  street number) and the kept row inherits the dropped one's hand check and facts. Phones ship as +1 and ten digits or not at all.
- The research matcher's statewide name fallback must stay within 30 km of the researched town (Chetek's Caddy Shack once landed
  on Hayward's Caddyshak).
- Places the research finds closed go in `data/research/closed.json` (with a source) or get `"open": false` in `curated.json`.
- Verified addresses Overture can't place: run `pipeline/geocode_research.py` (US Census geocoder), then rebuild.

## Build the app
- The Xcode project is **generated**: `xcodegen generate`. Never commit `WisconsinEats.xcodeproj`.
- Build: `xcodebuild build -project WisconsinEats.xcodeproj -scheme WisconsinEats -destination 'platform=iOS Simulator,name=<an iPhone>' -derivedDataPath ./DerivedData CODE_SIGNING_ALLOWED=NO`
- Tests: same with `test -only-testing:WisconsinEatsTests`. CI (`.github/workflows/build.yml`) runs exactly this on `macos-26`.
- UI smoke test (`WisconsinEatsUITests`, taps through every screen on iPhone and iPad): `-only-testing:WisconsinEatsUITests`,
  **without** `CODE_SIGNING_ALLOWED=NO`, because the UI-test runner must be signed to launch, even on a simulator. Run it on both dedicated
  simulators before every submission. It needs network access for Apple Maps place cards.
- Light mode only: `UIUserInterfaceStyle: Light` in `project.yml`. The palette has no dark variants, and dark mode made lists unreadable.
- `WisconsinEats/Resources/PrivacyInfo.xcprivacy` declares UserDefaults (CA92.1), no tracking and no collected data. Update it
  if you add any required-reason API or SDK.
- Screens: launch with `-screenshot <home|fishfry|supper|detail|map|inspections|icons|saved|about>`. That fixes the location to downtown
  Milwaukee and seeds saved places (`WisconsinEats/App/ScreenshotMode.swift`). On iPad each shot also selects a place for the detail column.
  `scripts/capture-screenshots.sh "<sim>"` writes `docs/screenshots/<name>.png`; `PREFIX=ipad-` for the iPad set.
  App Store sizes come from the "WI Eats 6.9" (iPhone 17 Pro Max, 1320×2868) and "WI Eats iPad 13" (2064×2752) simulators.
  Use those two for builds and tests too. Other sessions (e.g. the Chicago app) run tests on the shared booted iPhone 17 Pro,
  and two test runs on one simulator stall.
- **App Store builds must come from the public (non-beta) Xcode.** App Review refused build 1 because /Applications/Xcode.app is 27.1
  beta (27A9269). Archive and upload with `DEVELOPER_DIR="/Applications/Xcode 1.app/Contents/Developer"` (Xcode 27.0, 27A266a), or
  whatever Xcode is current and public when you read this; check `DTXcodeBuild` in the archived app's Info.plist. Bump
  `CURRENT_PROJECT_VERSION` for every upload.
- Brand images: `swift scripts/make-brand.swift` (cheese-wedge icon, `og.png`, favicons). Colors are sRGB brand tokens:
  green #203731, gold #FFB612.
- The Home Screen label is `WI Eats` (`CFBundleDisplayName`); the App Store name is set in App Store Connect, not in the project.

## Website (`docs/`)
- Lives at https://wisconsin.eatsranked.com/ (the hub is eatsranked.com; Cloudflare DNS `wisconsin` CNAME → nickstrom5.github.io, DNS only), set by
  `CUSTOM_DOMAIN` in `scripts/make-site.py`, which also writes `docs/CNAME`. The app's links (`WisconsinEats/App/Links.swift`) use it
  from build 3; builds 1–2 said github.io, which GitHub forwards.
- Generated: `.venv/bin/python scripts/make-site.py` writes every page, `sitemap.xml`, `robots.txt`, `site.webmanifest`, `CNAME`,
  and `playbook/site-numbers.json`. **Never hand-edit `docs/*.html`**; change the generator and re-run it.
- It asserts title 50–60 and description 140–160 characters and a single `<h1>`, and fails loudly if a variant doesn't fit.
- Pages: home, the three guides (with Q&A blocks), a Lent fish fry page, 13 city pages (each place on its nearest city only) and a
  `/cities/` hub, 4 region pages (county lists stated on each page), `/about.html` (methodology, sources, licenses in `/licenses/`),
  privacy, terms, `/explore/`, and one page per hand-checked or honored place at `/places/<slug>.html` (about 600). Facts only, from
  `data/app/places.json`; no ratings anywhere.
- Every page carries a strict Content-Security-Policy `<meta>` built from sha256 hashes of its own inline `<script>`/`<style>`. The build
  fails on any inline `style=` attribute or `on…=` handler, so add styles to the stylesheet blocks. JSON-LD escapes `<`, `>` and `&`.
- `APP_STORE_URL` (None until the app is live) switches every page to Apple's official badge, the Smart App Banner meta and
  installUrl/sameAs. It needs Apple's unmodified badge saved at `docs/img/app-store-badge.svg` first. Never put the Apple logo in our
  own buttons.
- The web app is `docs/explore/` (source `scripts/explore.js`, inlined by the generator). It has the app's guides, search (a port of
  `Search.swift`), filters, a canvas map of county outlines and a place panel. It reads `docs/data/core.json` (list, search and map
  columns) and lazily `docs/data/detail.json` (phones, sites, notes, inspections), both split from `data/app/places.json` by the
  generator. Keep its guide rules in step with `Guide.swift` (hand-checked only for fish fry, supper clubs and custard). Saved places and
  the last guide live in localStorage. Preview: the `wi-eats-site` launch config serves `build/serve/wisconsin-eats` → `docs/`.
- Site screenshots in `docs/img/`: 480px copies of `docs/screenshots/{home,fishfry,detail,map,icons}.png`, quantized PNG plus `cwebp -q 84`.
- QA: `.venv/bin/python scripts/qa-site.py` serves `docs/` locally and checks every page statically, then in headless Chrome
  (Python Playwright, `channel="chrome"`): 375 and 1280 px, no horizontal scroll, no console errors or CSP violations, no broken
  links, valid JSON-LD, 44 px tap targets, light and dark contrast, CLS, sitemap ↔ files, overclaims, and the web app's flows.
  Each check was mutation-tested. Don't drive the user's own browser.
- No analytics, no third-party scripts, no `aggregateRating`, no reviews in JSON-LD.

## Public vs private
- `docs/` is the published website; only site files go there. Strategy, listing copy and launch notes live in `playbook/`, which is
  public too: no personal emails, phone numbers or anything private in it (`playbook/14-security-cleanup.md` uses placeholders).
- Remote: github.com/nickstrom5/wisconsin-eats (public). Pushing `main` publishes the website through GitHub Pages, so push only with
  Nick's OK. Commit with
  `git -c user.name="Nick Soderstrom" -c user.email="329204362+nickstrom5@users.noreply.github.com" commit` (also set as this repo's
  `git config user.email`). The repo is public: never a personal or work email. History was rewritten to the no-reply address on
  2026-09-28, and the pre-rewrite history is kept locally only, in the branch `backup-before-email-rewrite`.
