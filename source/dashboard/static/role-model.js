/* Candidate replay only; excludes own transmissions and never configures a radio.
   Role definitions: https://meshtastic.org/docs/configuration/radio/device/
   Cancellation rules: meshtastic/firmware src/mesh/FloodingRouter.cpp */
((root)=>{
 const roles={
  CLIENT:{kind:'client',description:'General messaging; may cancel a queued relay after hearing another relay.'},
  CLIENT_BASE:{kind:'base',description:'Keeps relays for favorites; other traffic follows CLIENT behavior.'},
  CLIENT_MUTE:{kind:'mute',description:'Does not relay other nodes’ packets. Its own traffic is separate.'},
  ROUTER:{kind:'router',description:'Earlier infrastructure forwarding. Connection and power defaults may change.'},
  ROUTER_LATE:{kind:'router',description:'Later infrastructure forwarding. Timing differs from ROUTER.'},
  CLIENT_HIDDEN:{kind:'client',local:true,description:'Reduces routine broadcasts; forwards only local-channel traffic.'},
  TRACKER:{kind:'client',awake:true,description:'Prioritizes position reports. Sleeping periods can prevent reception.'},
  SENSOR:{kind:'client',awake:true,description:'Prioritizes sensor telemetry. Sleeping periods can prevent reception.'},
  TAK:{kind:'client',description:'Favors ATAK communication; changes routine originating traffic.'},
  TAK_TRACKER:{kind:'client',awake:true,description:'Generates TAK position reports; forwarding also depends on configuration.'},
  LOST_AND_FOUND:{kind:'client',description:'Sends periodic recovery-location messages.'},
  REPEATER:{kind:'legacy',description:'Deprecated since 2.7.11. Legacy forwarding behavior is not estimated for HQ’s current firmware.'},
  ROUTER_CLIENT:{kind:'legacy',description:'Deprecated since 2.3.15. Legacy forwarding behavior is not estimated for HQ’s current firmware.'}
 };
 function estimate(role,counts,options){
  const spec=roles[role];if(!spec||spec.kind==='legacy')return null;
  const c=Math.max(0,Number(counts.candidates)||0),n=Math.min(c,Math.max(0,Number(counts.affected)||0)),f=c-n;
  const {cancel,seconds,awake=100,local=100}=options;
  if(![cancel,seconds,awake,local].every(Number.isFinite)||cancel<0||cancel>100||seconds<.05||seconds>5||awake<0||awake>100||local<0||local>100)return null;
  const p=cancel/100,baseline=f+n*(1-p);
  let target=spec.kind==='mute'?0:spec.kind==='router'?c:spec.kind==='base'?baseline:c*(1-p);
  if(spec.awake)target*=awake/100;if(spec.local)target*=local/100;
  const delta=target-baseline;
  return {baseline,target,delta,minutes:delta*seconds/60};
 }
 const api={roles,estimate};if(typeof module==='object'&&module.exports)module.exports=api;else root.RFRoleModel=api;
})(typeof window==='object'?window:globalThis);
