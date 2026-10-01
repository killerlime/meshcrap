import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'source/dashboard'))
from environment_evidence import adsb_summary, counter_rate, precipitation_report


class EvidenceTests(unittest.TestCase):
    def test_remote_and_stale_positions_not_counted(self):
        aircraft = dict(type='adsb_icao', seen=1, seen_pos=2, lat=40, lon=-100, rssi=-20)
        result = adsb_summary(dict(now=1000, aircraft=[aircraft,
            aircraft | {'mlat':['lat','lon']}, aircraft | {'seen_pos':100},
            aircraft | {'type':'tisb_icao'}, aircraft | {'seen':100}]), 1001)
        self.assertEqual(result['fresh_aircraft'], 4)
        self.assertEqual(result['adsb_positions'], 1)
        self.assertEqual(result['excluded_positions'], 2)
        self.assertFalse(result['local_reception_verified'])
        self.assertEqual(result['median_rssi_dbfs'], -20)

    def test_stale_snapshot(self):
        with self.assertRaises(ValueError):
            adsb_summary(dict(now=100, aircraft=[]), 1000)

    def test_missing_signal_is_not_zero(self):
        self.assertIsNone(adsb_summary(dict(now=1000,aircraft=[]),1001)['median_rssi_dbfs'])

    def test_counter_resets_and_duplicate_time(self):
        self.assertIsNone(counter_rate(100, 10, 1, 2))
        self.assertIsNone(counter_rate(100, 110, 1, 1))
        self.assertEqual(counter_rate(100, 120, 1, 11), 2)

    def test_trace_zero_missing_are_distinct(self):
        row=dict(stationNumber='TEST-1',id=1,obsDateTime='2026-01-01T07:00:00',units='english',precip=0)
        self.assertEqual(precipitation_report(row,'TEST-1')['precipitation_state'],'measured')
        self.assertEqual(precipitation_report(row | {'precipIsTrace':True},'TEST-1')['precipitation_state'],'trace')
        self.assertEqual(precipitation_report(row | {'precip':None},'TEST-1')['precipitation_state'],'missing')
        self.assertFalse(precipitation_report(row,'TEST-1')['interval_verified'])
        with self.assertRaises(ValueError):
            precipitation_report(row,'TEST-11')


if __name__ == '__main__': unittest.main()
