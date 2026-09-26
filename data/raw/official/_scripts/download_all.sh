#!/bin/zsh
# Re-download every official bulk source listed in ../SOURCES.md.
# Polite: 1 s sleep between pages (inside arcgis_dl.py), sequential requests only.
set -euo pipefail
cd "$(dirname "$0")/.."
P=/Users/nicksoderstrom/Developer/claudecode/wi-eats/.venv/bin/python
D=_scripts/arcgis_dl.py
UA="Mozilla/5.0 (Macintosh) wi-eats-research/0.1 (polite bulk download of public open data)"
mkdir -p milwaukee madison_dane datcp other_liquor

# --- City of Milwaukee (License Division GIS; active licenses only, refreshed nightly)
MKE=https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/regulation/license/FeatureServer
$P $D $MKE/9 milwaukee/mke_food_licenses_active
$P $D $MKE/0 milwaukee/mke_alcohol_licenses_active
curl -sL -A "$UA" -o milwaukee/mke_liquorlicenses_ckan.csv \
  "https://data.milwaukee.gov/dataset/1aba8821-f5f6-4031-b469-5c39c90e99c7/resource/45c027b5-fa66-4de2-aa7e-d9314292093d/download/liquorlicenses.csv"

# --- Public Health Madison & Dane County (City of Madison ArcGIS Server, OPEN_DB_TABLES)
MAD=https://maps.cityofmadison.com/arcgis/rest/services/OPEN_DB_TABLES/MapServer
$P $D $MAD/5 madison_dane/phmdc_establishments
$P $D $MAD/7 madison_dane/phmdc_inspections
W="GUIDE_ITEM_STATUS IN ('OUT','Violation(s)')"
$P $D $MAD/10 madison_dane/phmdc_violations_guidesheet_2023plus "$W"
$P $D $MAD/11 madison_dane/phmdc_violations_guidesheet_2022 "$W"
$P $D $MAD/12 madison_dane/phmdc_violations_guidesheet_2021 "$W"

# --- DATCP (statewide) food processing plant license holders (NOT restaurants; supplementary)
curl -s -A "$UA" -o datcp/datcp_food_processing_plant_license_holders.csv \
  "https://mydatcp.wi.gov/documents/dfrs/Food%20Processing%20Plant%20License%20Holders.csv"

# --- Other municipal/county alcohol license layers (small; check freshness in SOURCES.md)
$P $D "https://services5.arcgis.com/4lnceVNfgKvUXLJv/arcgis/rest/services/Sauk_County_Alcohol_Licenses_2026/FeatureServer/0" other_liquor/sauk_county_alcohol_licenses_2026
$P $D "https://services5.arcgis.com/WgCOhpTBP3tb7eDk/arcgis/rest/services/Liquor_Licenses_Updated/FeatureServer/0" other_liquor/racine_city_liquor_licenses
$P $D "https://services5.arcgis.com/WgCOhpTBP3tb7eDk/arcgis/rest/services/Liquor_License_Non_Rewewals/FeatureServer/0" other_liquor/racine_city_liquor_license_nonrenewals
$P $D "https://services5.arcgis.com/gyXZ0hXCxDXxFxHi/arcgis/rest/services/Liquor_Licenses/FeatureServer/0" other_liquor/wauwatosa_liquor_licenses_structures
$P $D "https://services5.arcgis.com/gyXZ0hXCxDXxFxHi/arcgis/rest/services/Liquor_Licenses/FeatureServer/1" other_liquor/wauwatosa_liquor_licenses_properties
for L in 0 1 2 3; do
  $P $D "https://services2.arcgis.com/i52vmcFqzIWK9plW/arcgis/rest/services/Alcohol_Licenses/FeatureServer/$L" other_liquor/janesville_alcohol_licenses_2022_layer$L
done
