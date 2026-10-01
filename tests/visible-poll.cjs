const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert');
const listeners={},timers=[];let observe,shown=false,calls=0,release;
const document={hidden:false,readyState:'complete',body:{},getElementById:()=>({getClientRects:()=>shown?[1]:[]}),addEventListener:(n,f)=>listeners[n]=f};
const context={window:{},document,console,setInterval:f=>timers.push(f),MutationObserver:class{constructor(f){observe=f}observe(){}}};
vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../source/dashboard/static/visible-poll.js'),'utf8'),context);
const settle=()=>new Promise(r=>setImmediate(r));
(async()=>{
 context.window.MeshcrapPoll.watch('test',async()=>{calls++;await new Promise(r=>release=r)},3000);
 timers[0]();assert.equal(calls,0);
 shown=true;observe();assert.equal(calls,1);timers[0]();assert.equal(calls,1);
 release();await settle();document.hidden=true;listeners.visibilitychange();timers[0]();assert.equal(calls,1);
 document.hidden=false;listeners.visibilitychange();assert.equal(calls,2);release();await settle();
 shown=false;observe();timers[0]();assert.equal(calls,2);
 console.log('PASS: hidden feature suppression, immediate reopen and overlapping-request prevention');
})().catch(error=>{console.error(error);process.exitCode=1});
