# App Store Connect

The app is free, has no in-app purchases, no account, no backend and no restricted entitlements.
There is nothing to wait on from Apple except review.

## 1. Identifiers (developer.apple.com → Certificates, IDs & Profiles)
- App ID: `com.wisconsineats.ios`, explicit. **Registered 2026-09-28** by an App Store export with `-allowProvisioningUpdates`: it has a cloud-managed Apple Distribution certificate and the profile "iOS Team Store Provisioning Profile: com.wisconsineats.ios". No capabilities to tick.
- Team: Nick's team, `4C8TU6U7MQ` (same as Cartworth). Set `DEVELOPMENT_TEAM` in `project.yml`, then run `xcodegen generate`.

## 2. New app (appstoreconnect.apple.com → Apps → +)
- Platform: iOS. Name: `Wisconsin Eats: Restaurants`. Primary language: English (U.S.).
- Bundle ID: `com.wisconsineats.ios`. SKU: `wisconsineats-ios-1`.
- User access: full.

## 3. App information
- Subtitle: `Fish Fry & Supper Club Guide`
- Category: primary **Food & Drink**, secondary **Travel**.
- Content rights: "Does your app contain, show, or access third-party content?" **Yes.** The app shows open data (Overture Maps under CDLA Permissive 2.0 and ODbL, and City of Milwaukee and Dane County public records) and Apple Maps content through MapKit. Licenses and attribution are on the About screen and in `docs/terms.html`. No Google, Yelp or review-site data is included.
- Age rating questionnaire:
  - Answer "Infrequent/Mild" to *Alcohol, Tobacco, or Drug Use or References*: taverns, bars, supper clubs and brandy old fashioneds are named.
  - Answer "None" to everything else.
  - No user-generated content, no web browsing, no messaging, no gambling.
  - Expect 13+. Don't under-declare; references to alcohol count.
- Privacy policy URL: `https://wisconsin.eatsranked.com/privacy.html` (the github.io address entered first forwards here; update the field anyway)
- Support URL: `https://wisconsin.eatsranked.com/`. Marketing URL: `https://wisconsin.eatsranked.com/`. No new build needed to change these.

## 4. Pricing and availability
- Price: **Free**. Availability: United States only at launch (every listing is in Wisconsin). Add Canada later if people ask.
- iPad: supported (`TARGETED_DEVICE_FAMILY` 1,2). Apple silicon Macs: leave "Make available on Mac" **off** until checked on a Mac.

## 5. App Privacy
- Data collection: **"No, we do not collect data from this app."** The label reads **Data Not Collected**.
- Why that's true:
  - There's no analytics, crash-reporting or ad SDK.
  - Location is used on the device only.
  - Saved places live in UserDefaults on the device.
  - MapKit lookups go to Apple under Apple's own policy. Apple doesn't count them as collection by the developer.

## 6. Export compliance
- `ITSAppUsesNonExemptEncryption = NO` is already in Info.plist (only Apple's HTTPS via MapKit). No questions at upload.

## 7. Build and upload
Already done on 2026-09-28: the signed archive "WisconsinEats 1.0.0 (1)" is in Xcode's Organizer, and it exports cleanly for the App Store.
Once the App Store Connect record exists, upload either from Organizer (Distribute App → App Store Connect) or with:
`xcodebuild -exportArchive -archivePath "<archive>" -exportPath build/export -exportOptionsPlist scripts/ExportOptions-AppStore.plist -allowProvisioningUpdates`
after changing `destination` in that plist from `export` to `upload`. For each later build, bump `CURRENT_PROJECT_VERSION`.

1. `xcodegen generate`, open `WisconsinEats.xcodeproj`, then set the team if it isn't set.
2. Set the version to 1.0 and the build to 1 (`MARKETING_VERSION` / `CURRENT_PROJECT_VERSION` in `project.yml`).
3. Product → Archive → Distribute App → App Store Connect → Upload.
4. TestFlight: add yourself as an internal tester. On a real iPhone:
   - Open a place and tap **Ratings, hours & photos**. Apple's card must open.
   - Allow location and check that Near Me sorts by distance.
   - Search for a place in Spotlight after the first launch.

## 8. Version page
- Screenshots:
  - iPhone 6.9-inch (1320 × 2868) and iPad 13-inch (2064 × 2752), from `scripts/capture-screenshots.sh` on the "WI Eats 6.9" and "WI Eats iPad 13" simulators.
  - Upload order: home, fishfry, detail, map, supper, icons, inspections, saved.
- Promotional text, description, keywords and What's New: `06-app-store-listing.md`.
- Review notes (paste):

```
Wisconsin Eats is a free guide to Wisconsin restaurants. No login, no account, no purchases.

• Lists: Friday fish fries, supper clubs and frozen custard stands were checked by hand
  (each has a 2025–2026 source on file). All other restaurants come from Overture Maps open
  data (CDLA Permissive 2.0) and City of Milwaukee / Public Health Madison & Dane County
  public license records. Attribution is on the About tab.
• Ratings, hours and photos are Apple's: tap "Ratings, hours & photos" on any place to open
  the MapKit place card (MKMapItemDetail). The app does not store or rank by ratings.
• Location is optional and only sorts lists by distance on the device.
• Inspection grades (Dane County only) are labelled in the app as our own summary of public
  inspection records, not official grades.

To try it: Guides → Friday Fish Fry → any place → "Ratings, hours & photos".
```

- Contact: Nick Soderstrom, work-with-nick@gmail.com, and a phone number.
- Release: manual release, so the site's App Store button can be switched the same day.

## 9. After approval
App Store Connect record created 2026-09-28: Apple ID **6816947017** (App Store URL once live: https://apps.apple.com/app/id6816947017). Build 1.0.0 (1) uploaded the same day.
- Put the numeric Apple ID into `docs/*.html` (see "SEO after launch" in `10-site-and-email-runbook.md`).
- Set `APP_STORE_URL` in `scripts/make-site.py`'s page template, re-run it, and commit.
