/* Original optional game launcher. No timer, canvas or game frame until opened. */
(() => {
  'use strict';
  const button = document.createElement('button');
  button.type = 'button'; button.textContent = '❄';
  button.title = 'Take a snow day'; button.setAttribute('aria-label', 'Take a snow day');
  button.style.cssText = 'display:block;margin:24px auto;padding:10px 16px;background:transparent;color:inherit;border:0;cursor:pointer';
  document.querySelector('main')?.append(button);
  button.addEventListener('click', () => {
    const dialog = document.createElement('dialog');
    dialog.setAttribute('aria-label', 'Packet Slopes — a snow day');
    dialog.style.cssText = 'width:min(560px,94vw);height:min(820px,92dvh);max-height:92dvh;padding:8px;border-radius:16px;background:#102638;color:white;border:2px solid #72d2de';
    const close = document.createElement('button'); close.type = 'button'; close.textContent = 'Close snow day';
    close.style.cssText = 'min-height:44px;margin-bottom:6px';
    const frame = document.createElement('iframe'); frame.title = 'Packet Slopes skiing game';
    frame.src = '/static/packet-slopes.html'; frame.setAttribute('sandbox', 'allow-scripts');
    frame.style.cssText = 'width:100%;height:calc(100% - 56px);border:0;display:block';
    dialog.append(close, frame); document.body.append(dialog);
    close.onclick = () => dialog.close();
    dialog.addEventListener('close', () => { frame.remove(); dialog.remove(); button.focus(); }, {once:true});
    dialog.showModal(); close.focus();
  });
})();
