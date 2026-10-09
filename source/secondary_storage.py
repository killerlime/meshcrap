"""Optional secondary receiver storage. Separate history, without upload hooks."""
import json,sqlite3,time,threading
from datetime import datetime,timezone
from pathlib import Path
from node_roles import reported_role
BASE_DIR=Path('@@DATA_DIR@@')/'secondary'
DB_FILE=BASE_DIR/'mesh.db'
db=None
db_lock=threading.RLock()
last_receive_monotonic=time.monotonic()
def json_default(obj):
    """Make protobuf/bytes/other odd objects safe for raw JSON storage."""
    if isinstance(obj, bytes):
        return obj.hex()

    try:
        return str(obj)
    except Exception:
        return repr(obj)

def open_database():
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False,
        timeout=30
    )

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS packets (
        row_id INTEGER PRIMARY KEY AUTOINCREMENT,

        collector_time TEXT NOT NULL,
        rx_time INTEGER,

        packet_id INTEGER,
        from_num INTEGER,
        from_id TEXT,
        to_num INTEGER,
        to_id TEXT,

        channel INTEGER,
        portnum TEXT,

        rx_snr REAL,
        rx_rssi INTEGER,

        hop_start INTEGER,
        hop_limit INTEGER,
        hops_used INTEGER,

        transport TEXT,

        latitude REAL,
        longitude REAL,
        altitude INTEGER,

        battery_level INTEGER,
        voltage REAL,
        channel_utilization REAL,
        air_util_tx REAL,
        uptime_seconds INTEGER,

        raw_json TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_packets_rx_time
        ON packets(rx_time);

    CREATE INDEX IF NOT EXISTS idx_packets_from_id
        ON packets(from_id);

    CREATE INDEX IF NOT EXISTS idx_packets_from_num
        ON packets(from_num);

    CREATE INDEX IF NOT EXISTS idx_packets_portnum
        ON packets(portnum);

    CREATE INDEX IF NOT EXISTS idx_packets_packet_id
        ON packets(packet_id);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_packets_dedupe
    ON packets(
        packet_id,
        from_num,
        COALESCE(rx_time, -1),
        COALESCE(rx_snr, -999.0),
        COALESCE(hop_start, -1),
        COALESCE(hop_limit, -1)
    );

    CREATE TABLE IF NOT EXISTS nodes (
        node_num INTEGER PRIMARY KEY,

        node_id TEXT,
        long_name TEXT,
        short_name TEXT,
        hw_model TEXT,
        role TEXT,

        latitude REAL,
        longitude REAL,
        altitude INTEGER,

        battery_level INTEGER,
        voltage REAL,

        last_heard INTEGER,
        updated_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_nodes_node_id
        ON nodes(node_id);

    CREATE TABLE IF NOT EXISTS collector_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TEXT NOT NULL,
        event_type TEXT NOT NULL,
        message TEXT
    );
    """)

    conn.execute("ALTER TABLE packets ADD COLUMN observation_type TEXT DEFAULT 'LIVE'") if 'observation_type' not in {r[1] for r in conn.execute('PRAGMA table_info(packets)')} else None
    conn.execute('CREATE INDEX IF NOT EXISTS idx_packets_collector_time ON packets(collector_time)')
    conn.execute('CREATE TABLE IF NOT EXISTS collection_sessions(session_id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, profile_json TEXT NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_started ON collection_sessions(started_at)')
    conn.commit()
    return conn

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def log_event(event_type, message):
    print(f"[{event_type}] {message}", flush=True)

    if db is None:
        return

    try:
        with db_lock:
            db.execute("""
                INSERT INTO collector_events (
                    event_time,
                    event_type,
                    message
                )
                VALUES (?, ?, ?)
            """, (
                now_iso(),
                event_type,
                str(message)
            ))
            db.commit()

    except Exception as e:
        print(f"[DB ERROR] Could not log event: {e}", flush=True)

def snapshot_nodes(iface):
    nodes = getattr(iface, "nodes", {}) or {}

    count = 0

    with db_lock:
        for node_key, node in nodes.items():

            if not isinstance(node, dict):
                continue

            user = node.get("user", {}) or {}
            position = node.get("position", {}) or {}
            metrics = node.get("deviceMetrics", {}) or {}

            node_num = node.get("num")

            if node_num is None:
                continue

            db.execute("""
                INSERT INTO nodes (
                    node_num,
                    node_id,
                    long_name,
                    short_name,
                    hw_model,
                    role,
                    latitude,
                    longitude,
                    altitude,
                    battery_level,
                    voltage,
                    last_heard,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(node_num) DO UPDATE SET
                    node_id       = COALESCE(excluded.node_id, nodes.node_id),
                    long_name     = COALESCE(excluded.long_name, nodes.long_name),
                    short_name    = COALESCE(excluded.short_name, nodes.short_name),
                    hw_model      = COALESCE(excluded.hw_model, nodes.hw_model),
                    role          = COALESCE(excluded.role, nodes.role),
                    latitude      = COALESCE(excluded.latitude, nodes.latitude),
                    longitude     = COALESCE(excluded.longitude, nodes.longitude),
                    altitude      = COALESCE(excluded.altitude, nodes.altitude),
                    battery_level = COALESCE(excluded.battery_level, nodes.battery_level),
                    voltage       = COALESCE(excluded.voltage, nodes.voltage),
                    last_heard    = COALESCE(excluded.last_heard, nodes.last_heard),
                    updated_at    = excluded.updated_at
            """, (
                node_num,
                user.get("id") or node_key,
                user.get("longName"),
                user.get("shortName"),
                user.get("hwModel"),
                reported_role(user),

                position.get("latitude"),
                position.get("longitude"),
                position.get("altitude"),

                metrics.get("batteryLevel"),
                metrics.get("voltage"),

                node.get("lastHeard"),
                now_iso()
            ))

            count += 1

        db.commit()

    log_event("NODE_SNAPSHOT", f"Stored/updated {count} nodes")

def extract_position(decoded):
    position = decoded.get("position") or {}

    return (
        position.get("latitude"),
        position.get("longitude"),
        position.get("altitude")
    )

def extract_metrics(decoded):
    metrics = decoded.get("telemetry") or {}

    if isinstance(metrics, dict):
        metrics = (
            metrics.get("deviceMetrics")
            or metrics.get("device_metrics")
            or metrics
        )

    if not isinstance(metrics, dict):
        metrics = {}

    return (
        metrics.get("batteryLevel"),
        metrics.get("voltage"),
        metrics.get("channelUtilization"),
        metrics.get("airUtilTx"),
        metrics.get("uptimeSeconds")
    )

def update_node_from_packet(packet, decoded):
    from_num = packet.get("from")

    if from_num is None:
        return

    from_id = packet.get("fromId")
    role = reported_role(decoded.get("user")) if decoded.get("portnum") == "NODEINFO_APP" else None

    latitude, longitude, altitude = extract_position(decoded)

    (
        battery_level,
        voltage,
        channel_util,
        air_util_tx,
        uptime
    ) = extract_metrics(decoded)

    with db_lock:
        db.execute("""
            INSERT INTO nodes (
                node_num,
                node_id,
                role,
                latitude,
                longitude,
                altitude,
                battery_level,
                voltage,
                last_heard,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(node_num) DO UPDATE SET
                node_id       = COALESCE(excluded.node_id, nodes.node_id),
                role          = COALESCE(excluded.role, nodes.role),
                latitude      = COALESCE(excluded.latitude, nodes.latitude),
                longitude     = COALESCE(excluded.longitude, nodes.longitude),
                altitude      = COALESCE(excluded.altitude, nodes.altitude),
                battery_level = COALESCE(excluded.battery_level, nodes.battery_level),
                voltage       = COALESCE(excluded.voltage, nodes.voltage),
                last_heard    = COALESCE(excluded.last_heard, nodes.last_heard),
                updated_at    = excluded.updated_at
        """, (
            from_num,
            from_id,
            role,
            latitude,
            longitude,
            altitude,
            battery_level,
            voltage,
            packet.get("rxTime"),
            now_iso()
        ))

        db.commit()

def on_receive(packet, interface):
    global last_receive_monotonic
    last_receive_monotonic = time.monotonic()
    try:
        if not isinstance(packet, dict):
            return

        decoded = packet.get("decoded") or {}

        if not isinstance(decoded, dict):
            decoded = {}

        packet = dict(packet)
        packet["_collectorReceiverId"] = f"!{interface.localNode.nodeNum:08x}"
        collector_time = now_iso()

        rx_time = packet.get("rxTime")
        packet_id = packet.get("id")

        from_num = packet.get("from")
        from_id = packet.get("fromId")

        to_num = packet.get("to")
        to_id = packet.get("toId")

        channel = packet.get("channel")
        portnum = decoded.get("portnum")

        rx_snr = packet.get("rxSnr")
        rx_rssi = packet.get("rxRssi")

        hop_start = packet.get("hopStart")
        hop_limit = packet.get("hopLimit")

        hops_used = None

        if hop_start is not None and hop_limit is not None:
            try:
                hops_used = int(hop_start) - int(hop_limit)
            except (TypeError, ValueError):
                pass

        transport = packet.get("transportMechanism")

        latitude, longitude, altitude = extract_position(decoded)

        (
            battery_level,
            voltage,
            channel_util,
            air_util_tx,
            uptime
        ) = extract_metrics(decoded)

        raw_json = json.dumps(
            packet,
            default=json_default,
            separators=(",", ":")
        )

        with db_lock:
            db.execute("""
                INSERT OR IGNORE INTO packets (
                    collector_time,
                    rx_time,
                    packet_id,

                    from_num,
                    from_id,
                    to_num,
                    to_id,

                    channel,
                    portnum,

                    rx_snr,
                    rx_rssi,

                    hop_start,
                    hop_limit,
                    hops_used,

                    transport,

                    latitude,
                    longitude,
                    altitude,

                    battery_level,
                    voltage,
                    channel_utilization,
                    air_util_tx,
                    uptime_seconds,

                    raw_json,
                    observation_type
                )
                VALUES (
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?
                )
            """, (
                collector_time,
                rx_time,
                packet_id,

                from_num,
                from_id,
                to_num,
                to_id,

                channel,
                portnum,

                rx_snr,
                rx_rssi,

                hop_start,
                hop_limit,
                hops_used,

                transport,

                latitude,
                longitude,
                altitude,

                battery_level,
                voltage,
                channel_util,
                air_util_tx,
                uptime,

                raw_json,
                packet.get('_collectorObservationType', 'UNDATED')
            ))

            db.commit()

        if packet.get('_collectorObservationType', 'UNDATED') == 'LIVE':
            update_node_from_packet(packet, decoded)
            user = decoded.get('user') if decoded.get('portnum') == 'NODEINFO_APP' else None
            if isinstance(user, dict):
                with db_lock:
                    db.execute('UPDATE nodes SET long_name=COALESCE(?,long_name), short_name=COALESCE(?,short_name), hw_model=COALESCE(?,hw_model) WHERE node_num=?',
                               (user.get('longName'), user.get('shortName'), user.get('hwModel'), from_num))
                    db.commit()

        print(
            f"{collector_time} "
            f"{from_id or from_num} "
            f"{portnum or '?'} "
            f"SNR={rx_snr} "
            f"RSSI={rx_rssi} "
            f"hops={hops_used}",
            flush=True
        )

    except Exception as e:
        log_event("PACKET_ERROR", repr(e))
