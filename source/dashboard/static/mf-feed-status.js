(() => {
const main=document.querySelector('main');if(!main)return;
const box=document.createElement('details');box.className='console-feed';
const summary=document.createElement('summary'),description=document.createElement('p');
summary.textContent='Potato feed';box.append(summary,description);main.querySelector('h1')?.after(box);
box.insertAdjacentHTML('beforeend','<p class="muted">PotatoMesh integration · Credit to <a href="https://github.com/l5yth/potato-mesh">l5yth and the PotatoMesh contributors · source</a>.</p>');
let busy=false;
async function refresh(){if(busy||document.hidden)return;busy=true;
try{const r=await fetch('/api/potato-feed/status',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error();const s=await r.json();
summary.textContent=!s.enabled?'Potato feed · disabled':s.operator_hold?'Potato feed · review required':s.capture_paused?'Potato feed · paused':`Potato feed · ${s.pending} queued`;
description.textContent=!s.enabled?'Optional integration. Configure your own destination and token before enabling.':`Public MediumFast slot ${s.slot}; types: ${(s.data_types||[]).join(', ')}. ${s.sent} accepted records. Private messages and other slots stay local. No original per-node exceptions are included.`;
}catch(e){summary.textContent='Potato feed · status unavailable';}finally{busy=false;}}
refresh();setInterval(refresh,15000);
})();
