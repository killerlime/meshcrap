(() => {
  const saver = document.getElementById('idleSaver');
  const logo = document.getElementById('idleLogo');
  let lastTouch = Date.now(), mode = 'active', swallowUntil = 0, held = false, movedAt = 0;
  function moveLogo() {
    logo.style.left = Math.round(Math.random() * Math.max(0, innerWidth - logo.offsetWidth)) + 'px';
    logo.style.top = Math.round(Math.random() * Math.max(0, innerHeight - logo.offsetHeight)) + 'px';
  }
  function tick() {
    if (held) lastTouch = Date.now();
    const elapsed = Date.now() - lastTouch;
    const next = elapsed >= 600000 ? 'sleep' : elapsed >= 300000 ? 'saver' : 'active';
    if (next !== mode) {
      mode = next;
      window.lcdIdle = mode !== 'active';
      saver.dataset.mode = mode;
      if (window.lcdIdle) { if (!saver.open) saver.showModal(); }
      else if (saver.open) {saver.close();window.dispatchEvent(new Event('lcd:wake'));}
      if (mode === 'saver') { moveLogo(); movedAt = Date.now(); }
    }
    if (mode === 'saver' && Date.now() - movedAt >= 15000) { moveLogo(); movedAt = Date.now(); }
  }
  function activity(e) {
    const waking = mode !== 'active';
    if (waking) swallowUntil = Date.now() + 800;
    if (waking || Date.now() < swallowUntil) { e.preventDefault(); e.stopImmediatePropagation(); }
    if (e.type === 'pointerdown' || e.type === 'touchstart') held = true;
    if (['pointerup','pointercancel','touchend','touchcancel'].includes(e.type)) held = false;
    lastTouch = Date.now();
    tick();
  }
  for (const name of ['pointerdown','pointerup','pointercancel','touchstart','touchmove','touchend','touchcancel','click','wheel','keydown'])
    document.addEventListener(name, activity, {capture:true, passive:false});
  saver.addEventListener('cancel', e => { e.preventDefault(); lastTouch = Date.now(); tick(); });
  window.addEventListener('blur', () => { held = false; });
  window.addEventListener('resize', () => { if (mode === 'saver') moveLogo(); });
  setInterval(tick, 1000);
})();
