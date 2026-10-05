const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let now=10000,online=true,selection='',tick,active=null;const saved=new Map([['rf-refresh:overview',JSON.stringify({pace:4})]]),events={};
class Element{
 constructor(){this.hidden=false;this.isConnected=true;this.dataset={};this.listeners={};this.children=[];}
 getClientRects(){return this.hidden?[]:[{}]}
 append(...n){this.children.push(...n)} prepend(n){this.children.unshift(n)} before(){}
 setAttribute(k,v){this[k]=v} addEventListener(k,fn){this.listeners[k]=fn}
 querySelectorAll(){return []} querySelector(){return null}
}
const panels={overview:new Element(),nodes:new Element()};panels.nodes.hidden=true;
const document={hidden:false,get activeElement(){return active},getElementById:id=>panels[id.replace('dashboard-panel-','')]||null,querySelector:()=>null,createElement:()=>new Element(),addEventListener:(e,f)=>events[e]=f};
const window={getSelection:()=>({toString:()=>selection}),addEventListener(){}};
const context={window,document,navigator:{get onLine(){return online}},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},Date:class extends Date{static now(){return now}},console,setInterval:f=>{tick=f},setTimeout};
vm.runInNewContext(fs.readFileSync(process.argv[2]||'source/dashboard/static/refresh-controls.js','utf8'),context);
let calls=0,release;
window.RFRefresh.every('overview',async()=>{await window.RFRefresh.ready();calls++;},1000);
window.RFRefresh.every('nodes',async()=>{throw Error('Hidden page must not run');},1000);
const settle=()=>new Promise(r=>setImmediate(r));
(async()=>{
 tick();now+=1001;tick();await settle();assert.equal(calls,1);
 const bar=panels.overview.children[0],toggle=bar.children[0].children[0],manual=bar.children[2];
 assert.equal(bar.children.length,3);assert.equal(events.pointermove,undefined);
 toggle.checked=false;toggle.listeners.change();now+=2000;tick();assert.equal(calls,1);assert.equal(bar.dataset.state,'yellow');
 active={matches:()=>true,closest:()=>null};
 manual.listeners.click();await settle();assert.equal(calls,2);assert.match(bar.children[1].textContent,/Paused/);active=null;
 assert.deepEqual(JSON.parse(saved.get('rf-refresh:overview')),{paused:true});
 toggle.checked=true;toggle.listeners.change();tick();await settle();assert.equal(calls,3);
 active={matches:()=>true,closest:()=>null};now+=2000;tick();assert.equal(calls,3);active=null;
 selection='copied text';tick();assert.equal(calls,3);selection='';tick();await settle();assert.equal(calls,4);
 online=false;now+=2000;tick();assert.equal(calls,4);assert.equal(bar.dataset.state,'red');online=true;
 now+=1001;tick();await settle();assert.equal(calls,5);
 let pendingCalls=0;window.RFRefresh.every('overview',()=>{pendingCalls++;return new Promise(r=>release=r)},1000);now+=2000;tick();now+=2000;tick();assert.equal(pendingCalls,1);release();await settle();
 document.hidden=true;now+=20000;tick();assert.equal(pendingCalls,1);
 console.log('PASS: compact controls, pause persistence, legacy pace ignored, manual refresh bypasses editing wait, hidden/offline gating, editing/selection protection, no overlap.');
})();
