// Arrange existing live elements without replacing their controls or data bindings.
(() => {
 const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;};
 function init(){
  const panel=document.getElementById('dashboard-panel-filter');
  const hourly=document.getElementById('rfHealthHourlySummary');
  const noise=document.getElementById('lnaNoisePanel');
  const analysis=panel?.querySelector('.lna-match');
  const environment=document.getElementById('rfEnvironmentSummary')?.closest('.card');
  const main=hourly?.closest('.card');
  const controls=analysis?.parentElement;
  if(!panel||!main||!controls||!noise||!environment||panel.dataset.organized)return;
  panel.dataset.organized='true';panel.classList.add('lna-organized');
  const style=make('style');style.textContent=`
   .lna-organized{gap:16px!important}
   .lna-organized .lna-controls{margin:0;padding:18px;background:var(--card);min-width:0}
   .lna-organized h2,.lna-organized h3{margin-top:0}
   .lna-organized p{line-height:1.55;margin:8px 0}
   .lna-organized .lna-section-note{color:var(--muted);font-size:13px;line-height:1.5;margin:0 0 14px}
   .lna-organized details{margin-top:12px;border-top:1px solid var(--border);padding-top:12px}
   .lna-organized summary{cursor:pointer;min-height:30px;line-height:1.5;font-weight:600;color:var(--text);padding:4px 0}
   .lna-organized summary:focus-visible{outline:2px solid var(--mesh);outline-offset:4px;border-radius:3px}
   .lna-organized .lna-state{display:block;font-size:18px;color:var(--mesh);margin-bottom:8px}
   .lna-organized .lna-match{padding:18px;border:1px solid var(--border);border-radius:10px;overflow:auto}
   .lna-organized .lna-match table{width:100%;text-align:left;border-collapse:collapse}
   .lna-organized .lna-match th,.lna-organized .lna-match td{padding:9px;border-bottom:1px solid var(--border)}
   .lna-organized #rfHealthHourlyNote{font-size:13px;line-height:1.55;text-transform:none;letter-spacing:normal}
   .lna-organized .graph-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
   .lna-organized .graph-grid>.card:last-child:nth-child(odd){grid-column:1/-1}
   .lna-organized .noc-grid{grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px}
   .lna-organized .lna-detail-body{margin-top:14px}
   .lna-organized #lnaNoisePanel>p{font-size:14px}
   @media(max-width:700px){.lna-organized .graph-grid{grid-template-columns:1fr}.lna-organized .lna-controls,.lna-organized .lna-match{padding:14px}.lna-organized .noc-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.lna-organized .value{overflow-wrap:anywhere}}
  `;document.head.append(style);
  // Keep the current state visible; put deliberate state changes behind a disclosure.
  analysis.remove();
  const current=controls.querySelector('strong');current.classList.add('lna-state');
  const change=make('details');change.append(make('summary','Record an LNA change'));
  for(const child of [...controls.children])if(child!==current)change.append(child);
  controls.append(make('p','Record changes after physically switching the LNA. The cavity filter and cable stay fixed.','lna-section-note'),change);
  // Retain comparison rendering in its original element, independent of the controls.
  const mainHeading=main.querySelector('h2');mainHeading.textContent='Hourly trends';
  mainHeading.after(make('p','Reception, signal and receiver conditions for the selected window. Only complete, healthy hours enter the comparison.','lna-section-note'));
  const rules=make('details');rules.append(make('summary','Test setup, eligibility and switch legend'));
  const note=document.getElementById('rfHealthHourlyNote');rules.append(note);
  // The switch legend is injected beside the hourly note by the marker plugin.
  const legend=[...main.querySelectorAll('p')].find(p=>p.textContent.startsWith('Graph markers:'));
  if(legend)rules.append(legend);
  main.append(rules);
  const envChart=document.getElementById('rfHealthEnvironmentChart')?.closest('.card');
  if(envChart)envChart.querySelector('h3').textContent='Hourly receiver conditions';
  // Keep the noise trend visible; move its longer methodology below it.
  const noiseDetails=make('details');noiseDetails.append(make('summary','How to read noise floor'));
  const paragraphs=[...noise.children].filter(e=>e.tagName==='P');
  for(const p of paragraphs)if(p.textContent.startsWith('More-negative')||p.textContent.startsWith('Comparison uses'))noiseDetails.append(p);
  noise.append(noiseDetails);
  // Raw receiver diagnostics remain available without competing with the primary test.
  const diagnostics=make('details',null,'card');diagnostics.append(make('summary','Detailed receiver diagnostics'));
  environment.classList.add('lna-detail-body');environment.classList.remove('card');
  environment.querySelector('h2').textContent='Raw receiver samples';diagnostics.append(environment);
  panel.append(controls,analysis,noise,main,diagnostics);
  panel.addEventListener('toggle',e=>{if(e.target.tagName==='DETAILS'&&e.target.open)requestAnimationFrame(()=>e.target.querySelectorAll('canvas').forEach(c=>window.Chart?.getChart(c)?.resize()));},true);
 }
 window.addEventListener('load',init);
})();
