/* Independent optional receiver; no radio or collector actions. */
(() => {
 'use strict';
 function validURL(value){
  if(typeof value!=='string'||value.length>256)return false;
  if(/^\/(?:sniffer|rf-sniffer)(?:-[a-z0-9]{1,24})?\/$/.test(value))return true;
  if(!/^https:\/\/(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)(?::[0-9]{1,5})?(?:\/[A-Za-z0-9_-]+)*\/?$/.test(value))return false;
  try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password&&/^(?:\/[A-Za-z0-9_-]+)*\/?$/.test(url.pathname);}catch{return false;}
 }
 function init(){
  const nav=document.getElementById('dashboardTabs'),main=document.querySelector('main');if(!nav||!main)return;
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!=null)node.textContent=text;if(cls)node.className=cls;return node;};
  const tab=el('button','RF sniffer');tab.type='button';tab.id='dashboard-tab-sniffer';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','dashboard-panel-sniffer');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
  const panel=el('section',null,'dashboard-panel rf-sniffer');panel.id='dashboard-panel-sniffer';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
  const heading=el('div',null,'sniffer-heading'),title=el('h2','RF sniffer'),badge=el('span','Optional · separate receiver','sniffer-separate'),setup=el('button','Quick setup'),open=el('a','Open separately');setup.type='button';open.target='_blank';open.rel='noopener noreferrer';open.hidden=true;heading.append(title,badge,setup,open);
  const status=el('p','Open to load the optional receiver.','sniffer-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const wizard=el('section',null,'sniffer-wizard');wizard.hidden=true;wizard.setAttribute('aria-label','RF sniffer quick setup');wizard.tabIndex=-1;
  const stepTitle=el('h3'),stepBody=el('div'),stepActions=el('div',null,'sniffer-step-actions');wizard.append(stepTitle,stepBody,stepActions);
  const embed=el('div');panel.append(heading,status,wizard,embed);main.append(panel);nav.append(tab);
  let integration=null,loading=false,step=0,frame=null,checkController=null;
  const stages=[
   ['1 · Prepare a separate receiver','Run a passive SDR sniffer independently. Its web dashboard must already work. Meshcrap does not install it, probe radios, or start sharing data.'],
   ['2 · Keep it private','Serve its web interface at a private HTTPS address, or a prefix-aware /sniffer/ path on this dashboard. Keep the native web port on loopback or blocked by a firewall. Protect the separate control endpoints too.'],
   ['3 · Connect the view','Run the short terminal wizard on your dashboard host. It preserves your existing settings. Restart only the dashboard afterward, then check the connection here.']
  ];
  function drawStep(){
   stepTitle.textContent=stages[step][0];stepBody.replaceChildren(el('p',stages[step][1]));stepActions.replaceChildren();
   if(step===0){const source=el('a','Sniffer installation instructions');source.href='https://github.com/alphafox02/meshtastic-sniffer#install';source.target='_blank';source.rel='noopener noreferrer';stepBody.append(source);stepBody.append(el('p','The external project has its own GPL-3.0-or-later license. Its receiver and data remain separate.'));}
   if(step===1)stepBody.append(el('p','Only embed a web page you operate and trust. Keys, channel URLs and credentials belong to the separate private receiver; never enter them here.'));
   if(step===2){stepBody.append(el('code','python meshcrap.py sniffer-setup'));const reload=el('button','Reload settings');reload.type='button';reload.addEventListener('click',()=>loadIntegration(true));stepActions.append(reload);const check=el('button','Check connection');check.type='button';check.disabled=!integration?.enabled;check.addEventListener('click',checkConnection);stepActions.append(check);}
   if(step>0){const back=el('button','Back');back.type='button';back.addEventListener('click',()=>{step--;drawStep();});stepActions.append(back);}
   if(step<2){const next=el('button','Next');next.type='button';next.addEventListener('click',()=>{step++;drawStep();stepTitle.focus();});stepActions.append(next);}
   const close=el('button','Close setup');close.type='button';close.addEventListener('click',()=>{wizard.hidden=true;setup.focus();});stepActions.append(close);
  }
  function showWizard(){drawStep();wizard.hidden=false;wizard.focus();}
  function unloadFrame(){if(frame){frame.remove();frame=null;}}
  function showFrame(){
   if(!integration?.enabled||!validURL(integration.url)||panel.hidden||frame)return;
   frame=el('iframe');frame.title='Independent RF sniffer dashboard';frame.loading='lazy';frame.referrerPolicy='no-referrer';
   // The configured trusted companion owns its controls. Deny popups, top
   // navigation, downloads, camera, microphone, location and USB delegation.
   frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms');frame.setAttribute('allow',"camera 'none'; microphone 'none'; geolocation 'none'; usb 'none'; bluetooth 'none'");
   frame.src=integration.url;embed.append(frame);
   status.textContent='Separate SDR observations. If framing is blocked, use Open separately. This view does not add records to the collector.';
  }
  async function loadIntegration(force=false){
   if(loading)return;if(integration&&!force){showFrame();return;}loading=true;
   try{const response=await fetch('/api/rf-sniffer/integration',{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!response.ok)throw Error();const value=await response.json();if(typeof value.enabled!=='boolean'||value.enabled&&!validURL(value.url))throw Error();integration=value;open.hidden=!value.enabled;unloadFrame();if(value.enabled){open.href=value.url;showFrame();}else{open.removeAttribute('href');status.textContent='Optional receiver is off. Use Quick setup when you want to add one.';showWizard();}if(!wizard.hidden)drawStep();}
   catch{status.textContent='Sniffer settings are unavailable. The collector continues independently.';}
   finally{loading=false;}
  }
  async function checkConnection(){
   if(!integration?.enabled||!validURL(integration.url))return;
   if(new URL(integration.url,location.href).origin!==location.origin){status.textContent='Separate HTTPS origin configured. Browser privacy prevents a reliable connection test here. Check the embedded view or Open separately; RF health is reported by that receiver.';return;}
   checkController?.abort();checkController=new AbortController();const timeout=setTimeout(()=>checkController.abort(),8000);status.textContent='Checking the separate web page…';
   try{const response=await fetch(integration.url,{cache:'no-store',redirect:'error',signal:checkController.signal});if(!response.ok||!(response.headers.get('Content-Type')||'').includes('text/html'))throw Error();await response.body?.cancel();status.textContent='Web page responds. Check that the embedded view shows your receiver; a page response alone cannot verify RF reception.';showFrame();}
   catch{status.textContent='Web page unavailable or redirects. Check the private proxy path, permissions and separate receiver service. Collection is unaffected.';}
   finally{clearTimeout(timeout);}
  }
  setup.addEventListener('click',showWizard);tab.addEventListener('click',()=>{main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(t=>{const active=t===tab;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;});document.querySelector('main>.controls')?.setAttribute('hidden','');loadIntegration();});
  new MutationObserver(()=>{if(panel.hidden){checkController?.abort();unloadFrame();}else showFrame();}).observe(panel,{attributes:true,attributeFilter:['hidden']});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
