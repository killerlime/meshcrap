"""Profile evidence, not a path-loss model or a 915 MHz ducting detector.

Refractivity: ITU-R P.453-14 Annex 1 equation 6. Modified refractivity uses
Earth radius 6371 km. Inputs must supply actual level pressure and vapour
pressure; sea-level-adjusted station pressure and surface RH are not profiles.
"""
import math
from datetime import datetime


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def refractivity(pressure_hpa, temperature_k, vapour_pressure_hpa):
    if not all(finite(v) for v in (pressure_hpa, temperature_k, vapour_pressure_hpa)):
        raise ValueError('Nonfinite atmospheric value')
    if not (50 <= pressure_hpa <= 1100 and 180 <= temperature_k <= 330 and
            0 <= vapour_pressure_hpa <= min(100, pressure_hpa)):
        raise ValueError('Atmospheric value outside supported range')
    p, t, e = pressure_hpa, temperature_k, vapour_pressure_hpa
    return 77.6*p/t - 5.6*e/t + 375000*e/(t*t)


def profile_evidence(profile):
    """Accept one co-located, same-valid-time profile with explicit provenance.

    Gaps over 250 m are left unresolved, not interpolated into a claimed layer.
    Heights must increase; pressure must decrease. Single-level data cannot
    establish a gradient. Forecasts remain forecasts even after their valid time.
    """
    if not isinstance(profile,dict) or profile.get('kind') not in ('observation', 'analysis', 'forecast'):
        raise ValueError('Specify observation, analysis or forecast provenance')
    for key in ('source', 'valid_time', 'height_datum'):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ValueError('Missing profile provenance: '+key)
    if profile['height_datum'] not in ('geometric_msl', 'geometric_agl'):
        raise ValueError('Convert heights to a consistent geometric datum first')
    try:
        when=datetime.fromisoformat(profile['valid_time'].replace('Z','+00:00'))
        if when.tzinfo is None:raise ValueError('Timestamp requires a timezone')
    except (ValueError,TypeError) as exc:
        raise ValueError('Specify an ISO valid time with timezone') from exc
    rows = profile.get('levels')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise ValueError('Invalid profile size')
    levels = []
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid profile level')
        h = row.get('height_m')
        if not finite(h) or not -500 <= h <= 20000:
            raise ValueError('Invalid profile height')
        n = refractivity(row.get('pressure_hpa'), row.get('temperature_k'), row.get('vapour_pressure_hpa'))
        if levels and (h <= levels[-1]['height_m'] or row['pressure_hpa'] >= levels[-1]['pressure_hpa']):
            raise ValueError('Profile levels must rise with decreasing pressure')
        levels.append(dict(height_m=h, pressure_hpa=row['pressure_hpa'], n=n,
                           m=n+1e6*h/6371000))
    layers = []
    for lower, upper in zip(levels, levels[1:]):
        gap = upper['height_m']-lower['height_m']
        gradient = (upper['m']-lower['m'])/gap*1000
        resolved = gap <= 250
        layers.append(dict(bottom_m=lower['height_m'], top_m=upper['height_m'],
                           thickness_m=gap, dm_per_km=gradient,
                           classification=('unresolved_spacing' if not resolved else
                                           'negative_modified_gradient' if gradient < 0 else
                                           'no_negative_gradient_in_sample')))
    candidates = sum(l['classification']=='negative_modified_gradient' for l in layers)
    return dict(kind=profile['kind'], source=profile['source'], valid_time=profile['valid_time'],
                height_datum=profile['height_datum'], levels=levels, layers=layers,
                candidate_layers=candidates, path_ducting_confirmed=False,
                statement=('Vertical profile required; surface data alone cannot identify a duct.' if not layers else
                           'Negative modified-refractivity gradient sampled; possible trapping layer, not confirmation of a radio path.' if candidates else
                           'No resolved negative gradient found. Thin or unsampled layers may still exist.'),
                limitations=['No frequency-dependent trapping or terrain calculation',
                             'Profile location and valid time must match the region being compared',
                             'Layer boundaries and minimum usable frequency are not estimated'])
