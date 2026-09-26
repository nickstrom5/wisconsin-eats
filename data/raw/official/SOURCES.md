# Official Wisconsin food-establishment sources (surveyed 2026-09-25)

What official government data exists for licensed food establishments in Wisconsin, how to get it in bulk, and what was downloaded. Re-run every download with `_scripts/download_all.sh`. It uses the paginated ArcGIS downloader in `_scripts/arcgis_dl.py`, which sleeps 1 second between pages.

Bottom line: no statewide bulk list of licensed restaurants exists. Two jurisdictions publish usable machine-readable data:
- **City of Milwaukee**: active food licenses with coordinates.
- **Public Health Madison & Dane County (PHMDC)**: establishments, inspections and violations, with addresses only.

Everywhere else, inspection data sits in vendor web portals with no export. A few small alcohol-license layers exist.

## Summary

| Source | Coverage | Format | Rows | Restaurant-type rows | Active/closed signal | Inspections | Lat/lon | Files |
|---|---|---|---|---|---|---|---|---|
| Milwaukee food licenses | City of Milwaukee only | ArcGIS FeatureServer, saved as GeoJSON and CSV | 2,777 (active only) | 1,705 `FREST` | Layer holds only active licenses. `EXPIRATION_DATE` is from 2026-09-26 on. | No | Yes (1 null) | `milwaukee/mke_food_licenses_active.*` |
| Milwaukee alcohol licenses (GIS) | City of Milwaukee | ArcGIS FeatureServer | 1,276 (active only) | 909 `BTAVN` (Class B tavern) | Active only | No | Yes | `milwaukee/mke_alcohol_licenses_active.*` |
| Milwaukee liquor licenses (CKAN) | City of Milwaukee | CSV (cp1252 encoding, CR line endings) | 1,279 | 911 `BTAVN` | `EXP_DATE`/`EFF_DATE`; current licenses | No | No (address and taxkey) | `milwaukee/mke_liquorlicenses_ckan.csv` |
| PHMDC establishments | City of Madison plus all of Dane County | ArcGIS MapServer table | 3,845 | 1,673 `Primarily Restaurant` (1,467 Active or About to Expire) | `LicExpirationStatus` (Active / Expired / Pending / Inactive / About to Expire) | Yes (see the next two rows) | **No**, address only | `madison_dane/phmdc_establishments.csv` |
| PHMDC inspections | Same | ArcGIS table | 25,217 (2012-01-03 to 2026-07-23) | 12,470 at Primarily Restaurant | n/a | Yes: type, date, result | n/a | `madison_dane/phmdc_inspections.csv` |
| PHMDC violations (guidesheet OUT items) | Same | ArcGIS tables, filtered | 38,224 (2021-09-16 to 2026-07-23) | n/a | n/a | Yes: item-level violations with comments | n/a | `madison_dane/phmdc_violations_guidesheet_{2021,2022,2023plus}.csv` |
| DATCP food processing plant license holders | Statewide | CSV | 1,863 | 0. These are processors, not restaurants. About 94 have bakery-like names. | Active only ("Expired licenses are not included") | No | No | `datcp/datcp_food_processing_plant_license_holders.csv` |
| Sauk County alcohol licenses 2026 | Sauk County | ArcGIS FeatureServer | 300 | 223 with any Class B or C (on-premise) | 2026 license-year snapshot | No | Yes | `other_liquor/sauk_county_alcohol_licenses_2026.*` |
| City of Racine liquor licenses | City of Racine | ArcGIS FeatureServer (geocoded) | 199 plus 8 non-renewals | 140 Class B variants | Last edit 2025-08-15 (2025-26 license year); separate non-renewal layer | No | Yes | `other_liquor/racine_city_liquor_licenses*.*` |
| City of Wauwatosa liquor licenses | City of Wauwatosa | ArcGIS FeatureServer (polygons) | 107 structures, 108 parcels | 85 Class B or C variants | **Stale**: last edit 2024-01-19 | No | Approximate centroid | `other_liquor/wauwatosa_liquor_licenses_*.*` |
| City of Janesville alcohol licenses | City of Janesville | ArcGIS FeatureServer (4 layers) | 127 | 101 Class B, C, club or hotel | **Stale**: 2022 license year (last edit 2022-04-15) | No | Yes | `other_liquor/janesville_alcohol_licenses_2022_layer{0-3}.*` |

Every ArcGIS download also has a `.layer.json` file holding the layer metadata exactly as the server returned it. The CSVs are attribute tables. For point layers they include `lon`/`lat` in WGS84 (the downloader requests `outSR=4326`) and dates converted to ISO format.

---

## 1. Wisconsin DATCP (Division of Food & Recreational Safety): no bulk retail-food or restaurant data

- **Retail food establishment license list: none published.** The myDATCP "Registries / Lists" section under Food and Recreational Safety has active-license-holder lists (PDF, XLSX and CSV) only for these categories: Food Processing Plant, Food Warehouse, Dairy Plant, Milk Distributor/Producer, Bulk Milk Weigher, Milk & Cream Tester, and Meat establishment directories. **There is no Retail Food Establishment list.** The page is https://mydatcp.wi.gov/SiteMap/BrowseService/SG_d7c9053b-82c1-e211-b39f-0050568c06ae?Key=Services_Group. HEAD requests for the obvious filenames (`Retail Food Establishment License Holders.csv`, `Retail Food License Holders.csv`) under `https://mydatcp.wi.gov/documents/dfrs/` returned 404.
- **Inspection results, state-inspected establishments:** https://inspections.myhealthdepartment.com/wisconsin-datcp (MyHealthDepartment vendor portal). It is a search interface only, with no export or API offered. **Its robots.txt explicitly disallows `ClaudeBot`, `anthropic-ai`, GPTBot and other AI/data crawlers.** It was not scraped and should not be.
- **Inspection results, agent health departments:** HealthSpace portals, listed in section 4. They are HTML only.
- **data.wi.gov / data.wisconsin.gov / opendata.wi.gov:** none of these hostnames resolve in DNS today. Wisconsin has no working statewide open-data portal.
- **Scale, from DATCP's HealthSpace landing page:** BFRB (the Bureau of Food and Recreational Businesses) oversees about 43,800 facilities, and about 29,200 of them are licensed and inspected by 57 local agent health departments.
- **The only realistic path to statewide data is a public records request** to DATCP DFRS licensing: datcpdfslicensing@wi.gov, (608) 224-4923. See https://datcp.wi.gov/Pages/About_Us/PublicRecords.aspx. Even then it would cover only establishments DATCP licenses directly. Each agent health department holds its own records.

### Downloaded (supplementary): DATCP Food Processing Plant License Holders
- URL: `https://mydatcp.wi.gov/documents/dfrs/Food%20Processing%20Plant%20License%20Holders.csv` (Last-Modified 2026-09-25 02:00 GMT; the report was generated 2026-09-24 9:00 PM). It is regenerated nightly.
- Publisher: WI DATCP, Division of Food & Recreational Safety.
- 1,863 rows. Columns: `LicenseNo, LicenseLegalName1, LicenseDBA, LicenseLegalAddress, LicenseLegalCity, LicenseLegalState, LicenseLegalCounty, LicenseHistorystatus, LicenseExpiration`. Six "X" flag columns follow. The CSV gives them SSRS textbox names, but the XLSX header labels them as follows:
  - `Licensebusinesslogic` = Large Potentially Hazardous
  - `LicenseBusinesslgic` = Large Non-Potentially Hazardous
  - `LicenseSwissCheese` = Small Potentially Hazardous
  - `Textbox35` = Small Non-PHF
  - `Textbox37` = Very Small PHF
  - `Textbox39` = Very Small Non-PHF
- Active signal: the list holds only active licenses. `LicenseHistorystatus` = `Full` for all rows. Expiration is 03/31/2027 except for 1 row.
- These are wholesale food processors (bakeries, candy makers, coffee roasters, canners), **not restaurants**. Useful only to cross-reference bakeries. No lat/lon. The county is blank for 547 rows.

## 2. City of Milwaukee: active food licenses with coordinates, but no inspection bulk data

### Food licenses (downloaded)
- Endpoint: `https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/regulation/license/FeatureServer/9` ("Food licenses"; the MapServer/9 endpoint is identical).
- Publisher: City of Milwaukee (ITMD GIS, from License Division data). The service description says it covers "City of Milwaukee license locations ... food ...". Layer note: "this layer is filtered to only show the active licenses."
- Last updated: `GIS_DATETIME` = 2026-09-25 01:24:36 on every row, so the layer is rebuilt nightly.
- Rows: 2,777. Two `LICENSE_ID`s are duplicated.
- Columns: `OBJECTID, MAP_ID, CORP_NAME, TRADE_NAME, LICENSEE, ENTITY_ADDRESS, TAXKEY_LIRA, ALD_DIST, POLICE_DIST, LIC_TYPE_CODE, LIC_TYPE_ABBR, PROFESSION_FULL_NAME, TOT_CAP, ROOM_CAP, EFFECTIVE_DATE, GRANTED_DATE, ISSUED_DATE, EXPIRATION_DATE, GIS_DATETIME, LICENSE_ID`, plus `lon, lat`.
- Category values:
  - `LIC_TYPE_ABBR = FREST` / `PROFESSION_FULL_NAME = "Food Dealer - Restaurant"` / `LIC_TYPE_CODE = 262`: **1,705** (restaurants)
  - `LIC_TYPE_ABBR = FOOD` / `"Food Dealer Retail"` / `LIC_TYPE_CODE = 8`: 1,072 (grocery, convenience and retail food. Some bakeries or coffee shops may fall here.)
- Active/closed: every row is active. Closed or expired licenses are simply absent, and there is no history. To detect closures, diff snapshots over time.
- Lat/lon: yes, points in WGS84. 1 row has null geometry.
- Overlap: 748 FREST addresses also hold a Class B Tavern license (restaurant-bars).

### Alcohol licenses (downloaded)
- GIS endpoint: `.../regulation/license/FeatureServer/0` ("Alcohol Licenses", active only, same schema, nightly). It has 1,276 rows:

  | LIC_TYPE_ABBR | License | Code | Rows |
  |---|---|---|---|
  | `BTAVN` | Class B Tavern License | 20 | 909 |
  | `ALQML` | Class A Malt & Class A Liquor | 16 | 171 |
  | `AMALT` | Class A Fermented Malt Beverage Retailer | 14 | 89 |
  | `BBEER` | Class B Fermented Malt Beverage Retailer | 18 | 58 |
  | `CWINE` | Class C Wine Retailer | 24 | 39 |
  | `ALIQR` | Class A Retailer's Intoxicating Liquor | 15 | 10 |

  On-premise licenses (bars and restaurants) are `BTAVN`, `BBEER` and `CWINE`. The Class A licenses are off-premise liquor stores and groceries.
- CKAN copy: dataset `liquorlicenses` on data.milwaukee.gov (publisher: City Clerk – License Division). The CSV is at `https://data.milwaukee.gov/dataset/1aba8821-f5f6-4031-b469-5c39c90e99c7/resource/45c027b5-fa66-4de2-aa7e-d9314292093d/download/liquorlicenses.csv`, metadata_modified 2026-09-25T08:52, refreshed nightly.
  - 1,279 rows, with the same LIC_TYPE values (BTAVN 911).
  - Columns: `EXP_DATE, EFF_DATE, CORP_NAME, TRADE_NAME, LICENSEE, TAXKEY_NUMBER, HOUSE_NR, SDIR, STREET, STTYPE, ALDERMANIC_DISTRICT, POLICE_DISTRICT, LIC_TYPE, License Type Full Name, TOT_CAP, ROOM_CAP, TAXKEY`.
  - No lat/lon.
  - **Read it with `encoding="cp1252"`. The line endings are bare CR.**

### Inspections: not available in bulk
- data.milwaukee.gov has "Restaurant and Food Service Inspections", but it is only a CKAN *showcase* (no resources). It links to the Milwaukee Health Department's HealthSpace portal at https://www.healthspace.com/Clients/WI/Milwaukee/Web.nsf/home.xsp.
- That portal is an HTML A–Z facility list plus per-facility pages (name, address, last inspection date, type such as "Retail Food - Serving Meals"). It has no CSV, API or export. Not scraped.
- CKAN searches for food, license, restaurant, inspection, health and tavern turned up nothing else relevant among the 196 datasets.

## 3. Madison / Public Health Madison & Dane County (PHMDC): establishments, inspections and violations, with no coordinates

The ArcGIS Online items "Licensed Establishment" (id 2347e4149219405aac0e9f3fb69c79d1) and "Establishment Inspection" (id 878ab9bb8a8e4acea50dc06edfa37d3c) on the Madison hub point to `.../rest/services/Public/OPEN_DB_TABLES/...`, **which is dead (404)**. The live service sits at the root of the server:

- Service: `https://maps.cityofmadison.com/arcgis/rest/services/OPEN_DB_TABLES/MapServer`, tables 5, 7 and 10–14. Supports query and pagination. maxRecordCount is 2000.
- Publisher: City of Madison GIS. The data comes from Public Health Madison & Dane County ("accessInformation: Public Health Madison & Dane County"; license: City of Madison Data Policy).
- Last updated: `RecDate` = 2026-09-16 05:00 on all rows (looks like a periodic full reload). The latest `InspectionDate` is 2026-07-23, so expect roughly a 2-month lag in inspections.
- Coverage: all of Dane County, because PHMDC is the DATCP agent for the whole county. 2,054 rows are in Madison. The rest are in Sun Prairie, Middleton, Fitchburg, Stoughton, Verona, Monona, Waunakee, DeForest and others. `AddrCity` is inconsistent: "Madison", "MADISON", "CITY OF MIDDLETON", "VILLAGE OF ...".

### Table 5 "PHMDC Restaurant Establishment" → `madison_dane/phmdc_establishments.csv`
- 3,845 rows, with unique `LicenseNbr`.
- Columns: `LicenseNbr, LicenseAppStatus, DoingBusinessAsName, LicExpirationDate, LicExpirationStatus, AddressFull, AddrStreetNo, AddrStreetDir, AddrStreetName, AddrStreetType, AddrUnit, PrimarilyRestaurant, RetailFoodEstab, RestaurantMobileCart, RestaurantMobileBase, RetailMobileCart, RetailMobileBase, FarmersMarket, RecDate, EstablishmentType, AddrCity, ESRI_OID`. The seven flag columns (PrimarilyRestaurant … FarmersMarket) are **all null**. Use `EstablishmentType`.
- `EstablishmentType` × `LicExpirationStatus`:

  | EstablishmentType | Active | About to Expire | Expired | Pending | Inactive | Total |
  |---|---|---|---|---|---|---|
  | **Primarily Restaurant** | 1,465 | 2 | 168 | 38 | 0 | 1,673 |
  | Retail Food Establishment | 668 | 3 | 57 | 15 | 0 | 743 |
  | Restaurant Mobile Cart | 111 | 0 | 19 | 14 | 0 | 144 |
  | Restaurant Mobile Base | 54 | 0 | 12 | 7 | 0 | 73 |
  | Retail Mobile Cart | 40 | 0 | 1 | 0 | 0 | 41 |
  | Retail Mobile Base | 3 | 0 | 0 | 1 | 0 | 4 |
  | Farmers Market | 4 | 0 | 2 | 1 | 0 | 7 |
  | Establisment Type not defined (sic) | 151 | 0 | 7 | 3 | 9 | 170 |
  | Swimming Pool | 465 | 0 | 25 | 7 | 0 | 497 |
  | Hotel/Motel | 341 | 0 | 46 | 7 | 0 | 394 |
  | Tattoo/Body Piercing | 67 | 0 | 19 | 1 | 0 | 87 |
  | Bed and Breakfast | 10 | 0 | 2 | 0 | 0 | 12 |

- Active/closed: `LicExpirationStatus` in {Active, About to Expire} means current. Expired means lapsed or closed. Pending means a new or renewing application. `LicenseAppStatus` is a secondary signal: Active 3,377 / Expired 373 / Under Review 76 / Open 15 / other 4. `LicExpirationDate` ranges from 2023-06-30 to 2027-06-30, and the license year ends June 30.
- Lat/lon: **none**. Only a single-line address (`AddressFull` has an embedded newline) plus parsed street parts. Geocoding is needed.

### Table 7 "PHMDC Restaurant Inspection" → `madison_dane/phmdc_inspections.csv`
- 25,217 rows, 2012-01-03 to 2026-07-23. Joins to establishments on `LicenseNbr`, and 100% of rows match.
- Columns: `LicenseNbr, InspectionNbr, InspectionType, InspectionDate, InspecDispositionStatus, InspecResultStatus, InspecResultStatusDate, InspecResultType, RecDate, ID`.
- `InspectionType`: Routine Inspection 18,604; Pre-Inspection/Pre-inspection 2,728; First Reinspection Chargeable 2,158; Re-Inspection Chargeable 784; Reinspection Non-Chargeable 372; Subsequent Reinspection Chargeable 305; Re-Inspection Non-Chargeable 113; Reinspection 83; Second Reinspection Chargeable 69; HACCP 1.
- Result:
  - `InspecResultType` APPROVED 20,768 / DENIED 4,445.
  - `InspecResultStatus` "No Reinspection Required" 20,768 / "Reinspection Required" 4,438 / "Immediate Suspension" 7 / "Cancelled" 4.
  - `InspecDispositionStatus` "Insp Completed" 20,768 / "Insp Cancelled" 4,449.
  - Note: DENIED rows carry disposition "Insp Cancelled", so check both fields when interpreting.
- Only inspections of establishments still in table 5 are present. Inspections of long-closed places are not.

### Tables 10/11/12 "PHMDC Restaurant Guidesheet 2023 / 2022 / 2021" → `madison_dane/phmdc_violations_guidesheet_*.csv`
- Item-level inspection checklists. The full tables are large: 2023+ has 869,263 rows, 2022 has 151,898 and 2021 has 40,967. Tables 13 (2020) and 14 (2019) are empty.
- **Only the violation rows were downloaded**, using `where GUIDE_ITEM_STATUS IN ('OUT','Violation(s)')`: 31,661 + 5,128 + 1,435 = **38,224 rows**, covering inspections from 2021-09-16 to 2026-07-23.
- Columns: `GuidesheetID, LicenseNbr, InspectionNbr, GUIDESHEET_SEQ_NBR, GUIDE_TYPE, GUIDE_ITEM_DISPLAY_ORDER, GUIDE_ITEM_TEXT, GUIDE_ITEM_STATUS, GUIDE_ITEM_COMMENT, RepeatViolation, CorrectedOnsite, RecDate, ComplianceDate, InspectionDate`.
- `GUIDE_TYPE`:
  - `IONN 2017` / `IONN OTHER 2017` are FDA foodborne-illness risk factors and public-health interventions, the serious items. Top examples: TEMPERATURE - COLD HOLDING, DATE MARK, SANITIZATION - CHEMICAL.
  - `GRP 2017` / `GRP OTHER 2017` are Good Retail Practices. Top example: SANITIZER TEST KIT.
  - `POOL ...`, `HMT` (hotel/motel), `TBP` (tattoo/body piercing) and `BNB` are non-food.
- `RepeatViolation` = CHECKED on 1,218 rows. `CorrectedOnsite` = CHECKED on 12,254 rows.
- Other status values in the full tables (not downloaded): IN, NA, N/A, NO, N, Y, No Violation.

## 4. Other Wisconsin counties and cities

### Food inspections and licenses: no open bulk data found anywhere else
DATCP's own "Map of retail food agents" (https://www.healthspace.com/Clients/WI/State/statewebportal.nsf/map.xsp) shows that **every local agent health department except PHMDC publishes inspections only through a HealthSpace portal**. That covers `https://www.healthspace.com/Clients/WI/<Name>/Web.nsf`. Counties and cities inspected directly by DATCP use the MyHealthDepartment portal described in section 1.

HealthSpace portals are HTML A–Z lists and per-facility pages, with no CSV, API or export. Checked examples: the Milwaukee and Appleton pages, and the Walworth County and Portage County pages that link out to them. **None were scraped.** Agents on HealthSpace:
- Adams, Appleton, Ashland, Barron, Bayfield, Brown (Green Bay), Buffalo
- Central Racine County, Chippewa, City of Franklin, De Pere, Douglas, Dunn, Eau Claire
- Environmental Health Consortium (Cudahy / South Milwaukee / St. Francis)
- Florence, Fond du Lac, Greendale, Greenfield, Hales Corners, Iron, Jackson, Jefferson–Watertown, Juneau, Kenosha, La Crosse, Langlade, Lincoln
- Manitowoc, Marathon, Menasha, City of Milwaukee, North Shore, Oak Creek, Oneida, Outagamie, Pepin, Pierce, Polk, Portage
- Racine (city), Rock, Rusk, Sawyer, Sheboygan, South Central (Sauk), Taylor, Trempealeau, Tri-County (REHA), University EHP, Vernon, Vilas
- Washington, **Waukesha County**, Waupaca, **Wauwatosa**, **West Allis**, West Milwaukee, **Winnebago**, Wood

Walworth County and other DATCP-direct counties are covered by the state portal only.

ArcGIS Online and Hub searches (food, restaurant, inspection, license and liquor terms, crossed with about 45 WI place names) found **no** official food-license or food-inspection layer for any WI government other than Milwaukee and Madison. The hits were student or university projects, food pantries, and private company maps. None are official license data.

### Alcohol / tavern licenses (machine-readable, downloaded)
- **Sauk County alcohol licenses 2026**
  - Endpoint: `https://services5.arcgis.com/4lnceVNfgKvUXLJv/arcgis/rest/services/Sauk_County_Alcohol_Licenses_2026/FeatureServer/0`
  - Owner: SaukPublicHealth (Sauk County Health Department). Item modified 2026-01-16.
  - 300 rows, compiled from the municipalities in the county.
  - Columns: `BusinessName, BusinessAddress, City, State, Zip, County, Municipality, Class_A_Beer, Class_A_Cider, Class_A_Liquor, Class_B_Beer, Class_B_Liquor, Class_C_Wine, FID`. The class columns are 0/1 flags.
  - On-premise (bar or restaurant) means `Class_B_Beer=1 OR Class_B_Liquor=1 OR Class_C_Wine=1`: 223 rows (Class_B_Beer 223, Class_B_Liquor 159, Class_C_Wine 34).
  - Points: yes. No status field; it is the 2026 snapshot.
- **City of Racine "Liquor License Locations"**
  - Endpoint: `https://services5.arcgis.com/WgCOhpTBP3tb7eDk/arcgis/rest/services/Liquor_Licenses_Updated/FeatureServer/0`
  - Owner: City of Racine, WI org. Last edit 2025-08-15.
  - 199 rows, geocoded with the Esri World geocoder.
  - Useful columns: `USER_BUS_NAME, USER_DBA, USER_OPER_NAME, USER_License_Type, USER_Full_Address, USER_LOC_*`, plus geocoder fields (`Score`, `Match_addr`, `X`, `Y`).
  - `USER_License_Type` values are messy: "CLASS B" 116, CLASS "A" 33, "CLASS A" 26, CLASS "B" AND "CLASS C" 6, "CLASS B" Club 5, CLASS "B" Public Facility 4, CLASS "B" 4, RESERVED "CLASS B" 3+1, CLASS B 1. Everything containing "B" or "C" is on-premise: 140 rows.
  - Companion layer `Liquor_License_Non_Rewewals/FeatureServer/0` has 8 rows of licenses not renewed (includes `USER_Turned_In`). Use it to mark closures.
- **City of Wauwatosa "Liquor_Licenses"**
  - Endpoint: `https://services5.arcgis.com/gyXZ0hXCxDXxFxHi/arcgis/rest/services/Liquor_Licenses/FeatureServer/0` (structures, 107 rows) and `/1` (parcels, 108 rows).
  - Polygons. The CSV has approximate vertex-mean centroids (`lon_centroid_approx`, `lat_centroid_approx`).
  - **Stale**: last edit 2024-01-19.
  - `Class` values: Class B Combo 44, Reserve Class B Combo 28, Class A Combo 20, Class B (Beer) and Class C (Wine) 8, Class B Beer 2, Class A Liquor 1, Class A Beer 1, Class C Wine 1, PEDD Class B Combo 1, Class B Combo (300 Seat Exemption) 1.
- **City of Janesville "Alcohol Licenses"**
  - Endpoint: `https://services2.arcgis.com/i52vmcFqzIWK9plW/arcgis/rest/services/Alcohol_Licenses/FeatureServer/{0,1,2,3}`
  - **Stale**: 2022 license year (license numbers 2022-xxx; last edit 2022-04-15).
  - 127 rows total. `LicenseTyp` values: CLASS B IL & FMB 59, CLASS A IL & FMB 26, CLASS B BEER ONLY 11, CLASS B IL & FMB SPECIAL FOR RESTAURANTS 9, CLASS B RESERVE IL & FMB 8, CLASS C WINE 7, CLUB 5, CLASS B MOTEL/HOTEL 2.

### Found but not downloaded (too old to represent current establishments)
- La Crosse County `AlcoholTobacco` FeatureServer (https://services.arcgis.com/YTojcvpJ9GpgYxjF/arcgis/rest/services/AlcoholTobacco/FeatureServer): Alcohol layer with 314 rows. Last edit 2020-11-30.
- Winnebago County `Liquor licenses Winnebago county 2019_Full` (https://services3.arcgis.com/6sBmb6JOWXOANYPt/arcgis/rest/services/Liquor%20licenses%20Winnebago%20county%202019_Full/FeatureServer): 410 rows of 2019 data.

## Places with NO usable bulk official data
- **Statewide (DATCP):** no retail food or restaurant license list and no inspection bulk data. The inspection portal is search-only and its robots.txt forbids AI crawlers. A public records request is the only route.
- **Milwaukee inspections:** HealthSpace HTML only. The licenses are available (section 2).
- **Every county and city other than Milwaukee (licenses) and Dane County/Madison (licenses and inspections):** including Waukesha County, Brown County/Green Bay, Kenosha, Racine (food), La Crosse, Eau Claire, Outagamie/Appleton, Winnebago/Oshkosh, Sheboygan, Marathon/Wausau, Rock/Janesville (food), Wauwatosa (food) and West Allis. Their food data is only in HealthSpace or MyHealthDepartment web portals, with no export.
- **Wisconsin statewide open-data portal:** does not exist (data.wi.gov does not resolve).
