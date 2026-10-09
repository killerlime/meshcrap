const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('source/dashboard/static/recovery-client.js','utf8');
(async()=>{
 const responses=[{ok:false,status:304},{ok:false,status:503},{ok:true,status:200}];let calls=0;
 const ctx={window:{fetch:async()=>{calls++;return responses.shift();}},location:new URL('http://localhost/'),URL,Request,AbortController,setTimeout,clearTimeout};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 assert.equal((await ctx.window.fetch('/api/explorer/nodes')).status,304);
 await assert.rejects(ctx.window.fetch('/api/summary'),/503/);
 assert.equal((await ctx.window.fetch('/api/control',{method:'POST'})).status,200);
 assert.equal(calls,3,'requests must not be replayed');
 console.log('PASS: conditional 304 reads succeed, genuine errors surface, and actions are not retried');
})().catch(e=>{console.error(e);process.exitCode=1;});
