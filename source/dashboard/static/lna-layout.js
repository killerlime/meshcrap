// One LNA workspace; retain existing live controls, charts and data bindings.
(() => {
 const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;};
 const evidence={};let summary;
 for(const key of ['analysis','noise','hours'])window.addEventListener('rf:lna-'+key,e=>{evidence[key]=e.detail;renderEvidence();});
 function renderEvidence(){
  if(!summary)return;const a=evidence.analysis,n=evidence.noise,h=evidence.hours,selected=window.getDashboardHours?.()||24;
  summary.replaceChildren(make('h3','Can we compare the LNA yet?'));
  if(!a||!n||!h||[a,n,h].some(d=>Number(d.hours)!==selected)){summary.append(make('p','Gathering evidence for the selected time period…','muted'));return;}
  const eligible=h.timeline.filter(r=>r.comparison_eligible),off=eligible.filter(r=>r.lna_state==='OFF').length,on=eligible.filter(r=>r.lna_state==='ON').length;
  const complete=a.paired_hours>0&&a.nodes.length>0;
  const verdict=make('p',complete?'A comparison is available. Changes are observational; they do not prove the LNA caused them.':'Not enough matched evidence yet. Keep collecting healthy observations in both physical LNA states.','lna-verdict '+(complete?'rf-health-green':'rf-health-yellow'));summary.append(verdict);
  const grid=make('div',null,'lna-readiness');
  for(const [title,ok,detail] of [['Both states observed',off>0&&on>0,`${off} OFF / ${on} ON eligible hours`],['Same clock hours',a.paired_hours>0,`${a.paired_hours} matched pairs`],['Same direct nodes',a.nodes.length>0,`${a.nodes.length} matched nodes`],['Noise comparison',n.matched.paired_hours>0,`${n.matched.paired_hours} qualified pairs`]]){
   const card=make('div',null,ok?'rf-health-green':'rf-health-yellow');card.append(make('strong',(ok?'● Ready · ':'● Waiting · ')+title),make('small',detail));grid.append(card);
  }summary.append(grid);
  if(!a.paired_hours&&selected<168){const wider=make('button','Check 7 days');wider.type='button';wider.addEventListener('click',()=>setHours(168));summary.append(wider);}
 }
 function init(){
  const panel=document.getElementById('dashboard-panel-filter'),hourly=document.getElementById('rfHealthHourlySummary'),noise=document.getElementById('lnaNoisePanel'),analysis=panel?.querySelector('.lna-match');
  const main=hourly?.closest('.card'),controls=analysis?.parentElement,environment=document.getElementById('rfEnvironmentSummary')?.closest('.card');
  if(!panel||!main||!controls||!noise||!environment)return;panel.classList.add('lna-organized');
  const fold=(label,content,id)=>{const d=make('details',null,'card lna-fold');if(id)d.id=id;d.append(make('summary',label),content);return d;};
  analysis.remove();const current=controls.querySelector('strong');current.classList.add('lna-state');
  const changes=make('div');for(const child of [...controls.children])if(child!==current)changes.append(child);
  controls.append(make('p','Physical state recorded by you. Keep the cavity filter and cable unchanged.','muted'),fold('Record a physical LNA change',changes));controls.id='lna-state-controls';
  summary=make('section',null,'card lna-evidence');summary.id='lna-evidence';
  const comparison=fold('Matched OFF / ON results',analysis,'lna-comparison');comparison.open=true;
  main.querySelector('h2').textContent='Reception & signal trends';main.id='lna-trends';
  const rules=make('div');rules.append(document.getElementById('rfHealthHourlyNote'));
  const legend=[...main.querySelectorAll('p')].find(p=>p.textContent.startsWith('Graph markers:'));if(legend)rules.append(legend);
  main.querySelector('h2').after(fold('Hourly totals and eligibility',hourly));main.append(fold('Test method and chart markers',rules));
  const envChart=document.getElementById('rfHealthEnvironmentChart')?.closest('.card');if(envChart)envChart.querySelector('h3').textContent='Receiver conditions';
  const noiseNotes=make('div');for(const p of [...noise.children])if(p.tagName==='P'&&(p.textContent.startsWith('More-negative')||p.textContent.startsWith('Comparison uses')))noiseNotes.append(p);noise.append(fold('How to interpret noise floor',noiseNotes));
  const diagnosticsBody=make('div');environment.classList.remove('card');environment.querySelector('h2').textContent='Raw receiver samples';diagnosticsBody.append(environment);
  const diagnostics=fold('Receiver diagnostics and raw samples',diagnosticsBody,'lna-diagnostics');
  const remoteBody=make('div'),remote=fold('Other receivers · supporting context',remoteBody,'lna-remote-context');remote.hidden=true;
  panel.append(controls,summary,comparison,main,noise,remote,diagnostics);
  function moveExtras(){const logs=document.getElementById('receiverDiagnostics');if(logs&&logs.parentElement!==diagnosticsBody)diagnosticsBody.prepend(logs);const receivers=document.getElementById('lnaRemotePanel');if(receivers&&receivers.parentElement!==remoteBody){remoteBody.append(receivers);remote.hidden=false;}}
  new MutationObserver(moveExtras).observe(panel,{childList:true,subtree:true});moveExtras();renderEvidence();
  panel.addEventListener('toggle',e=>{if(e.target.tagName==='DETAILS'&&e.target.open)requestAnimationFrame(()=>e.target.querySelectorAll('canvas').forEach(c=>window.Chart?.getChart(c)?.resize()));},true);
 }
 window.addEventListener('dashboard:time-window',renderEvidence);
 window.addEventListener('load',init);
})();
