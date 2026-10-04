"""Synthetic trip evidence; no radios or private coordinates."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source/dashboard'))
from survey_evidence import summarize

def position(at=1000,lat=1.5,accuracy=10):
    return dict(lat=lat,lon=2.5,time=at,source='phone_gps',accuracy_m=accuracy)

def trace(status='requested',channel=0,at=1000):
    return dict(kind='trace',source=1,destination=2,channel=channel,packet_id=3,
                requested_at=at,time=at,status=status,position=position(at))

def report(events):
    return summarize((dict(body=json.dumps(e)) for e in events),len(events))

class EvidenceTests(unittest.TestCase):
    def test_whole_trip_and_channel_collision(self):
        events=[trace(),trace('success'),trace('timeout',channel=1)]
        events += [dict(kind='position',source=1,time=1000+i,position=position()) for i in range(5100)]
        r=report(events)
        self.assertEqual((r['trace_count'],r['successes']),(2,1))
        self.assertEqual(r['metrics']['records'],5103)
        self.assertEqual(r['metrics']['unique_fixes'],1)
        self.assertEqual(r['metrics']['repeated_fixes'],5099)

    def test_pending_not_reply_rate_denominator_and_late_reply_wins(self):
        r=report([trace('timeout'),trace('late_success'),trace(at=1100)])
        self.assertEqual(r['metrics']['reply_fraction'],1)
        self.assertEqual(r['metrics']['incomplete'],1)
        self.assertEqual(r['metrics']['late_replies'],1)

    def test_approximate_gps_and_implausible_jump_do_not_make_coverage(self):
        events=[dict(kind='position',source=1,time=t,position=position(t,lat,a))
                for t,lat,a in [(1000,1.5,10),(1015,5,10),(1030,5.1,700)]]
        r=report(events)
        self.assertEqual(r['metrics']['reliable_distance_miles'],0)
        self.assertEqual(r['metrics']['rejected_jumps'],1)
        self.assertEqual(r['metrics']['approximate_fixes'],1)
        self.assertFalse(r['evidence'])

    def test_receptions_deduplicate_and_require_nearby_fix_time(self):
        event=dict(kind='reception',source=1,sender=2,packet_id=3,channel=0,time=1000,rx_time=1000,position=position())
        old=dict(event,packet_id=4,rx_time=950)
        r=report([event,event,old])
        self.assertEqual(r['metrics']['received_packets'],2)
        self.assertEqual(r['metrics']['heard_nodes'],1)
        self.assertEqual(len(r['evidence']),1)

if __name__=='__main__':unittest.main()
