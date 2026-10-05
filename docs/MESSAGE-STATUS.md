# Messages status

The Messages menu has a small red dot for unread received broadcasts and a
green dot when all configured channels have been viewed up to their latest
message. A gray dot means the first status check has not completed.

Read state is saved per channel in this browser and shared between its dashboard
tabs. Opening the latest list marks the received messages on that channel read
after they render. History pages, searched subsets and hidden views do not
acknowledge new messages. Other channels remain unread until viewed.

The dashboard checks lightweight message IDs every 30 seconds while visible.
The server shares a ten-second cache across viewers. Status checks do not return
message text, send radio traffic or contact an external feed. The indicator
reflects broadcasts received by this collector, not messages the collector
has not received. Clearing browser storage resets the read state.
