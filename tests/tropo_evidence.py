import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source/dashboard'))
from tropo_evidence import refractivity, profile_evidence


def profile(levels):
    return dict(kind='forecast',source='Synthetic fixture',valid_time='2026-01-01T00:00:00Z',
                height_datum='geometric_agl',levels=levels)


def level(h,p=1000,t=300,e=10):
    return dict(height_m=h,pressure_hpa=p,temperature_k=t,vapour_pressure_hpa=e)


class TropoTests(unittest.TestCase):
    def test_reference_values(self):
        self.assertAlmostEqual(refractivity(1000,300,0),258.6666666667)
        self.assertAlmostEqual(refractivity(1000,300,10),300.1466666667)

    def test_surface_is_insufficient(self):
        r=profile_evidence(profile([level(0)]))
        self.assertEqual(r['candidate_layers'],0)
        self.assertIn('surface',r['statement'])

    def test_drying_layer_is_candidate_not_proof(self):
        r=profile_evidence(profile([level(0,e=20),level(100,p=988,e=5)]))
        self.assertEqual(r['candidate_layers'],1)
        self.assertFalse(r['path_ducting_confirmed'])
        self.assertEqual(r['kind'],'forecast')

    def test_coarse_layers_not_claimed(self):
        r=profile_evidence(profile([level(0,e=20),level(500,p=940,e=0)]))
        self.assertEqual(r['layers'][0]['classification'],'unresolved_spacing')
        self.assertEqual(r['candidate_layers'],0)

    def test_inversion_alone_is_not_candidate(self):
        r=profile_evidence(profile([level(0,e=10),level(100,p=988,t=301,e=10)]))
        self.assertEqual(r['candidate_layers'],0)

    def test_invalid_order_and_nonfinite(self):
        for rows in ([level(0),level(0,p=990)],[level(0),level(100,p=1001)],
                     [level(float('nan'))],[level(0,t=True)]):
            with self.assertRaises(ValueError):profile_evidence(profile(rows))


if __name__=='__main__':unittest.main()
