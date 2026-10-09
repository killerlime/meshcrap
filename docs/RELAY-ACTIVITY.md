# Relay activity

Open **Relays** from the dashboard menu. Choose the shared time window, search
by originating node name or ID, and click column headings to sort in either
direction. Click a node name to open its details.

The table counts unique originating packets received locally through a relay.
**Node info** counts `NODEINFO_APP` packets, rather than all packet types.
Signal and last-heard fields describe the latest relayed reception in the
selected window. Relay entries show how many of that node's packets arrived
with each last-hop relay identifier. Packets with a positive hop count but no
usable relay identifier are included and labeled separately.

This is reception evidence, not proof that the receiver retransmitted those
packets or a measurement of the entire mesh. Direct receptions, imported node
snapshots, MQTT traffic, internal traffic and receiver self-updates are excluded.
Repeated copies of the same origin/packet ID count once within the window.
Packets lacking both hop and relay evidence are reported as unknown and do not
appear in the table.

Meshtastic's `relay_node` field contains only the final byte of the relay node
number. A single match in the known-node list is a candidate, not authenticated
proof of identity. When several known nodes match, the table displays
**Ambiguous**; hover to see the candidates. Unmatched identifiers stay unknown.
No identity is chosen based on role, proximity or signal strength.

The feature uses stored SQLite data and existing Flask dependencies. It sends
no radio requests. Results are cached for 30 seconds and refresh automatically
once per minute while the page is visible; the usual auto-refresh checkbox and
manual refresh button remain available.

Source: [Meshtastic MeshPacket schema](https://github.com/meshtastic/protobufs/blob/master/meshtastic/mesh.proto).

The separate **Node map** supports mouse-wheel zoom, fit-all, focus on the
configured receiver location, and zoom to the selected node. Automatic updates
do not reset its view.
