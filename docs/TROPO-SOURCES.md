# Tropospheric evidence: source review

Reviewed 2026-10-01. Integration is experimental and optional. This document
distinguishes usable source interfaces from adapters that are actually enabled.
No background atmospheric polling is enabled by this release work.

## Prepared forecasts from the amateur-radio community

**Tropocast (SQ3A)** is the strongest documented API candidate found so far.
Its [Device API](https://tropocast.eu/developers) serves JSON manifests and small
forecast images. [OpenAPI](https://tropocast.eu/openapi.json) also documents public
status and forecast metadata. Read-only checks of `/api/v1/device/status` and
`/api/v1/tropo/metadata?area=world&source=gdps&model=full` returned successfully.
The status response advertised an enabled API and public developer previews.

The worldwide GDPS source is the relevant option outside Europe; ICON-EU covers
Europe. GDPS updates twice daily and ICON-EU four times daily. Production Device
API credentials require project approval. Keys belong in private server-side
storage and the `X-Tropocast-Key` header, never in URLs or browser code. No account
has been created or approval requested on the user's behalf.

A compact image is useful for a regional context panel. It is **not numeric RF
evidence**: the verified Device API provides rendered products, not a documented
per-location duct strength time series. Do not infer numbers from colors.
Keep source/model/run/valid time and attribution visible, and verify permitted
redistribution/caching before releasing a bundled integration. Start with one
current frame, loaded only when viewed; do not preload a whole forecast animation.

**F5LEN** provides worldwide refractivity forecast layers, including GeoTIFF
data used by its interactive map. The [author's description and terms](https://tropo.f5len.org/WW/info.php)
describe roughly 4 MB per dataset, four daily runs, and personal/internal,
non-commercial use without redistribution or alteration. That makes the site
useful for private comparison, but not a dataset to bundle with this public app.
The displayed quantity is an averaged refractive index, not direct proof of a
negative vertical modified-refractivity gradient. Keep it distinct from a
profile-based trapping-layer calculation.

**Hepburn / DX Info Centre** provides a mature visual forecast; its
[forecast page](https://www.dxinfocentre.com/tropo.html) and
[license terms](https://www.dxinfocentre.com/licence.htm) govern reuse. No documented
numeric public API was found in the reviewed pages. Link to the source rather
than scrape or repackage forecast images without permission.

**DXView / NG0E** provides [live APRS propagation](https://vhf.dxview.org/) and a
text interface. Its observations concern stations near 144 MHz. This is useful
independent evidence of regional propagation changes, but neither a calibrated
915 MHz measurement nor a definitive mechanism classification. No stable numeric
API or redistribution grant was verified in this review. APRS receiver density,
internet feeds and digipeater paths must be handled before drawing conclusions.

## Public atmospheric measurements and models

**NOAA HRRR through NOMADS** supplies regional forecast fields via HTTPS GRIB2
and [subset requests](https://www.cpc.ncep.noaa.gov/products/wesley/scripting_grib_filter.html).
Use the [product inventory](https://www.nco.ncep.noaa.gov/pmb/products/hrrr/) to select
the actual vertical temperature, pressure, moisture and height fields. Surface-only
weather and sparsely spaced pressure levels can miss thin layers. Native vertical
levels are a better candidate but need explicit decoding and unit/datum checks.
The existing 2D filter alone is not a verified full-profile adapter.

**NOAA IGRA** offers observed radiosonde profiles and metadata through
[documented HTTPS files](https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive),
including recent per-station archives. This is machine-readable public data rather
than a JSON tropo API. Check station position, observation time, quality flags,
geopotential-versus-geometric height and vertical resolution. A distant sounding
is regional evidence, not a measurement directly above every radio path.
Cite the source dataset and subset: DOI 10.7289/V5X63K0Q.

**NWS JSON API** supplies supplemental alerts, observations and forecasts under
its [public API documentation](https://www.weather.gov/documentation/services-web-api).
These add weather context; surface values alone do not establish a duct.
The bounded cache in `source/dashboard/public_weather_cache.py` is tested but
not connected to a scheduled worker or UI yet.

## Resource budget and honesty rules

- One separately scheduled worker; no model download or processing in page requests.
- Conditional requests, duplicate-run detection, timeouts, byte limits and failure
  backoff. Match cadence to model updates, not to the dashboard refresh timer.
- Request only the configured region and necessary variables. Keep small summaries
  for months; retain bulky raw fields only under a bounded storage policy.
- Record forecast run, valid time, observed time and collection time separately.
  Missing/stale data stays missing/stale; do not fill it with zero.
- Show forecast potential, measured atmospheric profiles and local RF anomalies
  as distinct layers. Neither an attractive forecast color nor a long packet path
  proves ducting at 915 MHz.
- Compare direct RF paths within the same radio/channel/antenna/LNA configuration
  epoch. Exclude internet-injected traffic and do not use relayed origin distance
  as a direct reception range. Aircraft altitude and traffic volume confound ADS-B.

## Implemented calculation boundary

`tropo_evidence.py` implements the refractivity expression in
[ITU-R P.453-14](https://www.itu.int/rec/R-REC-P.453-14-201908-I/en), then evaluates
adjacent modified-refractivity gradients in supplied geometric-height profiles.
It rejects bad ordering and nonfinite values, keeps forecasts labeled, and marks
gaps above 250 m unresolved. That spacing cutoff is an application screening
choice, not an ITU resolution guarantee. No layer thickness implies a verified
minimum usable frequency. Tests cover dry/wet reference values, coarse samples,
surface-only input, and an inversion that is not a trapping candidate.

Next: verify a bounded source profile end-to-end, compare against a trusted
reference calculation, then add the regional map and matched-window correlation
view. Do not present the current offline foundation as a live ducting monitor.
