#!/usr/bin/env python3

from flask import Flask, render_template, jsonify, request, g, send_from_directory
import sqlite3
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

from node_summary import summarize_nodes
from coverage_areas import AREAS, contains, clipped_bounds
from system_health import host_health, reception_health

app = Flask(__name__)
app.config['RADIO_CONTROLS_ENABLED'] = @@ENABLE_RADIO_CONTROLS@@
@app.before_request
def optional_features():
    if request.path.startswith(('/api/secondary-control','/api/lcd-control','/api/pki/')):
        return jsonify(error='This hardware integration is unavailable in the portable distribution'), 501
    if request.path.startswith(('/api/msp-ingestors','/api/msp-heard-by')):
        return jsonify(error='External mesh lookup is disabled in the portable distribution'), 501
    if not app.config['RADIO_CONTROLS_ENABLED'] and request.path.startswith('/api/node-control/') and request.method=='POST' and not request.path.endswith(('/unlock','/lock')):
        return jsonify(error='Enable radio controls in the local configuration first'), 403


DB = Path("@@DATA_DIR@@/mesh.db")

@app.get('/install')
def install_app():
    return render_template('install.html')

@app.get('/service-worker.js')
def service_worker():
    response=send_from_directory(app.static_folder, 'service-worker.js')
    response.headers['Cache-Control']='no-cache'
    return response



def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    g.setdefault('database_connections', []).append(conn)
    return conn


def nowutc():
    return datetime.now(timezone.utc)


def startup_windows(conn):
    rows = conn.execute("""
        SELECT event_time,event_type
        FROM collector_events
        WHERE event_type IN ('CONNECTED','NODE_SNAPSHOT')
        ORDER BY event_id
    """).fetchall()

    windows = []
    start = None

    for r in rows:
        if r["event_type"] == "CONNECTED":
            start = r["event_time"]
        elif r["event_type"] == "NODE_SNAPSHOT" and start:
            windows.append((start, r["event_time"]))
            start = None

    return windows


def startup_filter(windows, alias="p"):
    if not windows:
        return "1=1", []

    parts = []
    params = []

    for start, end in windows:
        parts.append(
            f"NOT ({alias}.collector_time >= ? "
            f"AND {alias}.collector_time <= ?)"
        )
        params.extend([start, end])

    return " AND ".join(parts), params


def clamp_hours(value):
    try:
        value = int(value)
    except Exception:
        value = 24

    return max(1, min(value, 720))


def health_score(row):
    packets = row["packets"] or 0

    if packets == 0:
        return None

    direct_pct = (
        (row["direct_packets"] or 0) / packets
    ) * 100

    snr = row["avg_snr"]
    hops = row["avg_hops"]

    sample_score = min(20, packets * 2)
    direct_score = 30 * direct_pct / 100

    if snr is None:
        snr_score = 0
    else:
        snr_score = max(
            0,
            min(40, (snr + 12) * 2)
        )

    if hops is None:
        hop_score = 0
    else:
        hop_score = max(
            0,
            10 - hops * 1.5
        )

    return round(min(
        100,
        sample_score +
        direct_score +
        snr_score +
        hop_score
    ))


def health_label(score):
    if score is None:
        return "NO DATA"
    if score >= 85:
        return "STRONG"
    if score >= 70:
        return "HEALTHY"
    if score >= 50:
        return "MARGINAL"
    return "EDGE"


def rf_quality_label(snr):
    if snr is None: return "NO DATA"
    if snr >= 5: return "EXCELLENT"
    if snr >= 0: return "GOOD"
    if snr >= -7: return "MARGINAL"
    return "EDGE"


@app.route("/")
def index():
    return render_template("index.html")


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

@app.route("/api/summary")
def summary():

    hours = clamp_hours(
        request.args.get("hours", 24)
    )

    conn = db()

    now = nowutc()
    start = now - timedelta(hours=hours)

    windows = startup_windows(conn)
    filt, fparams = startup_filter(windows)

    result = summarize_nodes(conn, start.isoformat(), filt, fparams, now)

    total_packets = conn.execute("""
        SELECT COUNT(*)
        FROM packets
    """).fetchone()[0]

    remote_totals = conn.execute("""SELECT COUNT(*) AS packets, MAX(p.collector_time) AS last_packet FROM packets p WHERE p.from_num IS NOT NULL AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END AND COALESCE(p.observation_type,'LIVE')='LIVE'""").fetchone()

    total_nodes = conn.execute("""
        SELECT COUNT(*)
        FROM nodes
    """).fetchone()[0]

    last_packet = conn.execute("""
        SELECT MAX(collector_time)
        FROM packets
    """).fetchone()[0]

    events = [
        dict(r)
        for r in conn.execute("""
            SELECT
                event_id,
                event_time,
                event_type,
                message
            FROM collector_events
            ORDER BY event_id DESC
            LIMIT 12
        """).fetchall()
    ]

    conn.close()

    return jsonify({
        "generated": now.isoformat(),
        "hours": hours,
        "packets_total": total_packets,
        "packets_remote_total": remote_totals["packets"],
        "last_remote_packet": remote_totals["last_packet"],
        "nodes_total": total_nodes,
        "last_packet": last_packet,
        "nodes": result,
        "events": events
    })


# ------------------------------------------------------------
# Node detail
# ------------------------------------------------------------

@app.route("/api/node")
def node_detail():

    node = request.args.get(
        "node", ""
    ).strip()

    hours = clamp_hours(
        request.args.get("hours", 24)
    )

    if not node:
        return jsonify(
            {"error": "node required"}
        ), 400

    conn = db()

    now = nowutc()
    start = now - timedelta(hours=hours)

    windows = startup_windows(conn)
    filt, fparams = startup_filter(windows)

    info = conn.execute("""
        SELECT
            n.*,

            s.display_name AS site_name,
            s.latitude AS installed_latitude,
            s.longitude AS installed_longitude,
            s.agl_ft,
            s.msl_ft,
            s.hardware AS site_hardware,
            s.antenna,
            s.antenna_gain_dbi,
            s.ownership,
            s.notes AS site_notes

        FROM nodes n

        LEFT JOIN sites s
            ON s.node_long_name=n.long_name

        WHERE n.long_name=?
           OR n.node_id=?

        LIMIT 1
    """, (node, node)).fetchone()

    summaries = summarize_nodes(conn, start.isoformat(), filt, fparams, now)
    identity = info['node_num'] if info else None
    d = next((r for r in summaries if
              (identity is not None and r['from_num'] == identity) or r['node_id'] == node),
             dict(packets=0, rf_packets=0, signal_samples=0, known_hop_packets=0,
                  unknown_hop_packets=0, direct_packets=0, direct_pct=None,
                  avg_snr=None, min_snr=None, max_snr=None, avg_rssi=None,
                  min_rssi=None, max_rssi=None, avg_hops=None, last_seen=None,
                  score=None, health='NOT SCORED', activity='No updates in window', is_local=False))

    conn.close()

    return jsonify({
        "node": dict(info) if info else None,
        "stats": d,
        "hours": hours
    })


# ------------------------------------------------------------
# History
# ------------------------------------------------------------

@app.route("/api/history")
def history():

    node = request.args.get(
        "node", ""
    ).strip()

    hours = clamp_hours(
        request.args.get("hours", 24)
    )

    if not node:
        return jsonify([])

    conn = db()

    start = (
        nowutc() -
        timedelta(hours=hours)
    )

    windows = startup_windows(conn)
    filt, fparams = startup_filter(windows)

    rows = conn.execute(f"""
        SELECT
            p.collector_time,
            p.rx_snr,
            p.rx_rssi,
            p.hops_used

        FROM packets p

        LEFT JOIN nodes n
            ON p.from_num=n.node_num

        WHERE (
            n.long_name=?
            OR n.node_id=?
            OR p.from_id=?
        )

        AND p.collector_time >= ?
        AND ({filt})

        ORDER BY p.collector_time
    """, [
        node,
        node,
        node,
        start.isoformat()
    ] + fparams).fetchall()

    conn.close()

    return jsonify(
        [dict(r) for r in rows]
    )


# ------------------------------------------------------------
# Telemetry
# ------------------------------------------------------------

def first_radio_heard(conn, node_num):
    # Only retained local radio receipts qualify; metadata/snapshots do not.
    return conn.execute("""SELECT MIN(collector_time) FROM packets
        WHERE from_num=? AND COALESCE(observation_type,'LIVE')='LIVE'
        AND COALESCE(transport,'') NOT IN ('TRANSPORT_MQTT','TRANSPORT_INTERNAL')
        AND (rx_snr IS NOT NULL OR rx_rssi IS NOT NULL)
        AND CASE WHEN json_valid(raw_json) THEN COALESCE(json_extract(raw_json,'$.viaMqtt'),0) ELSE 0 END=0
        AND COALESCE(from_id,printf('!%08x',from_num)) !=
            COALESCE(json_extract(CASE WHEN json_valid(raw_json) THEN raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')
        """, (node_num,)).fetchone()[0]

@app.route("/api/telemetry")
def telemetry():

    node = request.args.get(
        "node", ""
    ).strip()

    if not node:
        return jsonify({
            "error": "node required"
        }), 400

    conn = db()

    # Resolve node identity first.
    identity = conn.execute("""
        SELECT
            n.node_num,
            n.node_id,
            COALESCE(s.latitude,n.latitude) AS latitude,
            COALESCE(s.longitude,n.longitude) AS longitude,
            CASE WHEN s.latitude IS NOT NULL AND s.longitude IS NOT NULL THEN 'installed' ELSE 'advertised' END AS location_source,
            n.long_name,
            n.short_name,
            n.hw_model,
            n.role,

            n.battery_level AS node_battery_level,
            n.voltage AS node_voltage,
            n.updated_at AS node_updated_at,

            s.display_name AS site_name,
            s.hardware AS site_hardware,
            s.agl_ft,
            s.msl_ft,
            s.antenna,
            s.antenna_gain_dbi,
            s.ownership,
            s.notes

        FROM nodes n

        LEFT JOIN sites s
            ON s.node_long_name=n.long_name

        WHERE n.long_name=?
           OR n.node_id=?

        LIMIT 1
    """, (node, node)).fetchone()

    # Latest packet that actually contains device telemetry.
    telem = conn.execute("""
        SELECT
            p.collector_time,
            p.rx_time,
            p.portnum,
            p.battery_level,
            p.voltage,
            p.channel_utilization,
            p.air_util_tx,
            p.uptime_seconds

        FROM packets p

        LEFT JOIN nodes n
            ON p.from_num=n.node_num

        WHERE (
            n.long_name=?
            OR n.node_id=?
            OR p.from_id=?
        )

        AND (
            p.battery_level IS NOT NULL
            OR p.voltage IS NOT NULL
            OR p.channel_utilization IS NOT NULL
            OR p.air_util_tx IS NOT NULL
            OR p.uptime_seconds IS NOT NULL
        )

        ORDER BY p.row_id DESC
        LIMIT 1
    """, (node, node, node)).fetchone()

    # Latest RF observation is deliberately separate from
    # telemetry. The newest telemetry packet does not
    # necessarily equal the newest received RF packet.
    rf = conn.execute("""
        SELECT
            p.collector_time,
            p.rx_snr,
            p.rx_rssi,
            p.hops_used,
            p.hop_start,
            p.hop_limit,
            p.portnum

        FROM packets p

        LEFT JOIN nodes n
            ON p.from_num=n.node_num

        WHERE (
            n.long_name=?
            OR n.node_id=?
            OR p.from_id=?
        )

        AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END
        AND COALESCE(p.observation_type,'LIVE')='LIVE'
        AND COALESCE(p.transport,'') NOT IN ('TRANSPORT_MQTT','TRANSPORT_INTERNAL')
        AND CASE WHEN json_valid(p.raw_json) THEN COALESCE(json_extract(p.raw_json,'$.viaMqtt'),0) ELSE 0 END=0
        AND (
            p.rx_snr IS NOT NULL
            OR p.rx_rssi IS NOT NULL
        )

        ORDER BY p.row_id DESC
        LIMIT 1
    """, (node, node, node)).fetchone()

    note = None

    if identity:
        note = conn.execute("""
            SELECT
                node_num,
                node_id,
                long_name,
                note,
                updated_at

            FROM node_notes

            WHERE node_num=?
               OR node_id=?
               OR long_name=?

            ORDER BY
                CASE
                    WHEN node_num=? THEN 0
                    WHEN node_id=? THEN 1
                    ELSE 2
                END

            LIMIT 1
        """, (
            identity["node_num"],
            identity["node_id"],
            identity["long_name"],
            identity["node_num"],
            identity["node_id"]
        )).fetchone()

    first_heard = first_radio_heard(conn, identity["node_num"]) if identity else None
    details = {}
    if identity:
        import json
        for key,port,variant in [('position','POSITION_APP','position'),('environment','TELEMETRY_APP','environmentMetrics')]:
            rows = conn.execute("""SELECT collector_time, raw_json FROM packets
                WHERE from_num=? AND portnum=? ORDER BY row_id DESC""",
                (identity['node_num'],port))
            for row in rows:
                try:
                    decoded = json.loads(row['raw_json'] or '{}').get('decoded',{})
                    value = decoded.get('position') if key=='position' else decoded.get('telemetry',{}).get(variant)
                    if isinstance(value,dict) and value:
                        details[key] = dict(received_at=row['collector_time'],values=value)
                        break
                except (ValueError,TypeError,AttributeError):
                    continue
    conn.close()

    return jsonify({
        "first_heard": first_heard,
        "details": details,
        "node":
            dict(identity)
            if identity else None,

        "telemetry":
            dict(telem)
            if telem else None,

        "rf":
            dict(rf)
            if rf else None,

        "note":
            dict(note)
            if note else None
    })



# ------------------------------------------------------------
# Node Notes
# ------------------------------------------------------------

@app.route(
    "/api/node-note",
    methods=["GET"]
)
def get_node_note():

    node = request.args.get(
        "node", ""
    ).strip()

    if not node:
        return jsonify({
            "error": "node required"
        }), 400

    conn = db()

    identity = conn.execute("""
        SELECT
            node_num,
            node_id,
            long_name

        FROM nodes

        WHERE long_name=?
           OR node_id=?

        LIMIT 1
    """, (node, node)).fetchone()

    if not identity:
        conn.close()

        return jsonify({
            "error": "node not found"
        }), 404

    row = conn.execute("""
        SELECT
            node_num,
            node_id,
            long_name,
            note,
            updated_at

        FROM node_notes

        WHERE node_num=?
           OR node_id=?
           OR long_name=?

        LIMIT 1
    """, (
        identity["node_num"],
        identity["node_id"],
        identity["long_name"]
    )).fetchone()

    conn.close()

    return jsonify({
        "node_num":
            identity["node_num"],

        "node_id":
            identity["node_id"],

        "long_name":
            identity["long_name"],

        "note":
            row["note"]
            if row else "",

        "updated_at":
            row["updated_at"]
            if row else None
    })


@app.route(
    "/api/node-note",
    methods=["POST"]
)
def save_node_note():

    data = request.get_json(
        silent=True
    ) or {}

    node = str(
        data.get("node", "")
    ).strip()

    note = str(
        data.get("note", "")
    )

    if not node:
        return jsonify({
            "ok": False,
            "error": "node required"
        }), 400

    # Small free-text notes only.
    note = note[:2000]

    conn = db()

    identity = conn.execute("""
        SELECT
            node_num,
            node_id,
            long_name

        FROM nodes

        WHERE long_name=?
           OR node_id=?

        LIMIT 1
    """, (node, node)).fetchone()

    if not identity:
        conn.close()

        return jsonify({
            "ok": False,
            "error": "node not found"
        }), 404

    timestamp = nowutc().isoformat()

    conn.execute("""
        INSERT INTO node_notes (
            node_num,
            node_id,
            long_name,
            note,
            updated_at
        )

        VALUES (?,?,?,?,?)

        ON CONFLICT(node_num)
        DO UPDATE SET
            node_id=excluded.node_id,
            long_name=excluded.long_name,
            note=excluded.note,
            updated_at=excluded.updated_at
    """, (
        identity["node_num"],
        identity["node_id"],
        identity["long_name"],
        note,
        timestamp
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "ok": True,
        "node_num":
            identity["node_num"],

        "node_id":
            identity["node_id"],

        "long_name":
            identity["long_name"],

        "note": note,

        "updated_at":
            timestamp
    })



# ------------------------------------------------------------
# Map
# ------------------------------------------------------------



# ============================================================
# Home area Coverage Survey Mode
# ============================================================

def _survey_init(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS coverage_surveys (
            survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            start_row_id INTEGER NOT NULL,
            end_row_id INTEGER,
            start_coverage REAL,
            end_coverage REAL,
            notes TEXT
        )
    """)

    columns = {r[1] for r in conn.execute('PRAGMA table_info(coverage_surveys)')}
    if 'area_id' not in columns:
        conn.execute("ALTER TABLE coverage_surveys ADD COLUMN area_id TEXT NOT NULL DEFAULT 'home'")
    conn.commit()


def _survey_active(conn):

    _survey_init(conn)

    return conn.execute("""
        SELECT *
        FROM coverage_surveys
        WHERE ended_at IS NULL
        ORDER BY survey_id DESC
        LIMIT 1
    """).fetchone()


def _survey_haversine(lat1, lon1, lat2, lon2):

    import math

    R = 3958.7613

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    aa = (
        math.sin(dp / 2) ** 2
        +
        math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return 2 * R * math.asin(math.sqrt(aa))


def _survey_probe_nums(conn):

    rows = conn.execute("""
        SELECT
            n.node_num,
            n.long_name,
            MIN(p.latitude) AS min_lat,
            MAX(p.latitude) AS max_lat,
            MIN(p.longitude) AS min_lon,
            MAX(p.longitude) AS max_lon
        FROM nodes n
        LEFT JOIN packets p
            ON p.from_num = n.node_num
        WHERE
            LOWER(TRIM(COALESCE(n.short_name,''))) LIKE '@@NODE_PREFIX_LOWER@@%'
        GROUP BY
            n.node_num,
            n.long_name
    """).fetchall()

    probes = set()

    for rr in rows:

        r = dict(rr)

        vals = (
            r["min_lat"],
            r["max_lat"],
            r["min_lon"],
            r["max_lon"]
        )

        if any(v is None for v in vals):
            continue

        span = _survey_haversine(
            float(r["min_lat"]),
            float(r["min_lon"]),
            float(r["max_lat"]),
            float(r["max_lon"])
        )

        if span >= 0.25:
            probes.add(r["node_num"])

    return probes


def _survey_metrics(conn, survey):

    if not survey:
        return None

    s = dict(survey)
    if s.get('area_id') == 'roaming':
        phone = app.extensions['survey_phone'].report(s['survey_id'])
        return dict(s, active=s['ended_at'] is None, area_name='Roaming survey',
                    routes=phone['routes'], phone=phone, traceroute_status=phone['status'],
                    gps_samples=phone['metrics']['unique_fixes'], distance_miles=phone['metrics']['reliable_distance_miles'],
                    probe_nodes=[r['node'] for r in phone['routes']],
                    contribution_note='Roaming survey: route and traceroutes across all areas. GPS tracks do not prove RF coverage. All retained companion records contribute to totals; display points are limited. GPS uncertainty and recording gaps are reported separately.')

    end_row = s["end_row_id"]

    if end_row is None:

        end_row = conn.execute("""
            SELECT COALESCE(MAX(row_id),0) AS x
            FROM packets
        """).fetchone()["x"]

    probes = _survey_probe_nums(conn)

    rows = conn.execute("""
        SELECT
            p.row_id,
            p.collector_time,
            p.from_num,
            COALESCE(
                n.long_name,
                p.from_id
            ) AS node,
            p.latitude,
            p.longitude,
            p.rx_snr,
            p.hops_used
        FROM packets p

        LEFT JOIN nodes n
            ON n.node_num = p.from_num

        WHERE
            p.row_id > ?
            AND p.row_id <= ?
            AND p.latitude IS NOT NULL
            AND p.longitude IS NOT NULL
            AND LOWER(TRIM(COALESCE(n.short_name,''))) LIKE '@@NODE_PREFIX_LOWER@@%'

        ORDER BY p.row_id
    """, (
        s["start_row_id"],
        end_row
    )).fetchall()

    rows = [
        dict(r)
        for r in rows
        if r["from_num"] in probes
    ]

    # --------------------------------------------------------
    # Actual point-to-point distance traveled
    # --------------------------------------------------------

    by_node = {}

    for r in rows:

        by_node.setdefault(
            r["from_num"],
            []
        ).append(r)

    distance = 0.0

    for points in by_node.values():

        previous = None

        for r in points:

            current = (
                float(r["latitude"]),
                float(r["longitude"])
            )

            if previous:

                d = _survey_haversine(
                    previous[0],
                    previous[1],
                    current[0],
                    current[1]
                )

                # Reject obvious GPS teleportation.
                if d <= 5.0:
                    distance += d

            previous = current

    # --------------------------------------------------------
    # Home area 1 mile grid
    # --------------------------------------------------------

    import math

    area_id = s.get('area_id', 'home')
    min_lat, max_lat, min_lon, max_lon = AREAS[area_id]['bounds']

    cell_miles = AREAS[area_id]['cell_miles']

    lat_step = cell_miles / 69.0

    lon_step = (
        cell_miles
        /
        (
            69.0
            *
            math.cos(
                math.radians(
                    (min_lat + max_lat) / 2
                )
            )
        )
    )

    buckets = {}

    for r in rows:

        lat = float(r["latitude"])
        lon = float(r["longitude"])

        if not contains(AREAS[area_id], lat, lon):
            continue

        if not (
            min_lat <= lat <= max_lat
            and
            min_lon <= lon <= max_lon
        ):
            continue

        ix = int(
            (lon - min_lon) // lon_step
        )

        iy = int(
            (lat - min_lat) // lat_step
        )

        key = (ix, iy)

        c = buckets.setdefault(
            key,
            {
                "samples": 0,
                "snr": [],
                "hops": []
            }
        )

        c["samples"] += 1

        if r["rx_snr"] is not None:
            c["snr"].append(
                float(r["rx_snr"])
            )

        if r["hops_used"] is not None:
            c["hops"].append(
                int(r["hops_used"])
            )

    proven = 0

    for c in buckets.values():

        avg_snr = (
            sum(c["snr"]) / len(c["snr"])
            if c["snr"]
            else None
        )

        avg_hops = (
            sum(c["hops"]) / len(c["hops"])
            if c["hops"]
            else None
        )

        if (
            c["samples"] >= 3
            and
            avg_snr is not None
            and
            avg_snr >= -12
            and
            (
                avg_hops is None
                or
                avg_hops <= 4
            )
        ):
            proven += 1

    from survey_report import enrich
    report = enrich(conn, s, rows, buckets,
                    (min_lat, max_lat, min_lon, max_lon), (lat_step, lon_step),
                    _survey_haversine, AREAS[area_id])
    phone = app.extensions['survey_phone'].report(s['survey_id'])
    report['phone'] = phone
    report['routes'] += phone['routes']
    report['traceroute_status'] = phone['status']
    return {
        **report,
        'area_id': area_id,
        'cell_miles': cell_miles,
        'area_name': AREAS[area_id]['name'],
        "survey_id":
            s["survey_id"],

        "started_at":
            s["started_at"],

        "ended_at":
            s["ended_at"],

        "active":
            s["ended_at"] is None,

        "gps_samples":
            len(rows),

        "distance_miles":
            distance,

        "cells_visited":
            len(buckets),

        "cells_proven_this_survey":
            proven,

        "probe_nodes":
            sorted({
                r["node"]
                for r in rows
                if r["node"]
            }),

        "start_coverage":
            s["start_coverage"],

        "end_coverage":
            s["end_coverage"]
    }


@app.route(
    "/api/coverage-survey",
    methods=["GET","POST"]
)
def coverage_survey():

    from datetime import datetime, timezone

    conn = db()

    _survey_init(conn)

    if request.method == "POST":

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        action = str(
            data.get(
                "action",
                ""
            )
        ).strip().lower()

        if action == "start":
            area_id = data.get('area_id', 'roaming')
            if area_id != 'roaming' and area_id not in AREAS:
                return jsonify(ok=False, error='Unknown coverage area'), 400


            if _survey_active(conn):

                return jsonify({
                    "ok": False,
                    "error":
                        "A survey is already active"
                }), 409

            row_id = conn.execute("""
                SELECT
                    COALESCE(
                        MAX(row_id),
                        0
                    ) AS x
                FROM packets
            """).fetchone()["x"]

            now = datetime.now(
                timezone.utc
            ).isoformat()

            conn.execute("""
                INSERT INTO coverage_surveys (
                    started_at,
                    start_row_id, area_id
                )
                VALUES (?,?,?)
            """, (
                now,
                row_id, area_id
            ))

            conn.commit()

        elif action == "stop":

            current = _survey_active(conn)

            if not current:

                return jsonify({
                    "ok": False,
                    "error":
                        "No survey is active"
                }), 409

            row_id = conn.execute("""
                SELECT
                    COALESCE(
                        MAX(row_id),
                        0
                    ) AS x
                FROM packets
            """).fetchone()["x"]

            now = datetime.now(
                timezone.utc
            ).isoformat()

            conn.execute("""
                UPDATE coverage_surveys

                SET
                    ended_at = ?,
                    end_row_id = ?

                WHERE survey_id = ?
            """, (
                now,
                row_id,
                current["survey_id"]
            ))

            conn.commit()

        else:

            return jsonify({
                "ok": False,
                "error":
                    "action must be start or stop"
            }), 400

    active = _survey_active(conn)

    current = (
        _survey_metrics(
            conn,
            active
        )
        if active
        else None
    )

    recent_rows = conn.execute("""
        SELECT *
        FROM coverage_surveys

        WHERE ended_at IS NOT NULL

        ORDER BY survey_id DESC

        LIMIT 5
    """).fetchall()

    recent = [
        _survey_metrics(
            conn,
            r
        )
        for r in recent_rows
    ]

    return jsonify({
        "ok": True,
        "active": current,
        "recent": recent
    })


@app.route("/api/coverage")
def coverage():
    import math
    from datetime import datetime, timezone, timedelta
    conn=db()
    area_id=request.args.get('area','home')
    if area_id not in AREAS:return jsonify(error='Unknown coverage area'),400
    area=AREAS[area_id]
    min_lat,max_lat,min_lon,max_lon=area['bounds']
    cell_miles=area['cell_miles']
    lat_step=cell_miles/69.0
    lon_step=cell_miles/(69.0*math.cos(math.radians((min_lat+max_lat)/2)))
    stale_before=datetime.now(timezone.utc)-timedelta(days=30)
    # --------------------------------------------------------
    # Automatically classify all Local* nodes.
    #
    # A local node becomes a coverage survey probe only after its
    # recorded GPS positions span at least 0.25 statute mile.
    # This classification identifies mobile survey probes for reporting.
    # Map coverage accepts observations from all fixed and mobile nodes.
    # --------------------------------------------------------

    owned_rows=conn.execute("""
      SELECT
        n.node_num,
        n.long_name,
        MIN(p.latitude) AS min_lat,
        MAX(p.latitude) AS max_lat,
        MIN(p.longitude) AS min_lon,
        MAX(p.longitude) AS max_lon,
        COUNT(CASE
          WHEN p.latitude IS NOT NULL
           AND p.longitude IS NOT NULL
          THEN 1 END) AS position_samples
      FROM nodes n
      LEFT JOIN packets p ON p.from_num=n.node_num
      WHERE LOWER(TRIM(COALESCE(n.short_name,''))) LIKE '@@NODE_PREFIX_LOWER@@%'
      GROUP BY n.node_num,n.long_name
      ORDER BY n.long_name
    """).fetchall()

    owned_nodes=[]
    probe_nums=set()

    def haversine_miles(lat1,lon1,lat2,lon2):
      R=3958.7613
      p1=math.radians(lat1)
      p2=math.radians(lat2)
      dp=math.radians(lat2-lat1)
      dl=math.radians(lon2-lon1)
      aa=(math.sin(dp/2)**2 +
          math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2)
      return 2*R*math.asin(math.sqrt(aa))

    for rr in owned_rows:
      r=dict(rr)
      span=0.0

      if (r['min_lat'] is not None and
          r['max_lat'] is not None and
          r['min_lon'] is not None and
          r['max_lon'] is not None):

        span=haversine_miles(
          float(r['min_lat']),
          float(r['min_lon']),
          float(r['max_lat']),
          float(r['max_lon'])
        )

      is_probe=span >= 0.25

      if is_probe:
        probe_nums.add(r['node_num'])

      owned_nodes.append({
        'node_num':r['node_num'],
        'node':r['long_name'],
        'position_samples':r['position_samples'] or 0,
        'movement_miles':span,
        'survey_probe':is_probe
      })

    rows=conn.execute("""
      SELECT
        p.collector_time,
        p.from_num,
        COALESCE(n.long_name,p.from_id) node,
        p.latitude,
        p.longitude,
        p.rx_snr,
        p.rx_rssi,
        p.hops_used
      FROM packets p
      LEFT JOIN nodes n ON n.node_num=p.from_num
      WHERE p.latitude BETWEEN ? AND ?
        AND p.longitude BETWEEN ? AND ?
        -- All nodes with recorded positions can contribute coverage evidence.
      ORDER BY p.row_id
    """,(min_lat,max_lat,min_lon,max_lon)).fetchall()

    # Fixed and mobile nodes both contribute their recorded observations.
    # Movement classification above describes survey probes only; it does not
    # exclude stationary nodes from the map's coverage evidence.

    rows=[r for r in rows if contains(area,r['latitude'],r['longitude'])]
    from coverage_age import accumulate
    obs,old_obs=accumulate(rows,min_lat,min_lon,lat_step,lon_step,stale_before)
    current_evidence=sum(c['samples'] for c in obs.values())
    stale_evidence=sum(c['samples'] for c in old_obs.values())
    nx=math.ceil((max_lon-min_lon)/lon_step); ny=math.ceil((max_lat-min_lat)/lat_step); counts={'PROVEN':0,'MARGINAL':0,'UNTESTED':0,'STALE':0}; cells=[]
    for iy in range(ny):
     for ix in range(nx):
      south=min_lat+iy*lat_step; north=min(max_lat,south+lat_step); west=min_lon+ix*lon_step; east=min(max_lon,west+lon_step); recent=obs.get((ix,iy)); historical=old_obs.get((ix,iy)); c=recent or historical; status='UNTESTED'
      display_bounds=clipped_bounds(area,south,north,west,east)
      if not display_bounds:continue
      samples=0; nodes=[]; avg_snr=best_snr=avg_rssi=avg_hops=direct_pct=last=None
      if c:
       samples=c['samples']; nodes=sorted(c['nodes']); last=c['last']; avg_snr=sum(c['snr'])/len(c['snr']) if c['snr'] else None; best_snr=max(c['snr']) if c['snr'] else None
       avg_rssi=sum(c['rssi'])/len(c['rssi']) if c['rssi'] else None; avg_hops=sum(c['hops'])/len(c['hops']) if c['hops'] else None; direct_pct=100*c['direct']/len(c['hops']) if c['hops'] else None
       if recent is None: status='STALE'
       elif samples>=3 and avg_snr is not None and avg_snr>=-12 and (avg_hops is None or avg_hops<=4): status='PROVEN'
       else: status='MARGINAL'
      counts[status]+=1; cells.append({'id':f'{ix}:{iy}','status':status,'bounds':[[south,west],[north,east]],'display_bounds':display_bounds,'samples':samples,'current_samples':recent['samples'] if recent else 0,'stale_samples':historical['samples'] if historical else 0,'nodes':nodes,'avg_snr':avg_snr,'best_snr':best_snr,'avg_rssi':avg_rssi,'avg_hops':avg_hops,'direct_pct':direct_pct,'last_seen':last})
    total=len(cells); tested=counts['PROVEN']+counts['MARGINAL']; pct=100*counts['PROVEN']/total if total else 0
    return jsonify({'regions':[dict(id=k,**v) for k,v in AREAS.items()], 'accent':area['accent'], 'tagline':area['tagline'], 'name':area['name'], 'area_id':area_id, 'bounds':[[min_lat,min_lon],[max_lat,max_lon]],'goal_pct':90.0,'cell_miles':cell_miles,'total_cells':total,'counts':counts,'demonstrated_pct':pct,'tested_pct':100*tested/total if total else 0,'target_remaining':max(0,90-pct),'evidence_packets':current_evidence,'stale_evidence_packets':stale_evidence,'total_evidence_packets':len(rows),'stale_after_days':30,'cutoff_utc':stale_before.isoformat(),
      'owned_nodes':len(owned_nodes),
      'survey_probes':len(probe_nums),
      'probe_nodes':owned_nodes,
      'movement_threshold_miles':0.25,
      'fixed_nodes_count':True,
      'cells':cells})

@app.route("/api/map")
def map_nodes():

    conn = db()

    rows = conn.execute("""
        SELECT
            n.node_num,
            n.node_id,
            n.long_name,
            n.short_name,
            n.hw_model,
            n.role,

            n.latitude AS advertised_latitude,
            n.longitude AS advertised_longitude,
            n.altitude AS advertised_altitude,

            s.display_name AS site_name,

            COALESCE(
                s.latitude,
                n.latitude
            ) AS latitude,

            COALESCE(
                s.longitude,
                n.longitude
            ) AS longitude,

            s.agl_ft,
            s.msl_ft,
            s.hardware AS site_hardware,
            s.antenna,
            s.antenna_gain_dbi,
            s.ownership,
            s.notes,

            CASE
                WHEN s.latitude IS NOT NULL
                THEN 'installed'
                ELSE 'advertised'
            END AS location_source,

            (
                SELECT p.rx_snr
                FROM packets p
                WHERE p.from_num=n.node_num
                  AND p.rx_snr IS NOT NULL
                ORDER BY p.row_id DESC
                LIMIT 1
            ) AS last_snr,

            (
                SELECT p.rx_rssi
                FROM packets p
                WHERE p.from_num=n.node_num
                  AND p.rx_rssi IS NOT NULL
                ORDER BY p.row_id DESC
                LIMIT 1
            ) AS last_rssi,

            (
                SELECT p.hops_used
                FROM packets p
                WHERE p.from_num=n.node_num
                ORDER BY p.row_id DESC
                LIMIT 1
            ) AS last_hops,

            (
                SELECT p.collector_time
                FROM packets p
                WHERE p.from_num=n.node_num
                ORDER BY p.row_id DESC
                LIMIT 1
            ) AS last_observed

        FROM nodes n

        LEFT JOIN sites s
            ON s.node_long_name=n.long_name

        WHERE
            COALESCE(
                s.latitude,
                n.latitude
            ) BETWEEN -90 AND 90

        AND
            COALESCE(
                s.longitude,
                n.longitude
            ) BETWEEN -180 AND 180

        AND NOT (
            COALESCE(
                s.latitude,
                n.latitude
            ) = 0

            AND

            COALESCE(
                s.longitude,
                n.longitude
            ) = 0
        )

        ORDER BY
            COALESCE(
                s.display_name,
                n.long_name,
                n.node_id
            )
    """).fetchall()

    result = [
        dict(r) for r in rows
    ]

    represented = {
        r["site_name"]
        for r in rows
        if r["site_name"]
    }

    sites = conn.execute("""
        SELECT *
        FROM sites
        ORDER BY display_name
    """).fetchall()

    for s in sites:

        if s["display_name"] in represented:
            continue

        result.append({
            "node_num": None,
            "node_id": None,
            "long_name": s["node_long_name"],
            "short_name": None,
            "hw_model": None,
            "role": None,

            "advertised_latitude": None,
            "advertised_longitude": None,
            "advertised_altitude": None,

            "site_name": s["display_name"],

            "latitude": s["latitude"],
            "longitude": s["longitude"],

            "agl_ft": s["agl_ft"],
            "msl_ft": s["msl_ft"],

            "site_hardware": s["hardware"],
            "antenna": s["antenna"],
            "antenna_gain_dbi":
                s["antenna_gain_dbi"],

            "ownership": s["ownership"],
            "notes": s["notes"],

            "location_source": "installed",

            "last_snr": None,
            "last_rssi": None,
            "last_hops": None,
            "last_observed": None
        })

    conn.close()

    return jsonify(result)


# ------------------------------------------------------------
# Events
# ------------------------------------------------------------

@app.route("/api/events")
def events():

    hours = clamp_hours(
        request.args.get("hours", 24)
    )

    conn = db()

    start = (
        nowutc() -
        timedelta(hours=hours)
    )

    rows = conn.execute("""
        SELECT
            event_id,
            event_time,
            event_type,
            message

        FROM collector_events

        WHERE event_time >= ?

        ORDER BY event_id
    """, (
        start.isoformat(),
    )).fetchall()

    conn.close()

    return jsonify(
        [dict(r) for r in rows]
    )


@app.route(
    "/api/events",
    methods=["POST"]
)
def add_event():

    data = request.get_json(
        silent=True
    ) or {}

    message = str(
        data.get("message", "")
    ).strip()

    event_type = str(
        data.get(
            "event_type",
            "USER_EVENT"
        )
    ).strip().upper()

    if not message:
        return jsonify({
            "ok": False,
            "error": "Event description required"
        }), 400

    # Keep arbitrary web input small.
    message = message[:500]
    event_type = event_type[:40]

    conn = db()

    timestamp = nowutc().isoformat()

    cur = conn.execute("""
        INSERT INTO collector_events (
            event_time,
            event_type,
            message
        )

        VALUES (?,?,?)
    """, (
        timestamp,
        event_type,
        message
    ))

    conn.commit()

    event_id = cur.lastrowid

    conn.close()

    return jsonify({
        "ok": True,
        "event_id": event_id,
        "event_time": timestamp,
        "event_type": event_type,
        "message": message
    })


# ------------------------------------------------------------
# NOC v2: records, recent activity, system, telemetry history
# ------------------------------------------------------------

@app.route("/api/noc")
def noc():
    hours = clamp_hours(request.args.get("hours", 24))
    conn = db(); start = nowutc() - timedelta(hours=hours)
    windows=startup_windows(conn); filt,fp=startup_filter(windows)
    params=[start.isoformat()]+fp
    base=f"""FROM packets p LEFT JOIN nodes n ON p.from_num=n.node_num
             WHERE p.collector_time >= ? AND p.observation_type='LIVE' AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END AND ({filt})"""
    rows=conn.execute(f"""SELECT p.from_num,COALESCE(NULLIF(TRIM(n.long_name),''),NULLIF(p.from_id,''),CASE WHEN p.from_num IS NOT NULL THEN printf('!%08x',p.from_num) ELSE 'Unknown node' END) node,
        COUNT(*) packets,AVG(p.rx_snr) avg_snr,MIN(p.rx_snr) worst_snr,MAX(p.rx_snr) best_snr,
        MAX(p.hops_used) max_hops,AVG(p.hops_used) avg_hops,
        SUM(CASE WHEN p.hops_used=0 THEN 1 ELSE 0 END) direct_packets,
        MAX(p.collector_time) last_seen FROM packets p LEFT JOIN nodes n ON p.from_num=n.node_num
        WHERE p.collector_time >= ? AND p.observation_type='LIVE' AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END AND ({filt}) GROUP BY p.from_num""",params).fetchall()
    rr=[dict(x) for x in rows]
    for x in rr:
        x['rf_quality']=rf_quality_label(x['avg_snr'])
        x['direct_pct']=round((x['direct_packets'] or 0)/(x['packets'] or 1)*100,1)
    def pick(key,rev=True,nonnull=True):
        q=[x for x in rr if (x.get(key) is not None or not nonnull)]
        return (sorted(q,key=lambda x:x.get(key) if x.get(key) is not None else -1e99,reverse=rev)[0] if q else None)
    recent=[dict(x) for x in conn.execute(f"""SELECT p.collector_time,COALESCE(NULLIF(TRIM(n.long_name),''),NULLIF(p.from_id,''),CASE WHEN p.from_num IS NOT NULL THEN printf('!%08x',p.from_num) ELSE 'Unknown node' END) node,
        p.portnum,p.rx_snr,p.rx_rssi,p.hops_used,p.battery_level,p.voltage,
        p.from_num,n.short_name,n.hw_model,n.role,
        COALESCE(s.latitude,n.latitude,p.latitude) distance_latitude, COALESCE(s.longitude,n.longitude,p.longitude) distance_longitude,
        COALESCE(NULLIF(p.from_id,''),printf('!%08x',p.from_num)) node_id
        FROM packets p LEFT JOIN nodes n ON p.from_num=n.node_num LEFT JOIN sites s ON s.node_long_name=n.long_name
        WHERE p.collector_time >= ? AND p.from_num IS NOT NULL AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END AND COALESCE(p.observation_type,'LIVE')='LIVE' AND ({filt}) ORDER BY p.row_id DESC LIMIT 200""",params).fetchall()]
    window_activity = {r['from_num']:r for r in rr}
    origin=conn.execute("SELECT COALESCE(s.latitude,n.latitude),COALESCE(s.longitude,n.longitude) FROM nodes n LEFT JOIN sites s ON s.node_long_name=n.long_name WHERE n.node_id=? LIMIT 1", ('@@RECEIVER_ID@@',)).fetchone()
    for packet in recent:
        lat=packet.pop('distance_latitude');lon=packet.pop('distance_longitude')
        def located(a,b):return isinstance(a,(int,float)) and isinstance(b,(int,float)) and -90<=a<=90 and -180<=b<=180 and (a,b)!=(0,0)
        packet['distance_miles']=_survey_haversine(origin[0],origin[1],lat,lon) if origin and located(*origin) and located(lat,lon) else None
        activity = window_activity.get(packet['from_num'], {})
        packet['window_packets'] = activity.get('packets', 0)
        packet['window_direct_pct'] = activity.get('direct_pct')
    first=conn.execute(f"""SELECT COALESCE(NULLIF(TRIM(n.long_name),''),NULLIF(p.from_id,''),CASE WHEN p.from_num IS NOT NULL THEN printf('!%08x',p.from_num) ELSE 'Unknown node' END) node,MIN(p.collector_time) first_seen
        FROM packets p LEFT JOIN nodes n ON p.from_num=n.node_num WHERE p.from_num IS NOT NULL AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END AND p.observation_type='LIVE'
        GROUP BY p.from_num HAVING MIN(p.collector_time) >= ? ORDER BY first_seen DESC LIMIT 1""",[start.isoformat()]).fetchone()
    # Build cards and progression from the same evidence. Do not attach a
    # mobile node's CURRENT advertised coordinates to a historical packet.
    # Old history tables remain untouched for audit/rollback.
    import math
    evidence = conn.execute(f"""
        SELECT p.row_id,p.packet_id,p.collector_time,p.rx_time,
               COALESCE(NULLIF(TRIM(n.long_name),''),NULLIF(p.from_id,''),
                        printf('!%08x',p.from_num)) AS node,
               COALESCE(NULLIF(p.from_id,''),printf('!%08x',p.from_num)) AS node_id,
               p.latitude,p.longitude,p.rx_snr,p.rx_rssi,p.hops_used,
               s.latitude AS site_latitude,s.longitude AS site_longitude
        FROM packets p LEFT JOIN nodes n ON n.node_num=p.from_num
        LEFT JOIN sites s ON s.node_long_name=n.long_name
        WHERE p.observation_type='LIVE' AND p.packet_id IS NOT NULL
          AND p.from_num IS NOT NULL AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END
          AND p.hops_used >= 0 AND p.rx_snr IS NOT NULL AND ({filt})
        ORDER BY p.collector_time,p.row_id
    """, fp).fetchall()
    candidates = []
    for row in evidence:
        q = dict(row)
        # Prefer the position carried by the packet. Fixed installed sites
        # provide an explicitly labelled fallback; current node positions do not.
        for source,lat,lon in (
            ('packet',q['latitude'],q['longitude']),
            ('installed',q.pop('site_latitude'),q.pop('site_longitude')),
        ):
            try:
                lat,lon = float(lat),float(lon)
            except (ValueError,TypeError):
                continue
            if not (math.isfinite(lat) and math.isfinite(lon)
                    and -90 <= lat <= 90 and -180 <= lon <= 180
                    and (lat != 0 or lon != 0)):
                continue
            p1,p2 = math.radians(@@HOME_LAT@@),math.radians(lat)
            a = (math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)
                 * math.sin(math.radians(lon-(@@HOME_LON@@))/2)**2)
            distance = 2*3958.7613*math.asin(math.sqrt(min(1,max(0,a))))
            if distance > 250:
                continue
            q.update(latitude=lat,longitude=lon,location_source=source,
                     distance_miles=distance)
            # Cached packets can arrive together. Display their radio receive
            # time when valid instead of pretending the import time was contact time.
            q['observed_at'] = q['collector_time']
            if q['rx_time']:
                try:
                    received = datetime.fromtimestamp(q['rx_time'],timezone.utc)
                    observed = datetime.fromisoformat(q['collector_time'])
                    if datetime(2020,1,1,tzinfo=timezone.utc) <= received <= observed + timedelta(minutes=5):
                        q['collector_time'] = received.isoformat()
                except (ValueError,OverflowError,OSError,TypeError):
                    pass
            candidates.append(q)
            break

    def progression(direct=False):
        records = []
        best = -1.0
        for q in sorted(candidates,key=lambda q:(q['collector_time'],q['row_id'])):
            if direct and q['hops_used'] != 0:
                continue
            if q['distance_miles'] > best + 1e-9:
                records.append(q)
                best = q['distance_miles']
        return list(reversed(records))

    record_history = progression(direct=True)
    reached_history = progression()
    furthest_direct = record_history[0] if record_history else None
    furthest_reached = reached_history[0] if reached_history else None


    db_bytes=DB.stat().st_size if DB.exists() else 0
    last=conn.execute("SELECT MAX(collector_time) FROM packets").fetchone()[0]
    conn.close()

    return jsonify({
      'hours':hours,
      'records':{
          'most_active':pick('packets'),
          'best_snr':pick('best_snr'),
          'weakest_decode':pick('worst_snr',False),
          'highest_hops':pick('max_hops'),
          'newest':dict(first) if first else None,
          'furthest_direct':furthest_direct,
          'furthest_reached':furthest_reached
      },
      'furthest_direct_history':record_history,
      'furthest_reached_history':reached_history,
      'recent':recent,
      'system':{
          'database_bytes':db_bytes,
          'host':host_health(DB.parent),
          'remote_nodes':len(rr),
          'remote_updates':sum(x['packets'] for x in rr),
          'last_packet':last,
          'generated':nowutc().isoformat()
      }
    })

@app.route("/api/telemetry-history")
def telemetry_history():
    node=request.args.get('node','').strip(); hours=clamp_hours(request.args.get('hours',168))
    if not node: return jsonify([])
    conn=db(); start=nowutc()-timedelta(hours=hours)
    rows=conn.execute("""SELECT p.collector_time,p.battery_level,p.voltage,p.channel_utilization,p.air_util_tx,p.uptime_seconds
      FROM packets p LEFT JOIN nodes n ON p.from_num=n.node_num
      WHERE (n.long_name=? OR n.node_id=? OR p.from_id=?) AND p.collector_time>=?
      AND (p.battery_level IS NOT NULL OR p.voltage IS NOT NULL)
      ORDER BY p.collector_time""",(node,node,node,start.isoformat())).fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

# ------------------------------------------------------------
# Mobile Access Mode
# ------------------------------------------------------------
MOBILE_STATE = Path("/run/meshcrap-mesh-mobile-access")
MOBILE_HELPER = "/usr/local/sbin/mesh-mobile-access"

def _mobile_helper(*args):
    cmd = [MOBILE_HELPER, *args]
    cmd = ["sudo", "-n", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15)

def mobile_access_state():
    until = None
    minutes = None

    try:
        for line in MOBILE_STATE.read_text().splitlines():
            key, _, value = line.partition("=")
            if key == "until":
                until = int(value)
            elif key == "minutes":
                minutes = int(value)
    except Exception:
        pass

    now = int(time.time())
    remaining = max(0, (until or 0) - now)

    try:
        collector_active = subprocess.run(
            ["systemctl","is-active","--quiet","mesh-collector.service"],
            timeout=5
        ).returncode == 0
    except Exception:
        collector_active = False

    mobile = bool(
        until and remaining > 0 and not collector_active
    )

    # Automatic dual-NIC gateway state
    auto = {}
    auto_state = Path("/run/meshcrap-mesh-auto-mobile")

    try:
        for line in auto_state.read_text().splitlines():
            key, _, value = line.partition("=")
            if key:
                auto[key] = value
    except Exception:
        pass

    mode = auto.get("mode", "ready")

    try:
        clients = int(auto.get("clients", "0"))
    except Exception:
        clients = 0

    try:
        resume_at = int(auto.get("resume_at", "0"))
    except Exception:
        resume_at = 0

    grace_remaining = max(0, resume_at - now)

    peer = auto.get("peer")
    if peer:
        # Stored form is normally ('127.0.0.1', 12345).
        import re
        m = re.search(r"([0-9]+(?:\\.[0-9]+){3})", peer)
        if m:
            peer = m.group(1)

    try:
        gateway_active = subprocess.run(
            ["systemctl","is-active","--quiet","receiver-gateway.service"],
            timeout=5
        ).returncode == 0
    except Exception:
        gateway_active = False

    return {
        "mobile_access": mobile,
        "collector_active": collector_active,
        "remaining_seconds": remaining if mobile else 0,
        "until_epoch": until if mobile else None,
        "minutes": minutes if mobile else None,

        "gateway_active": gateway_active,
        "gateway_mode": mode,
        "gateway_clients": clients,
        "phone_connected": clients > 0 or mode == "mobile",
        "phone_peer": peer,
        "grace_remaining": grace_remaining,

        "phone_host": "127.0.0.1",
        "phone_port": 4404,
        "upstream_source": "127.0.0.1",
        "receiver_host": "@@RADIO_HOST@@",
        "receiver_port": 4403
    }

@app.route("/api/mobile-access", methods=["GET","POST"])
def mobile_access():
    return jsonify(enabled=False,mode='collector',collector_active=True,
                   message='Host network switching is not part of the portable distribution')


@app.route("/api/rf-environment")
def rf_environment():
    import json
    from datetime import datetime, timezone, timedelta

    try:
        hours = max(1, min(720, int(request.args.get("hours", 24))))
    except Exception:
        hours = 24

    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    experiment = json.loads((DB.parent / "reports" / "lna-experiment.json").read_text())
    start = max(start, datetime.fromisoformat(experiment["start_utc"]))
    conn = db()

    rows = conn.execute("""
        SELECT row_id, collector_time, raw_json
        FROM packets
        WHERE from_id = '@@RECEIVER_ID@@'
          AND portnum = 'TELEMETRY_APP'
          AND raw_json LIKE '%localStats%'
          AND collector_time >= ?
        ORDER BY row_id
    """, (start.isoformat(),)).fetchall()

    points = []
    prev = None

    for rr in rows:
        r = dict(rr)
        try:
            j = json.loads(r["raw_json"])
            s = j.get("decoded", {}).get("telemetry", {}).get("localStats", {})
        except Exception:
            continue

        rx = s.get("numPacketsRx")
        bad = s.get("numPacketsRxBad")
        dupe = s.get("numRxDupe")
        tx = s.get("numPacketsTx")
        ch = s.get("channelUtilization")
        air = s.get("airUtilTx")

        p = {
            "time": r["collector_time"],
            "rx": rx,
            "bad": bad,
            "dupe": dupe,
            "tx": tx,
            "channel_utilization": ch,
            "air_util_tx": air,
            "rx_delta": None,
            "bad_delta": None,
            "dupe_delta": None,
            "bad_share_pct": None
        }

        if prev is not None:
            try:
                drx = int(rx) - int(prev["rx"])
                dbad = int(bad) - int(prev["bad"])
                ddup = int(dupe) - int(prev["dupe"])
                if drx >= 0 and dbad >= 0 and ddup >= 0:
                    p["rx_delta"] = drx
                    p["bad_delta"] = dbad
                    p["dupe_delta"] = ddup
                    denom = drx + dbad
                    if denom > 0:
                        p["bad_share_pct"] = 100.0 * dbad / denom
            except Exception:
                pass

        if rx is not None and bad is not None and dupe is not None:
            prev = {"rx": rx, "bad": bad, "dupe": dupe}

        points.append(p)

    valid_bad = [x["bad_share_pct"] for x in points if x["bad_share_pct"] is not None]
    valid_ch = [float(x["channel_utilization"]) for x in points if x["channel_utilization"] is not None]
    valid_air = [float(x["air_util_tx"]) for x in points if x["air_util_tx"] is not None]

    latest = points[-1] if points else None

    return jsonify({
        "hours": hours,
        "samples": len(points),
        "latest": latest,
        "avg_bad_share_pct": (sum(valid_bad) / len(valid_bad) if valid_bad else None),
        "avg_channel_utilization": (sum(valid_ch) / len(valid_ch) if valid_ch else None),
        "avg_air_util_tx": (sum(valid_air) / len(valid_air) if valid_air else None),
        "points": points
    })



# ============================================================
# RF HEALTH HOURLY
# ============================================================

@app.route("/api/rf-health-hourly")
def rf_health_hourly():
    import json
    import statistics
    from datetime import datetime, timezone, timedelta

    try:
        hours = int(request.args.get("hours", 24))
    except Exception:
        hours = 24

    hours = max(1, min(hours, 720))

    RECEIVER_ID = "@@RECEIVER_ID@@"

    experiment = json.loads((DB.parent / "reports" / "lna-experiment.json").read_text())
    experiment_start = datetime.fromisoformat(experiment["start_utc"])
    transitions = sorted((datetime.fromisoformat(x["time_utc"]), x["state"]) for x in experiment["transitions"])

    now = datetime.now(timezone.utc)
    start = max(experiment_start, now - timedelta(hours=hours))

    conn = db()

    rows = conn.execute("""
        SELECT
            collector_time,
            from_id,
            from_num,
            portnum,
            rx_snr,
            rx_rssi,
            hops_used,
            raw_json
        FROM packets
        WHERE observation_type='LIVE'
          AND collector_time >= ?
        ORDER BY collector_time
    """, (start.isoformat(),)).fetchall()

    pki_request_ids = set()
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='pki_jobs'").fetchone():
        pki_request_ids = {r[0] for r in conn.execute("SELECT packet_id FROM pki_jobs WHERE requested_at>=? AND packet_id IS NOT NULL", (start.timestamp()-3600,))}

    restart_hours = {
        datetime.fromisoformat(r[0]).replace(minute=0, second=0, microsecond=0)
        for r in conn.execute("SELECT event_time FROM collector_events WHERE event_type IN ('START','CONNECTED','STOP')")
    }
    conn.close()

    def parse_time(value):
        try:
            return datetime.fromisoformat(
                value.replace("Z","+00:00")
            )
        except Exception:
            return None

    def percentile(vals, p):
        vals = sorted(vals)

        if not vals:
            return None

        if len(vals) == 1:
            return vals[0]

        x = (len(vals)-1)*p
        lo = int(x)
        hi = min(lo+1, len(vals)-1)
        frac = x-lo

        return (
            vals[lo]*(1-frac)
            +
            vals[hi]*frac
        )

    from lna_experiment import gap_hours
    own_times = [parse_time(r["collector_time"]) for r in rows if r["from_id"] == RECEIVER_ID]
    missing_hours = gap_hours([t for t in own_times if t], start, now)
    buckets = {}

    def bucket_for(t):
        key = t.replace(
            minute=0,
            second=0,
            microsecond=0
        )

        if key not in buckets:
            buckets[key] = {
                "packets": 0,
                "nodes": set(),
                "direct_packets": 0,
                "direct_nodes": set(),
                "snr": [],
                "weak_packets": 0,
                "stats_samples": [],
                "observed_minutes": set()
            }

        return buckets[key]

    for rr in rows:
        r = dict(rr)

        t = parse_time(
            r["collector_time"]
        )

        if not t:
            continue

        b = bucket_for(t)

        # Receiver self traffic is emitted regularly and gives us
        # a practical indication that the collector was actually
        # connected during this minute.
        if r["from_id"] == RECEIVER_ID:
            b["observed_minutes"].add(
                t.replace(second=0,microsecond=0)
            )

        # Poll responses remain stored but must not inflate ordinary mesh reception.
        try:
            diagnostic_reply = json.loads(r["raw_json"] or '{}').get('decoded', {}).get('requestId') in pki_request_ids
        except (ValueError, TypeError):
            diagnostic_reply = False
        # Mesh reception metrics exclude Receiver self telemetry and known PKI poll replies.
        if r["from_id"] != RECEIVER_ID and not diagnostic_reply:

            b["packets"] += 1

            node = (
                r["from_id"]
                or str(r["from_num"])
            )

            if node:
                b["nodes"].add(node)

            if r["hops_used"] == 0:
                b["direct_packets"] += 1

                if node:
                    b["direct_nodes"].add(node)

            if r["rx_snr"] is not None:
                try:
                    snr = float(r["rx_snr"])
                    b["snr"].append(snr)

                    if snr <= -10:
                        b["weak_packets"] += 1

                except Exception:
                    pass

        # Receiver LocalStats
        if (
            r["from_id"] == RECEIVER_ID
            and
            r["portnum"] == "TELEMETRY_APP"
            and
            r["raw_json"]
        ):
            try:
                j = json.loads(
                    r["raw_json"]
                )

                ls = (
                    j.get("decoded",{})
                     .get("telemetry",{})
                     .get("localStats",{})
                )

                rx = ls.get("numPacketsRx")
                bad = ls.get("numPacketsRxBad")

                ch = ls.get(
                    "channelUtilization"
                )

                air = ls.get(
                    "airUtilTx"
                )

                if (
                    rx is not None
                    and
                    bad is not None
                ):
                    b["stats_samples"].append({
                        "time": t,
                        "rx": int(rx),
                        "bad": int(bad),
                        "channel": (
                            float(ch)
                            if ch is not None
                            else None
                        ),
                        "air": (
                            float(air)
                            if air is not None
                            else None
                        )
                    })

            except Exception:
                pass

    # Cumulative LocalStats deltas across
    # chronological samples.
    all_stats = []

    for key in sorted(buckets):
        all_stats.extend(
            buckets[key]["stats_samples"]
        )

    all_stats.sort(
        key=lambda x:x["time"]
    )

    stats_by_hour = {}
    previous = None

    for sample in all_stats:

        key = sample["time"].replace(
            minute=0,
            second=0,
            microsecond=0
        )

        x = stats_by_hour.setdefault(
            key,
            {
                "rx_delta": 0,
                "bad_delta": 0,
                "channel": [],
                "air": []
            }
        )

        if sample["channel"] is not None:
            x["channel"].append(
                sample["channel"]
            )

        if sample["air"] is not None:
            x["air"].append(
                sample["air"]
            )

        if previous is not None:
            drx = (
                sample["rx"]
                -
                previous["rx"]
            )

            dbad = (
                sample["bad"]
                -
                previous["bad"]
            )

            # Ignore counter reset/reboot.
            crossed_transition = any(previous["time"] < when <= sample["time"] for when, state in transitions)
            continuous_stats = not any(previous["time"] < h + timedelta(hours=1) and sample["time"] >= h for h in missing_hours)
            if drx >= 0 and dbad >= 0 and not crossed_transition and continuous_stats:
                x["rx_delta"] += drx
                x["bad_delta"] += dbad

        previous = sample

    first_hour = start.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    last_hour = now.replace(
        minute=0,
        second=0,
        microsecond=0
    )

    timeline = []
    cur = first_hour

    while cur <= last_hour:

        b = buckets.get(cur)

        if b:
            snr = b["snr"]

            packets = b["packets"]
            nodes = len(b["nodes"])

            direct_packets = (
                b["direct_packets"]
            )

            direct_nodes = len(
                b["direct_nodes"]
            )

            weak_packets = (
                b["weak_packets"]
            )

            observed_minutes = len(
                b["observed_minutes"]
            )

            median_snr = (
                statistics.median(snr)
                if snr
                else None
            )

            p10_snr = percentile(
                snr,
                .10
            )

        else:
            packets = 0
            nodes = 0
            direct_packets = 0
            direct_nodes = 0
            weak_packets = 0
            observed_minutes = 0
            median_snr = None
            p10_snr = None

        st = stats_by_hour.get(
            cur,
            {}
        )

        rx_delta = st.get(
            "rx_delta",
            0
        )

        bad_delta = st.get(
            "bad_delta",
            0
        )

        denom = (
            rx_delta
            +
            bad_delta
        )

        bad_share = (
            100.0 * bad_delta / denom
            if denom > 0
            else None
        )

        channel = st.get(
            "channel",
            []
        )

        air = st.get(
            "air",
            []
        )

        hour_end = cur + timedelta(hours=1)

        states = [state for when, state in transitions if when <= cur]
        lna_state = states[-1] if states else "EXCLUDED"
        if any(cur < when < hour_end for when, state in transitions):
            lna_state = "MIXED"
        exclusion_reasons = []
        if cur < start:
            exclusion_reasons.append("Partial hour at selected window start")
        if cur < experiment_start:
            exclusion_reasons.append("Experiment start hour")
        if lna_state not in ("ON", "OFF"):
            exclusion_reasons.append("LNA transition hour")
        if cur in missing_hours:
            exclusion_reasons.append("Collection gap longer than 3 minutes")
        if cur in restart_hours:
            exclusion_reasons.append("Collector restart hour")
        if observed_minutes < 45:
            exclusion_reasons.append("Fewer than 45 observed minutes")
        if hour_end > now:
            exclusion_reasons.append("Hour not yet complete")

        observed_hours = (
            observed_minutes / 60.0
        )

        timeline.append({
            "hour": cur.isoformat(),

            "packets": packets,
            "unique_nodes": nodes,

            "direct_packets":
                direct_packets,

            "direct_nodes":
                direct_nodes,

            "median_snr":
                median_snr,

            "p10_snr":
                p10_snr,

            "weak_packets":
                weak_packets,

            "observed_minutes":
                observed_minutes,

            "packets_per_observed_hour":
                (
                    packets / observed_hours
                    if observed_hours > 0
                    else None
                ),

            "direct_per_observed_hour":
                (
                    direct_packets / observed_hours
                    if observed_hours > 0
                    else None
                ),

            "rx_bad_share_pct":
                bad_share,

            "channel_utilization":
                (
                    sum(channel)/len(channel)
                    if channel
                    else None
                ),

            "air_util_tx":
                (
                    sum(air)/len(air)
                    if air
                    else None
                ),

            "comparison_eligible": not exclusion_reasons,
            "exclusion_reasons": exclusion_reasons,
            "lna_state":
                lna_state
        })

        cur += timedelta(hours=1)

    return jsonify({
        "comparison": "lna",
        "experiment_start": experiment_start.isoformat(),
        "fixed_setup": experiment["fixed_setup"],
        "current_lna_state": transitions[-1][1],
        "hours": hours,
        "generated":
            now.isoformat(),
        "timeline":
            timeline
    })



from health_cache import shared_health_check

@app.route("/api/self-test")
@shared_health_check(seconds=5)
def dashboard_self_test():
    import subprocess
    from datetime import datetime, timezone

    RECEIVER_ID = "@@RECEIVER_ID@@"
    RECEIVER_HOST = "@@RADIO_HOST@@"
    RECEIVER_PORT = 4403

    def service_active(name):
        try:
            return subprocess.run(
                ["systemctl","is-active","--quiet",name],
                timeout=2
            ).returncode == 0
        except Exception:
            return False

    def age_seconds(value):
        if not value:
            return None
        try:
            t = datetime.fromisoformat(
                value.replace("Z","+00:00")
            )
            return max(
                0.0,
                (datetime.now(timezone.utc)-t).total_seconds()
            )
        except Exception:
            return None

    result = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "status": "HEALTHY",
        "checks": {}
    }

    collector = service_active("mesh-collector.service")
    gateway = service_active("receiver-gateway.service")
    dashboard = service_active("mesh-dashboard.service")

    result["checks"]["collector_service"] = {
        "ok": collector,
        "value": "active" if collector else "inactive"
    }

    result["checks"]["gateway_service"] = {
        "ok": gateway,
        "value": "active" if gateway else "inactive"
    }

    result["checks"]["dashboard_service"] = {
        "ok": dashboard,
        "value": "active" if dashboard else "inactive"
    }

    conn = db()

    last = conn.execute("""
        SELECT collector_time
        FROM packets
        WHERE observation_type='LIVE'
        ORDER BY row_id DESC
        LIMIT 1
    """).fetchone()

    last_rf = conn.execute("""
        SELECT collector_time
        FROM packets
        WHERE observation_type='LIVE'
          AND from_id != ?
          AND (
                rx_snr IS NOT NULL
                OR rx_rssi IS NOT NULL
                OR hops_used IS NOT NULL
              )
        ORDER BY row_id DESC
        LIMIT 1
    """, (RECEIVER_ID,)).fetchone()

    conn.close()

    last_time = last[0] if last else None
    last_age = age_seconds(last_time)

    rf_time = last_rf[0] if last_rf else None
    rf_age = age_seconds(rf_time)

    db_ok = last_age is not None and last_age < 180
    recent_rf_ok = rf_age is not None and rf_age < 900

    result["checks"]["database_live"] = {
        "ok": db_ok,
        "last_packet": last_time,
        "age_seconds": round(last_age,1) if last_age is not None else None
    }

    result["checks"]["recent_rf"] = {
        "ok": recent_rf_ok,
        "last_packet": rf_time,
        "age_seconds": round(rf_age,1) if rf_age is not None else None
    }

    socket_established = False
    socket_owner = None

    try:
        ss = subprocess.run(
            ["ss","-tnp"],
            capture_output=True,
            text=True,
            timeout=3
        )

        import socket
        addresses = {info[4][0] for info in socket.getaddrinfo(RECEIVER_HOST, RECEIVER_PORT, type=socket.SOCK_STREAM)}
        targets = {f"{address}:{RECEIVER_PORT}" for address in addresses} | {f"[{address}]:{RECEIVER_PORT}" for address in addresses}

        for line in ss.stdout.splitlines():
            columns = line.split()
            if len(columns) < 5 or columns[0] != "ESTAB" or columns[4] not in targets:
                continue

            socket_established = True

            if "receiver_gateway" in line:
                socket_owner = "gateway"
            elif "python" in line:
                socket_owner = "collector-or-python"
            else:
                socket_owner = "other"

            break

    except Exception:
        pass

    result["checks"]["receiver_socket"] = {
        "ok": socket_established,
        "connected": socket_established,
        "owner": socket_owner,
        "target": f"{RECEIVER_HOST}:{RECEIVER_PORT}"
    }

    routes = {str(rule) for rule in app.url_map.iter_rules()}

    noc_ok = "/api/noc" in routes
    rf_health_ok = "/api/rf-health-hourly" in routes

    result["checks"]["noc_api"] = {
        "ok": noc_ok,
        "value": "registered" if noc_ok else "missing"
    }

    result["checks"]["rf_health_api"] = {
        "ok": rf_health_ok,
        "value": "registered" if rf_health_ok else "missing"
    }

    hard_checks = [
        collector,
        gateway,
        dashboard,
        db_ok,
        socket_established,
        noc_ok,
        rf_health_ok
    ]

    result.update(reception_health(hard_checks, rf_age))

    return jsonify(result)


from messages_view import register_messages
register_messages(app, DB)

from node_control_web import register_node_control
register_node_control(app)
from survey_phone import register_survey_phone
register_survey_phone(app)

from mf_feed_web import register_feed_status
register_feed_status(app)

from performance import register_performance
register_performance(app)

from debug_logs import register_debug_logs
register_debug_logs(app)

from lna_experiment import register_lna_experiment
register_lna_experiment(app, DB)

@app.route('/api/recovery-health')
def recovery_health():
    # Verify the HTTP worker and a real database read, without scanning history.
    conn = db()
    conn.execute('SELECT row_id FROM packets ORDER BY row_id DESC LIMIT 1').fetchone()
    return 'ok', 200, {'Content-Type':'text/plain', 'Cache-Control':'no-store'}


@app.get('/api/lcd-rf')
def lcd_rf():
    import re
    node=request.args.get('node','@@RECEIVER_ID@@')
    if not re.fullmatch(r'![0-9a-fA-F]{8}',node):return jsonify(error='Invalid node ID'),400
    number=int(node[1:],16)
    conn=db();start=(nowutc()-timedelta(hours=1)).isoformat()
    filt,params=startup_filter(startup_windows(conn))
    target='1=1' if number==@@RECEIVER_NUM@@ else 'p.from_num=?'
    args=[start]+params+([] if number==@@RECEIVER_NUM@@ else [number])
    row=conn.execute(f"""SELECT COUNT(*) packets,COUNT(DISTINCT p.from_num) nodes,
        AVG(p.rx_snr) avg_snr,COUNT(p.rx_snr) snr_samples,
        AVG(p.rx_rssi) avg_rssi,COUNT(p.rx_rssi) rssi_samples,
        SUM(CASE WHEN p.hops_used=0 THEN 1 ELSE 0 END) direct,
        SUM(CASE WHEN p.hops_used BETWEEN 0 AND 7 THEN 1 ELSE 0 END) known_hops,
        MAX(p.collector_time) last_rf
        FROM packets p WHERE p.collector_time>=? AND ({filt}) AND ({target})
        AND COALESCE(p.observation_type,'LIVE')='LIVE'
        AND p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE NULL END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE @@RECEIVER_NUM@@ END
        AND COALESCE(p.transport,'') NOT IN ('TRANSPORT_MQTT','TRANSPORT_INTERNAL')
        AND CASE WHEN json_valid(p.raw_json) THEN COALESCE(json_extract(p.raw_json,'$.viaMqtt'),0) ELSE 0 END=0
        AND (p.transport='TRANSPORT_LORA' OR p.rx_snr IS NOT NULL OR p.rx_rssi IS NOT NULL)
        """,args).fetchone()
    conn.close()
    result=dict(row);result.update(hours=1,node_id=node,scope='receiver' if number==@@RECEIVER_NUM@@ else 'node')
    result['direct']=result['direct'] or 0;result['known_hops']=result['known_hops'] or 0
    result['relayed']=result['known_hops']-result['direct'];result['unknown_hops']=result['packets']-result['known_hops']
    return jsonify(result)

@app.get('/api/lcd-nodes')
def lcd_nodes():
    conn = db()
    rows = conn.execute("""SELECT COALESCE(NULLIF(node_id,''),printf('!%08x',node_num)) node_id,
        short_name,long_name,hw_model,role FROM nodes
        WHERE node_num IS NOT NULL
        ORDER BY CASE WHEN node_num=@@RECEIVER_NUM@@ THEN 0 WHEN upper(short_name) LIKE '@@NODE_PREFIX@@%' THEN 1 ELSE 2 END,
        COALESCE(NULLIF(long_name,''),short_name,node_id) COLLATE NOCASE""").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.get('/lcd')
def lcd_carousel():
    return render_template('lcd-carousel.html')

from msp_ingestors import register_msp_ingestors
register_msp_ingestors(app)

from ask_questions import register_ask_questions
register_ask_questions(app, DB)

from lcd_control import register_lcd_control
register_lcd_control(app)

from lna_noise import register_lna_noise
register_lna_noise(app, DB)



from insights import register_insights
register_insights(app, DB, startup_windows, startup_filter)

from node_utilities import register_utilities
register_utilities(app, DB)

from hq_weather import register_weather, start_weather
register_weather(app)

from role_compare import register_role_compare
register_role_compare(app, DB, startup_windows, startup_filter)

from heywhatsthat import register_heywhatsthat
register_heywhatsthat(app, DB)

from receiver_diagnostics import register_receiver_diagnostics
register_receiver_diagnostics(app, DB)

if __name__ == "__main__":
    if @@ENABLE_WEATHER@@: start_weather()
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from recovery_runtime import start_dashboard_watchdog
    # Use the supplied service manager restart policy; no host-specific watchdog.


    from waitress import serve
    serve(app, host="@@BIND_HOST@@", port=@@WEB_PORT@@,
          threads=4, connection_limit=100, channel_timeout=30,
          max_request_body_size=65536, max_request_header_size=16384,
          # LocalHTTPSProxy alone validates loopback + exact configured host.
          # Waitress must preserve headers for that existing trust boundary.
          clear_untrusted_proxy_headers=False, ident='')
