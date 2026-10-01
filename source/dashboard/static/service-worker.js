// Network-only application. Never cache APIs, user pages, keys or commands.
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || event.request.mode !== 'navigate') return;
  if (new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(fetch(event.request).catch(() => new Response(
    '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Meshcrap offline</title><style>body{font:18px/1.6 system-ui;background:#111713;color:#e1ebe4;padding:28px}a{color:#67ea94}</style><h1>Collector unavailable</h1><p>Check your connection and Tailscale, then reopen the dashboard. No commands have been queued.</p><a href="/">Try again</a>',
    {status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}}
  )));
});
