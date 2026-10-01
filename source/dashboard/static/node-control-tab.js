(() => {
  function init(){
    const nav=document.getElementById('dashboardTabs');
    const main=document.querySelector('main');
    if(!nav||!main||document.getElementById('dashboard-tab-control'))return;
    const button=document.createElement('button');button.type='button';button.textContent='Node Control';button.id='dashboard-tab-control';button.setAttribute('role','tab');button.setAttribute('aria-selected','false');button.setAttribute('aria-controls','dashboard-panel-control');button.tabIndex=-1;
    const panel=document.createElement('section');panel.className='dashboard-panel';panel.id='dashboard-panel-control';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);let frame;
    button.onclick=()=>{
      main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);
      nav.querySelectorAll('[role="tab"]').forEach(b=>{b.setAttribute('aria-selected',String(b===button));b.tabIndex=b===button?0:-1;});
      if(!frame){frame=document.createElement('iframe');frame.title='Receiver controls';frame.src='/node-control';frame.style.cssText='display:block;width:100%;height:calc(100vh - 280px);min-height:600px;border:0;border-radius:12px';panel.append(frame);}
    };
    nav.addEventListener('click',e=>{if(e.target.closest('[role="tab"]')!==button){panel.hidden=true;button.setAttribute('aria-selected','false');button.tabIndex=-1;}});
    nav.append(button);main.append(panel);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
