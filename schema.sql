CREATE TABLE collector_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TEXT NOT NULL,
        event_type TEXT NOT NULL,
        message TEXT
    );

CREATE TABLE coverage_surveys (

    survey_id INTEGER
        PRIMARY KEY AUTOINCREMENT,

    started_at TEXT NOT NULL,

    ended_at TEXT,

    start_row_id INTEGER NOT NULL,

    end_row_id INTEGER,

    start_coverage REAL,

    end_coverage REAL,

    notes TEXT
, area_id TEXT NOT NULL DEFAULT 'home');

CREATE TABLE external_node_snapshots (snapshot_sha256 TEXT NOT NULL,node_id TEXT NOT NULL,source_url TEXT NOT NULL,imported_at TEXT NOT NULL,raw_json TEXT NOT NULL,PRIMARY KEY(snapshot_sha256,node_id));

CREATE TABLE furthest_direct_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    packet_row_id INTEGER UNIQUE,
    packet_id INTEGER,
    collector_time TEXT NOT NULL,
    node_id TEXT,
    node TEXT,
    distance_miles REAL NOT NULL,
    rx_snr REAL,
    rx_rssi INTEGER,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    location_source TEXT NOT NULL
);

CREATE TABLE furthest_reached_history (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    packet_row_id INTEGER UNIQUE,

    packet_id INTEGER,

    collector_time TEXT NOT NULL,

    node_id TEXT,

    node TEXT,

    distance_miles REAL NOT NULL,

    hops_used INTEGER,

    rx_snr REAL,

    rx_rssi INTEGER,

    latitude REAL NOT NULL,

    longitude REAL NOT NULL,

    location_source TEXT NOT NULL
);

CREATE TABLE node_metadata_backfills (snapshot_sha256 TEXT NOT NULL,node_num INTEGER NOT NULL,field TEXT NOT NULL,previous_json TEXT NOT NULL,imported_json TEXT NOT NULL,imported_at TEXT NOT NULL,PRIMARY KEY(snapshot_sha256,node_num,field));

CREATE TABLE node_metadata_refreshes (id INTEGER PRIMARY KEY, snapshot_sha256 TEXT,node_num INTEGER,field TEXT,previous_json TEXT,imported_json TEXT,basis_json TEXT,imported_at TEXT);

CREATE TABLE node_notes (
    node_num INTEGER PRIMARY KEY,
    node_id TEXT,
    long_name TEXT,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE node_purge_requests(token TEXT PRIMARY KEY,completed_at REAL NOT NULL);

CREATE TABLE node_reappearance_guards (
 node_num INTEGER PRIMARY KEY, node_id TEXT NOT NULL UNIQUE, long_name TEXT NOT NULL,
 removed_at TEXT NOT NULL, removed_epoch INTEGER NOT NULL, released_at TEXT
);

CREATE TABLE nodes (
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

CREATE TABLE packets (
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
    , observation_type TEXT DEFAULT "LIVE");

CREATE TABLE pki_jobs (
              id TEXT PRIMARY KEY,node_num INTEGER NOT NULL,kind TEXT NOT NULL,
              requested_at REAL NOT NULL,packet_id INTEGER,status TEXT NOT NULL,
              received_at REAL,error TEXT);

CREATE TABLE pki_samples (
              job_id TEXT PRIMARY KEY,node_num INTEGER NOT NULL,kind TEXT NOT NULL,
              observed_at REAL,received_at REAL NOT NULL,payload_json TEXT NOT NULL,
              rx_rssi REAL,rx_snr REAL,hops INTEGER,transport TEXT NOT NULL);

CREATE TABLE pki_schedule (
              node_num INTEGER NOT NULL,kind TEXT NOT NULL,next_at REAL NOT NULL,
              failures INTEGER NOT NULL DEFAULT 0,last_status TEXT,last_success REAL,
              PRIMARY KEY(node_num,kind));

CREATE TABLE sites (
    site_id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL UNIQUE,
    node_long_name TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    agl_ft REAL,
    msl_ft REAL,
    hardware TEXT,
    antenna TEXT,
    antenna_gain_dbi REAL,
    ownership TEXT,
    notes TEXT,
    updated_at TEXT
);

CREATE TABLE web_sent_messages (
                sender_num INTEGER NOT NULL, packet_id INTEGER NOT NULL,
                channel INTEGER NOT NULL, destination_num INTEGER NOT NULL,
                text TEXT NOT NULL, submitted_at TEXT NOT NULL,
                PRIMARY KEY(sender_num, packet_id));

CREATE TRIGGER guard_deleted_node_fresh_packet AFTER INSERT ON packets
WHEN EXISTS (SELECT 1 FROM node_reappearance_guards g WHERE g.released_at IS NULL
 AND (g.node_num=NEW.from_num OR g.node_id=NEW.from_id)
 AND COALESCE(NEW.observation_type,'LIVE')='LIVE'
 AND COALESCE(NEW.rx_time,0)>g.removed_epoch AND NEW.collector_time>=g.removed_at
 AND (NEW.rx_snr IS NOT NULL OR NEW.rx_rssi IS NOT NULL)
 AND COALESCE(json_extract(NEW.raw_json,'$.viaMqtt'),0)=0)
BEGIN
 UPDATE node_reappearance_guards SET released_at=NEW.collector_time
 WHERE released_at IS NULL AND (node_num=NEW.from_num OR node_id=NEW.from_id);
 INSERT OR IGNORE INTO nodes(node_num,node_id,long_name,last_heard,updated_at)
 SELECT node_num,node_id,long_name,NEW.rx_time,NEW.collector_time FROM node_reappearance_guards
 WHERE released_at=NEW.collector_time AND (node_num=NEW.from_num OR node_id=NEW.from_id);
END;

CREATE TRIGGER guard_deleted_node_insert BEFORE INSERT ON nodes
WHEN EXISTS (SELECT 1 FROM node_reappearance_guards g WHERE g.released_at IS NULL AND (g.node_num=NEW.node_num OR g.node_id=NEW.node_id))
BEGIN SELECT RAISE(IGNORE); END;

CREATE TRIGGER guard_deleted_node_stale_packet BEFORE INSERT ON packets
WHEN EXISTS (SELECT 1 FROM node_reappearance_guards g WHERE g.released_at IS NULL
 AND (g.node_num=NEW.from_num OR g.node_id=NEW.from_id)
 AND NOT (COALESCE(NEW.observation_type,'LIVE')='LIVE'
 AND COALESCE(NEW.rx_time,0)>g.removed_epoch AND NEW.collector_time>=g.removed_at
 AND (NEW.rx_snr IS NOT NULL OR NEW.rx_rssi IS NOT NULL)
 AND COALESCE(json_extract(NEW.raw_json,'$.viaMqtt'),0)=0))
BEGIN SELECT RAISE(IGNORE); END;

CREATE TRIGGER guard_deleted_node_update BEFORE UPDATE ON nodes
WHEN EXISTS (SELECT 1 FROM node_reappearance_guards g WHERE g.released_at IS NULL AND (g.node_num=NEW.node_num OR g.node_id=NEW.node_id))
BEGIN SELECT RAISE(IGNORE); END;

CREATE INDEX idx_furthest_direct_history_time
ON furthest_direct_history(collector_time)
;

CREATE INDEX idx_furthest_reached_history_time
ON furthest_reached_history(collector_time)
;

CREATE INDEX idx_node_notes_long_name
    ON node_notes(long_name);

CREATE INDEX idx_node_notes_node_id
    ON node_notes(node_id);

CREATE INDEX idx_nodes_long_name ON nodes(long_name);

CREATE INDEX idx_nodes_node_id
        ON nodes(node_id);

CREATE INDEX idx_packets_channel_text ON packets(channel,row_id) WHERE portnum='TEXT_MESSAGE_APP' AND to_num=4294967295;

CREATE INDEX idx_packets_collector_time ON packets(collector_time);

CREATE UNIQUE INDEX idx_packets_dedupe
    ON packets(
        packet_id,
        from_num,
        COALESCE(rx_time, -1),
        COALESCE(rx_snr, -999.0),
        COALESCE(hop_start, -1),
        COALESCE(hop_limit, -1)
    );

CREATE INDEX idx_packets_from_id
        ON packets(from_id);

CREATE INDEX idx_packets_from_num
        ON packets(from_num);

CREATE INDEX idx_packets_live_time ON packets(collector_time) WHERE observation_type='LIVE';

CREATE INDEX idx_packets_packet_id
        ON packets(packet_id);

CREATE INDEX idx_packets_portnum
        ON packets(portnum);

CREATE INDEX idx_packets_rx_time
        ON packets(rx_time);

CREATE INDEX pki_jobs_node ON pki_jobs(node_num,kind,requested_at);

CREATE INDEX pki_jobs_request ON pki_jobs(packet_id);

CREATE INDEX pki_samples_time ON pki_samples(node_num,kind,observed_at);
