const assert=require('node:assert/strict');
const {simulate,firmwareScenario}=require('../source/dashboard/static/traffic-simulator.js');
assert.deepEqual(simulate([{count:100,reduction:50}],200,.5,1),{before:200,removed:50,after:150,percent:25,airtimeSeconds:50});
const nodes=[{total:120,reports:{position:60,device:40}}];
let r=firmwareScenario(nodes,{device:50},1,{enabled:false});assert.equal(r[0].telemetry,100);assert.equal(r[0].combined,100);
r=firmwareScenario(nodes,{device:100,position:100},1,{enabled:true,interval:3600,stationary:100,cache:100,window:60,max:1});assert.equal(r[0].combined,20); // non-report traffic is protected
r=firmwareScenario(nodes,{},1,{enabled:true,interval:3600,stationary:100,cache:0,window:0,max:0});assert.equal(r[0].positionSaved,59);assert.equal(r[0].combined,61);
assert.equal(firmwareScenario([],{},{},{}).length,0);
r=firmwareScenario([{total:100,reports:{nodeinfo:100}}],{nodeinfo:50},1,{enabled:true,interval:0,stationary:0,cache:50,window:0,max:0});assert.equal(r[0].combined,25); // no double counting combined effects
console.log('Traffic simulation tests passed.');
