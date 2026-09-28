# Launch checklist

In order. Items marked **Nick** need your accounts; everything else is in the repo already.

## This week
- [x] Website on GitHub Pages at https://wisconsin.eatsranked.com/ (repo nickstrom5/wisconsin-eats; hub eatsranked.com). See `05-naming.md`.
- [ ] **Nick:** Search USPTO for "Wisconsin Eats" (classes 9 and 43).
- [ ] **Nick:** Create a GitHub repo, push, and turn on Pages from `/docs` (runbook sections 3–4). Pages needs a public repo
      on the free plan, and everything outside `docs/` is then public too. That's fine: the playbook has no secrets.
- [ ] **Nick:** Set up Cloudflare DNS (runbook section 4). Support email is work-with-nick@gmail.com, so email routing (sections 5–6) is optional.
- [ ] Check https://wisconsin.eatsranked.com/privacy.html loads over HTTPS (GitHub builds a minute or two after each push).

## Build
- [ ] **Nick:** Set `DEVELOPMENT_TEAM: 4C8TU6U7MQ` in `project.yml`, run `xcodegen generate`, and archive (see `09-app-store-connect.md`).
- [ ] On a real iPhone through TestFlight:
  - Open a place and tap **Ratings, hours & photos**. Apple's card should open.
  - Allow location. Near Me should sort by distance.
  - Search Spotlight for "Del-Bar". It should find the place.
  - Check that Call, Website and Directions all open.
- [ ] Look at the iPad layout in landscape and portrait.

## Store
- [x] Submitted for review 2026-09-28: 1.0.0 (2), automatic release. Next: watch for Apple's email; after approval, see "After approval" below.
- [ ] **Nick:** Create the App Store Connect record. Fill it in from `06-app-store-listing.md` and `09-app-store-connect.md`.
- [ ] Upload the screenshots from `docs/screenshots/`: iPhone `home, fishfry, detail, map, supper, icons, inspections, saved`, and the `ipad-` set.
- [ ] Set the privacy label to "Data Not Collected". Answer the age questions honestly: alcohol references are infrequent.
- [ ] Submit, with a manual release.

## After approval
- [ ] Put the Apple ID into the site: the meta tag and `APP_STORE_URL` in `scripts/make-site.py`. Re-run the script and commit.
- [ ] Set up Search Console and Bing, submit the sitemap and request indexing (runbook section 9).
- [ ] Release the app.

## Before Lent 2027 (Ash Wednesday is Feb 10, 2027)
- [ ] By mid-January, refresh the data:
  - Re-check every fish fry and supper club for closures. Search budget was the limit last time, so start early.
  - Rebuild with `WI_APP=1`, copy places.json, re-run `make-site.py`, and ship an update.
- [ ] Promotional text (editable without review): switch to the Lent line in `06-app-store-listing.md`.
- [ ] Add the leads the research couldn't verify (Facebook-only places) if they post current menus.
