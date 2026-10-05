(() => {

 'use strict';

 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};

 window.ConsoleUI={summary(id,items){const box=document.getElementById(id);if(!box)return;box.replaceChildren(...items.map(([label,value,note])=>{const d=el('dl',null,'console-metric');d.append(el('dt',label),el('dd',value));if(note)d.append(el('small',note));return d;}));}};

 function init(){

  if(window.frameElement)document.documentElement.classList.add('console-embedded');

  const nav=document.getElementById('dashboardTabs');if(!nav)return;
  const main=document.querySelector('main');
  const surveyControls=document.getElementById('surveyControls'),surveyLive=document.getElementById('surveyLive');
  if(surveyControls&&surveyLive){
   const tab=el('button','Survey');tab.type='button';tab.id='dashboard-tab-survey';tab.setAttribute('role','tab');tab.setAttribute('aria-controls','dashboard-panel-survey');tab.setAttribute('aria-selected','false');tab.tabIndex=-1;
   const panel=el('section',null,'dashboard-panel');panel.id='dashboard-panel-survey';panel.hidden=true;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);
   const card=el('div',null,'card');card.append(el('h2','Coverage survey'),el('p','Choose an area and connect your travelling radio in the companion app. Tracks show travel; radio observations show coverage.'));
   const mapArea=document.getElementById('coverageArea');if(mapArea){const label=el('label','Survey area '),select=mapArea.cloneNode(true);select.id='surveyCoverageArea';select.removeAttribute('onchange');label.append(select);card.append(label);select.addEventListener('change',()=>{mapArea.value=select.value;mapArea.dispatchEvent(new Event('change',{bubbles:true}));});mapArea.addEventListener('change',()=>{select.value=mapArea.value;});}
   const phone=surveyControls.nextElementSibling;if(phone?.querySelector('a[href="/survey-companion"]'))card.append(phone);
   card.append(surveyControls,surveyLive);panel.append(card);main.append(panel);nav.append(tab);
   tab.addEventListener('click',()=>{main.querySelectorAll('.dashboard-panel').forEach(p=>p.hidden=p!==panel);nav.querySelectorAll('[role=tab]').forEach(b=>{b.setAttribute('aria-selected',String(b===tab));b.tabIndex=b===tab?0:-1;});if(typeof loadSurvey==='function')loadSurvey();});
   nav.addEventListener('click',e=>{if(e.target.closest('[role=tab]')!==tab){panel.hidden=true;tab.setAttribute('aria-selected','false');tab.tabIndex=-1;}});
  }
  const order=['overview','insights','ask','nodes','map','survey','messages','control','filter','heardby','ingestors','utilities','system','debug'];

  const descriptions={survey:['Survey','Roaming routes and survey evidence'],utilities:['Utilities','Database maintenance and debug logs'],insights:['Insights','Trends, observations and evidence'],ask:['Ask questions','Ask about your mesh in plain language'],overview:['Overview','Reception and saved records'],nodes:['Nodes','Matches your search and time window'],map:['Map & coverage','Positions and coverage · locations may be old'],messages:['Messages','Broadcasts and sent messages'],control:['Node control','Select Receiver or Secondary radio · independent controls and connections'],secondary:['Secondary radio control','Optional secondary-radio connection · control only'],filter:['LNA test','Enabled versus disabled · cavity filter and cable setup stay fixed'],heardby:['Heard by','Public reception reports'],ingestors:['MSP ingestors','Public ingestor directory'],system:['System & events','Connection health, diagnostics and configuration history'],debug:['Debug logs','Saved application logs']};

  order.forEach(id=>{const tab=document.getElementById('dashboard-tab-'+id),panel=document.getElementById('dashboard-panel-'+id);if(!tab||!panel)return;nav.append(tab);tab.textContent=descriptions[id][0];panel.tabIndex=0;const head=el('div',null,'console-panel-heading');head.append(el('h2',descriptions[id][0]),el('p',descriptions[id][1]));panel.prepend(head);});

  const controls=document.querySelector('main>.controls');const scope=el('span','Shared time window','console-scope');controls?.append(scope);

  const sync=()=>{const selected=nav.querySelector('[aria-selected=true]');if(!selected)return;const id=selected.id.replace('dashboard-tab-','');if(controls)controls.hidden=!['overview','insights','nodes','map','filter','role','whatif'].includes(id);const windowSelect=controls?.querySelector('#dashboardTimeWindow');if(windowSelect)windowSelect.value=String(window.getDashboardHours?.()||24);try{sessionStorage.setItem('console-active-tab',id);}catch{};controls?.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.getAttribute('onclick')?.match(/setHours\((\d+)\)/)?.[1])===(typeof hours==='number'?hours:24))));};

  nav.addEventListener('click',()=>queueMicrotask(sync));window.addEventListener('dashboard:time-window',()=>queueMicrotask(sync));controls?.addEventListener('click',()=>queueMicrotask(sync));

  document.querySelectorAll('th[onclick]').forEach(th=>{th.tabIndex=0;th.setAttribute('aria-label','Sort by '+th.textContent.trim());th.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();th.click();}});});

  document.querySelectorAll('.dashboard-panel').forEach(panel=>{const head=panel.querySelector('.console-panel-heading h2'),cardHeading=panel.querySelector('.card h2');if(cardHeading&&head&&cardHeading.textContent.trim().toLowerCase()===head.textContent.trim().toLowerCase())cardHeading.hidden=true;});

  document.querySelectorAll('.dashboard-panel> .card>p.muted').forEach(p=>{if(p.textContent.length<160)return;const details=el('details',null,'console-notes');details.append(el('summary','About these measurements'));p.before(details);details.append(p);});

  let saved;try{saved=sessionStorage.getItem('console-active-tab');}catch{}if(saved)document.getElementById('dashboard-tab-'+saved)?.click();sync();

 }

 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();

})();
