const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('source/dashboard/templates/index.html','utf8');
const script=html.slice(html.indexOf('let dashboardRefreshing = false;'),html.indexOf("document.addEventListener('DOMContentLoaded',()=>requestAnimationFrame(()=>{",html.indexOf('let dashboardRefreshing = false;')));
(async()=>{
 for(const [visible,expected] of [['overview',['summary']],['nodes',['summary']],['map',['map','coverage']],['system',['events']],['survey',['survey']],['filter',[]],['utilities',[]]]){
  const calls=[],notice={};const ctx={document:{hidden:false,getElementById:()=>notice},dashboardPanelVisible:id=>id===visible,queueMicrotask,Promise};
  for(const [name,label] of [['loadSummary','summary'],['loadMap','map'],['loadCoverage','coverage'],['loadEvents','events'],['loadSurvey','survey']])ctx[name]=async()=>calls.push(label);
  vm.createContext(ctx);vm.runInContext(script,ctx);await ctx.refreshDashboard();assert.deepEqual(calls,expected,visible);
 }
 console.log('PASS: visible panels request only their own data; map, events and survey refreshes remain enabled.');
})();
