"""Evidence-based node activity for the local receiver's dashboard."""
from datetime import datetime, timezone

LOCAL_NODE_NUM = @@RECEIVER_NUM@@


def summarize_nodes(conn, start, filt='1=1', params=(), now=None):
    now = now or datetime.now(timezone.utc)
    rows = conn.execute(f"""
        WITH observations AS (
            SELECT p.*,
              CASE WHEN p.from_num != CASE WHEN COALESCE(json_extract(CASE WHEN json_valid(p.raw_json) THEN p.raw_json ELSE '{{}}' END,'$._collectorReceiverId'),'@@RECEIVER_ID@@')='@@RECEIVER_ID@@' THEN @@RECEIVER_NUM@@ ELSE {LOCAL_NODE_NUM} END
                AND COALESCE(p.transport,'') NOT IN ('TRANSPORT_MQTT','TRANSPORT_INTERNAL')
                AND CASE WHEN json_valid(p.raw_json)
                    THEN COALESCE(json_extract(p.raw_json,'$.viaMqtt'),0) ELSE 0 END = 0
                AND (p.transport='TRANSPORT_LORA' OR p.rx_snr IS NOT NULL OR p.rx_rssi IS NOT NULL)
                THEN 1 ELSE 0 END AS is_rf
            FROM packets p
            WHERE p.collector_time >= ? AND ({filt})
              AND COALESCE(p.observation_type,'LIVE')='LIVE'
              AND p.from_num IS NOT NULL
        ), totals AS (
            SELECT from_num, MAX(from_id) from_id, COUNT(*) packets,
              SUM(is_rf) rf_packets,
              COUNT(CASE WHEN is_rf=1 THEN rx_snr END) signal_samples,
              AVG(CASE WHEN is_rf=1 THEN rx_snr END) avg_snr,
              MIN(CASE WHEN is_rf=1 THEN rx_snr END) min_snr,
              MAX(CASE WHEN is_rf=1 THEN rx_snr END) max_snr,
              AVG(CASE WHEN is_rf=1 THEN rx_rssi END) avg_rssi,
              MIN(CASE WHEN is_rf=1 THEN rx_rssi END) min_rssi,
              MAX(CASE WHEN is_rf=1 THEN rx_rssi END) max_rssi,
              SUM(CASE WHEN is_rf=1 AND hops_used BETWEEN 0 AND 7 THEN 1 ELSE 0 END) known_hop_packets,
              SUM(CASE WHEN is_rf=1 AND hops_used=0 THEN 1 ELSE 0 END) direct_packets,
              AVG(CASE WHEN is_rf=1 AND hops_used BETWEEN 0 AND 7 THEN hops_used END) avg_hops,
              MAX(collector_time) last_seen,
              MAX(CASE WHEN is_rf=1 THEN collector_time END) last_rf_seen,
              MAX(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN collector_time END) position_seen
            FROM observations GROUP BY from_num
        )
        SELECT t.*, COALESCE(NULLIF(n.node_id,''),NULLIF(t.from_id,''),printf('!%08x',t.from_num)) node_id,
          COALESCE(NULLIF(trim(n.long_name),''),NULLIF(trim(n.short_name),''),NULLIF(t.from_id,''),printf('!%08x',t.from_num)) node,
          n.short_name,n.hw_model,n.role,s.hardware site_hardware,
          CASE WHEN s.latitude IS NOT NULL AND s.longitude IS NOT NULL THEN s.latitude ELSE n.latitude END latitude,
          CASE WHEN s.latitude IS NOT NULL AND s.longitude IS NOT NULL THEN s.longitude ELSE n.longitude END longitude,
          CASE WHEN s.latitude IS NOT NULL AND s.longitude IS NOT NULL THEN 'Installed site'
               WHEN n.latitude IS NOT NULL AND n.longitude IS NOT NULL THEN 'Last advertised position'
               ELSE 'No position' END position_source
        FROM totals t LEFT JOIN nodes n ON n.node_num=t.from_num
        LEFT JOIN sites s ON s.site_id=(SELECT site_id FROM sites WHERE node_long_name=n.long_name ORDER BY updated_at DESC,site_id LIMIT 1)
        ORDER BY t.last_seen DESC,t.from_num
    """, [start] + list(params)).fetchall()
    result=[]
    for row in rows:
        d=dict(row)
        d['is_local']=d['from_num']==LOCAL_NODE_NUM
        d['is_meshcrap']=(d['short_name'] or '').strip().upper().startswith('@@NODE_PREFIX@@')
        known=d['known_hop_packets']
        d['unknown_hop_packets']=d['rf_packets']-known
        d['direct_pct']=round(d['direct_packets']/known*100,1) if known else None
        for key in ('avg_snr','min_snr','max_snr','avg_rssi','min_rssi','max_rssi','avg_hops'):
            if d[key] is not None: d[key]=round(d[key],2 if key=='avg_hops' else 1)
        d['worst_snr']=d['min_snr']; d['best_snr']=d['max_snr']
        try:
            dt=datetime.fromisoformat(d['last_seen'].replace('Z','+00:00'))
            age=max(0,(now-dt.replace(tzinfo=dt.tzinfo or timezone.utc)).total_seconds())
        except (ValueError,TypeError): age=None
        d['activity']='Unknown' if age is None else ('Within 1h' if age<3600 else 'Within 24h' if age<86400 else 'Older')
        # Compatibility fields; reception evidence does not establish node health.
        d['score']=None; d['health']='LOCAL RECEIVER' if d['is_local'] else 'NOT SCORED'
        result.append(d)
    return result
