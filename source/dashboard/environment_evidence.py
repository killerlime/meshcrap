"""Offline normalization for optional environmental comparisons; never radio data.

Input contracts: FlightAware dump1090 README-json.md and CoCoRaHS DailyPrecipObs.
No network access, source writes, account credentials or background polling.
"""
import math
import statistics


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def adsb_summary(snapshot, collected_at, max_age=120):
    """Aggregate a snapshot without retaining aircraft identities or tracks.

    Remote/unknown positions are excluded from the ADS-B position count. A
    directly encoded ADS-B position is not proof of a local RF reception: input
    may also contain network-fed messages. Range/correlation claims are omitted.
    """
    stamp = snapshot.get('now')
    if not number(stamp) or not number(collected_at) or not 0 <= collected_at-stamp <= max_age:
        raise ValueError('Stale or invalid ADS-B snapshot time')
    rows = snapshot.get('aircraft')
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Invalid aircraft snapshot')
    fresh = positioned = excluded = 0
    signals = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid aircraft record')
        age = row.get('seen')
        if not number(age) or not 0 <= age <= 60:
            continue
        fresh += 1
        remote = set(row.get('mlat') or []) | set(row.get('tisb') or [])
        lat, lon, age_pos = row.get('lat'), row.get('lon'), row.get('seen_pos')
        valid = (number(lat) and number(lon) and -90 <= lat <= 90 and
                 -180 <= lon <= 180 and number(age_pos) and 0 <= age_pos <= 60)
        if valid and row.get('type') in ('adsb_icao', 'adsb_icao_nt', 'adsb_other') and not {'lat', 'lon'} & remote:
            positioned += 1
            signal = row.get('rssi')
            if number(signal) and -100 <= signal <= 0:
                signals.append(signal)
        elif valid:
            excluded += 1
    return dict(source='dump1090', band_mhz=1090, observed_at=stamp,
                collected_at=collected_at, fresh_aircraft=fresh,
                adsb_positions=positioned, excluded_positions=excluded,
                median_rssi_dbfs=statistics.median(signals) if signals else None,
                signal_samples=len(signals), local_reception_verified=False)


def counter_rate(previous, current, previous_time, current_time):
    """Return no estimate across unknown values, time reversal or counter reset."""
    if not all(number(v) for v in (previous, current, previous_time, current_time)):
        return None
    if previous < 0 or current < previous or current_time <= previous_time:
        return None
    return (current-previous)/(current_time-previous_time)


def precipitation_report(row, station):
    """Keep original time strings/units; don't invent an accumulation interval.

    Station searches may be substring-based, so require an exact identity here.
    A trace is distinct from a measured zero. Notes and coordinates are omitted.
    """
    if row.get('stationNumber') != station:
        raise ValueError('Station identity mismatch')
    value = row.get('precip')
    trace = row.get('precipIsTrace') is True
    if value is not None and (not number(value) or value < 0):
        raise ValueError('Invalid precipitation amount')
    units = row.get('units')
    if units not in ('english', 'metric'):
        raise ValueError('Unknown source units')
    if not isinstance(row.get('obsDateTime'), str) or not row['obsDateTime']:
        raise ValueError('Missing observation date')
    return dict(source='CoCoRaHS', station=station, report_id=row.get('id'),
                observation_time_original=row['obsDateTime'],
                revision_time_original=row.get('dateTimeStamp'),
                units_original=units, precipitation_original=value,
                precipitation_state='trace' if trace else 'missing' if value is None else 'measured',
                accumulation_start=None, accumulation_end=None,
                interval_verified=False)
