/** LCD controls use the existing authenticated console session. */
(() => {
  let busy=false;
  const box=document.getElementById('lcdControls');
  if (!box) return;
  const status=box.querySelector('[data-lcd-status]'),note=box.querySelector('[data-lcd-note]');
  const sleep=box.querySelector('[data-lcd-sleep]'),wake=box.querySelector('[data-lcd-wake]');
  function render(d) {
    status.textContent='LCD: '+(d.state || 'unknown');
    const changing=['activating','deactivating','reloading'].includes(d.service_state);
    sleep.disabled=busy||!d.available||!d.unlocked||changing||d.state==='asleep';
    wake.disabled=busy||!d.available||!d.unlocked||changing||d.state==='awake';
    note.textContent=!d.available?'One-time administrator setup required.':!d.unlocked?'Unlock Receiver controls to use Sleep/Wake.':'Sleep stops the LCD browser to free memory. Wake takes a few seconds. The backlight may remain lit; collection continues. The LCD starts again after a Pi reboot.';
  }
  async function requestState(action) {
    const r=await fetch('/api/lcd-control',{cache:'no-store',signal:AbortSignal.timeout(35000),...(action?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})}:{})});
    const d=await r.json();if(!r.ok)throw Error(d.error||'LCD control unavailable.');return d;
  }
  async function refresh() {
    if(busy||document.hidden||!box.getClientRects().length)return;
    try{render(await requestState());}catch(e){status.textContent='LCD: unavailable';note.textContent=e.message;sleep.disabled=wake.disabled=true;}
  }
  async function act(action) {
    if(busy)return;busy=true;sleep.disabled=wake.disabled=true;note.textContent=action==='sleep'?'Putting LCD to sleep…':'Waking LCD…';
    try{const d=await requestState(action);busy=false;render(d);}catch(e){busy=false;note.textContent=e.message;status.textContent='LCD: refresh to check state';}
  }
  sleep.addEventListener('click',()=>act('sleep'));wake.addEventListener('click',()=>act('wake'));
  box.querySelector('[data-lcd-refresh]').addEventListener('click',refresh);
  box.querySelector('[data-lcd-unlock]').addEventListener('click',()=>window.showDashboardTab?.('control',true));
  refresh();setInterval(refresh,15000);document.addEventListener('visibilitychange',refresh);
})();
