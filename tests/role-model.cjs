const assert=require('node:assert/strict');const {roles,estimate}=require('../source/dashboard/static/role-model.js');
const counts={candidates:100,affected:80},options={cancel:50,seconds:.4,awake:100,local:100};
assert.equal(Object.keys(roles).length,13);
assert.equal(estimate('CLIENT_BASE',counts,options).delta,0);
assert.equal(estimate('CLIENT',counts,options).delta,-10);
assert.equal(estimate('CLIENT_MUTE',counts,options).target,0);
assert.equal(estimate('CLIENT_MUTE',counts,options).delta,-60);
for(const role of ['ROUTER','ROUTER_LATE'])assert.equal(estimate(role,counts,options).delta,40);
assert.equal(estimate('TRACKER',counts,{...options,awake:20}).target,10);
assert.equal(estimate('CLIENT_HIDDEN',counts,{...options,local:40}).target,20);
for(const role of ['TAK','TAK_TRACKER','SENSOR','LOST_AND_FOUND'])assert.equal(estimate(role,counts,options).target,50);
for(const role of ['REPEATER','ROUTER_CLIENT','invalid'])assert.equal(estimate(role,counts,options),null);
assert.equal(estimate('CLIENT',counts,{...options,seconds:NaN}),null);
assert.equal(estimate('CLIENT',counts,{...options,awake:101}),null);
for(const role of Object.keys(roles)){if(roles[role].kind==='legacy')continue;for(const cancel of [0,100]){const v=estimate(role,counts,{...options,cancel});assert.ok(v.target>=0&&v.target<=100);}}
console.log('PASS: all 13 role choices, signed baseline differences, conditional awake/local shares, deprecated roles, bounds and invalid input.');
