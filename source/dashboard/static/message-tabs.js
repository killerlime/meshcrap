(() => {
  function init() {
    const dashboard=document.querySelector('main');
    if(!dashboard||document.getElementById('consoleTabs'))return;
    document.querySelector('nav[aria-label="Message navigation"]')?.remove();
    const existing=document.getElementById('dashboardTabs');
    if(existing){
      const button=document.createElement('button');button.type='button';button.textContent='Messages';button.id='dashboard-tab-messages';
      button.setAttribute('role','tab');button.setAttribute('aria-selected','false');button.setAttribute('aria-controls','dashboard-panel-messages');button.tabIndex=-1;
      const panel=document.createElement('section');panel.id='dashboard-panel-messages';panel.className='dashboard-panel';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);
      let frame;
      button.addEventListener('click',()=>{
        dashboard.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);
        existing.querySelectorAll('[role="tab"]').forEach(b=>{b.setAttribute('aria-selected',String(b===button));b.tabIndex=b===button?0:-1;});
        if(!frame){frame=document.createElement('iframe');frame.title='Channel messages';frame.src='/messages?embedded=1';frame.style.cssText='display:block;width:100%;height:calc(100vh - 280px);min-height:520px;border:0;border-radius:12px';panel.append(frame);}
      });
      existing.addEventListener('click',event=>{if(event.target.closest('[role="tab"]')!==button){panel.hidden=true;button.setAttribute('aria-selected','false');button.tabIndex=-1;}});
      existing.addEventListener('keydown',event=>{
        if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
        const tabs=[...existing.querySelectorAll('[role="tab"]')];const i=tabs.indexOf(document.activeElement);if(i<0)return;
        event.preventDefault();event.stopImmediatePropagation();
        const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
        tabs[next].click();tabs[next].focus();
      },true);
      existing.append(button);dashboard.append(panel);return;
    }
    const style=document.createElement('style');
    style.textContent=`.console-tabs{display:flex;gap:8px;padding:0 20px;margin:18px auto;max-width:1440px}.console-tabs button{font:inherit;padding:12px 20px;border:1px solid #33465e;border-radius:9px;background:#172333;color:#a5b3c6;cursor:pointer}.console-tabs button[aria-selected="true"]{color:#64d6ba;border-color:#64d6ba;background:#203247}.console-tabs button:focus-visible{outline:2px solid #64d6ba;outline-offset:3px}#console-messages{max-width:1100px;margin:auto;padding:0 12px}#console-messages iframe{display:block;width:100%;height:calc(100vh - 220px);min-height:520px;border:0;border-radius:12px}[data-console-panel][hidden]{display:none!important}`;
    document.head.append(style);
    const nav=document.createElement('div');nav.id='consoleTabs';nav.className='console-tabs';
    nav.setAttribute('role','tablist');nav.setAttribute('aria-label','Console sections');
    const messages=document.createElement('section');messages.id='console-messages';
    dashboard.id='console-dashboard';
    const panels=[dashboard,messages];const buttons=[];let frame;
    ['Dashboard','Messages'].forEach((label,i)=>{
      const button=document.createElement('button');button.type='button';button.textContent=label;
      button.id='console-tab-'+i;button.setAttribute('role','tab');button.setAttribute('aria-controls',panels[i].id);
      panels[i].setAttribute('role','tabpanel');panels[i].setAttribute('aria-labelledby',button.id);panels[i].dataset.consolePanel='';
      button.addEventListener('click',()=>activate(i));
      button.addEventListener('keydown',event=>{
        if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
        event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?1:1-i;
        activate(next);buttons[next].focus();
      });
      buttons.push(button);nav.append(button);
    });
    dashboard.before(nav);dashboard.after(messages);
    function activate(index){
      panels.forEach((panel,i)=>{panel.hidden=i!==index;buttons[i].setAttribute('aria-selected',String(i===index));buttons[i].tabIndex=i===index?0:-1;});
      if(index===1&&!frame){frame=document.createElement('iframe');frame.title='Channel messages';frame.src='/messages?embedded=1';messages.append(frame);}
      if(index===0)window.dispatchEvent(new Event('resize'));
    }
    activate(0);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
