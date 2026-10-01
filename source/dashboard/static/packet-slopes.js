/* Original Meshcrap game and procedural artwork, under the repository Unlicense. */
(() => {
  'use strict';
  const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
  const score=document.getElementById('score'),status=document.getElementById('status');
  const start=document.getElementById('start'),pause=document.getElementById('pause');
  const keys=new Set(),pointers=new Map();
  let x=240,distance=0,rings=0,mittens=3,objects=[],running=false,started=false,frame=0,last=0,spawn=0,invincible=0,displaySecond=-1;
  const announce=text=>{status.textContent=text;};
  function hud(){score.textContent=`${Math.floor(distance)} m · ${rings} packets · ${mittens} signal bars`;const hop=rings%3;document.getElementById('route').textContent=`YOU ● — ${hop>=1?'●':'○'} RIDGE — ${hop>=2?'●':'○'} VALLEY — ○ BASE · ${Math.floor(rings/3)} delivered`;}
  function draw(){
    ctx.fillStyle='#e7f4f6';ctx.fillRect(0,0,480,600);
    ctx.strokeStyle='#c3e1e6';ctx.lineWidth=3;
    for(let i=0;i<9;i++){const y=(i*90+distance*3)%720-60;ctx.beginPath();ctx.moveTo(0,y);ctx.quadraticCurveTo(240,y+60,480,y);ctx.stroke();}
    for(const o of objects){
      if(o.kind==='ring'){ctx.strokeStyle='#b87500';ctx.lineWidth=5;ctx.beginPath();ctx.arc(o.x,o.y,13,0,Math.PI*2);ctx.stroke();ctx.strokeStyle='#ffcf55';ctx.lineWidth=2;ctx.beginPath();ctx.arc(o.x,o.y,20,0,Math.PI*2);ctx.stroke();ctx.fillStyle='#754d00';ctx.fillRect(o.x-5,o.y-4,10,8);}
      else if(o.kind==='pony'){
        ctx.save();ctx.translate(o.x,o.y);ctx.fillStyle='#f26ac5';ctx.beginPath();ctx.ellipse(0,0,18,11,0,0,Math.PI*2);ctx.fill();ctx.fillRect(7,-18,9,20);ctx.beginPath();ctx.ellipse(15,-20,11,7,-0.3,0,Math.PI*2);ctx.fill();ctx.beginPath();ctx.moveTo(11,-24);ctx.lineTo(10,-33);ctx.lineTo(17,-25);ctx.fill();
        ctx.strokeStyle='#bd3d9d';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(-11,5);ctx.lineTo(-13,20);ctx.moveTo(10,5);ctx.lineTo(13,20);ctx.moveTo(-16,-3);ctx.quadraticCurveTo(-29,-18,-26,4);ctx.stroke();ctx.fillStyle='#3b194d';ctx.fillRect(18,-22,3,3);
        ctx.strokeStyle='#ad7400';ctx.lineWidth=2;for(const [sx,sy] of [[-26,-22],[29,-7],[0,28]]){ctx.beginPath();ctx.moveTo(sx-4,sy);ctx.lineTo(sx+4,sy);ctx.moveTo(sx,sy-5);ctx.lineTo(sx,sy+5);ctx.stroke();}ctx.restore();
      }
      else{ctx.fillStyle='#b9d4da';ctx.beginPath();ctx.ellipse(o.x+8,o.y+19,23,7,0,0,Math.PI*2);ctx.fill();ctx.fillStyle='#6b4938';ctx.fillRect(o.x-4,o.y,8,22);ctx.fillStyle='#236858';ctx.beginPath();ctx.moveTo(o.x,o.y-30);ctx.lineTo(o.x-22,o.y+12);ctx.lineTo(o.x+22,o.y+12);ctx.closePath();ctx.fill();ctx.fillStyle='#fff';ctx.beginPath();ctx.moveTo(o.x,o.y-30);ctx.lineTo(o.x-8,o.y-14);ctx.lineTo(o.x+8,o.y-14);ctx.fill();}
    }
    ctx.save();ctx.translate(x,450);ctx.globalAlpha=invincible>0?0.55:1;
    ctx.strokeStyle='#263e61';ctx.lineWidth=5;
    for(const dx of [-9,9]){ctx.beginPath();ctx.moveTo(dx,-6);ctx.lineTo(dx+4,29);ctx.stroke();}
    ctx.fillStyle='#ee6b4d';ctx.fillRect(-11,-14,22,26);ctx.fillStyle='#ffdca5';ctx.beginPath();ctx.arc(0,-20,9,0,Math.PI*2);ctx.fill();ctx.fillStyle='#166c94';ctx.fillRect(-10,-29,20,8);
    ctx.strokeStyle='#166c94';ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(-10,-4);ctx.lineTo(-25,12);ctx.moveTo(10,-4);ctx.lineTo(25,12);ctx.stroke();
    ctx.fillStyle='#102638';ctx.fillRect(-7,-10,14,16);ctx.fillStyle='#76f0d0';ctx.fillRect(-4,-6,8,5);ctx.strokeStyle='#102638';ctx.beginPath();ctx.moveTo(6,-10);ctx.lineTo(10,-36);ctx.stroke();
    ctx.strokeStyle='#16786f';ctx.lineWidth=2;ctx.beginPath();ctx.arc(10,-36,9,-1,0.6);ctx.stroke();ctx.beginPath();ctx.arc(10,-36,15,-1,0.6);ctx.stroke();ctx.restore();
  }
  function halt(message){running=false;cancelAnimationFrame(frame);frame=0;keys.clear();pointers.clear();pause.textContent='Resume';announce(message);}
  function tick(now){
    if(!running)return;
    const dt=Math.min((now-last)/1000,0.05);last=now;
    const left=keys.has('ArrowLeft')||[...pointers.values()].includes(-1),right=keys.has('ArrowRight')||[...pointers.values()].includes(1);
    x=Math.max(24,Math.min(456,x+(Number(right)-Number(left))*280*dt));
    const speed=Math.min(260,130+distance/12);distance+=speed*dt/8;invincible=Math.max(0,invincible-dt);spawn-=dt;
    if(spawn<=0){const roll=Math.random();objects.push({x:30+Math.random()*420,y:-35,kind:roll<0.1?'pony':roll<0.48?'ring':'tree'});spawn=0.65;}
    for(const o of objects){o.y+=speed*dt;if(Math.abs(o.x-x)<(o.kind==='ring'?24:27)&&Math.abs(o.y-450)<25&&!o.hit){
      o.hit=true;if(o.kind==='ring'){rings++;o.y=700;announce(rings%3===0?'Packet chain delivered to base!':'Packet caught. Next relay ahead!');}else if(o.kind==='pony'){mittens=Math.min(3,mittens+1);o.y=700;announce('Sparkly pony courier! Signal boosted.');}else if(invincible===0){mittens--;invincible=1.5;announce('Interference! Lost one signal bar.');}
    }}
    objects=objects.filter(o=>o.y<650);draw();
    if(Math.floor(distance)!==displaySecond){displaySecond=Math.floor(distance);hud();}
    if(mittens<=0){hud();halt(`Out of signal! ${Math.floor(rings/3)} relay chains delivered over ${Math.floor(distance)} metres. Try again!`);started=false;pause.disabled=true;start.textContent='Ski again';return;}
    frame=requestAnimationFrame(tick);
  }
  function resume(){if(!started||document.hidden)return;running=true;last=performance.now();pause.textContent='Pause';announce('Collect packets. Every three completes a relay chain.');frame=requestAnimationFrame(tick);}
  start.onclick=()=>{halt('');x=240;distance=0;rings=0;mittens=3;objects=[];spawn=0;invincible=0;started=true;pause.disabled=false;start.textContent='Restart';hud();resume();canvas.focus();};
  pause.onclick=()=>{if(running)halt('Paused. Press Resume when ready.');else resume();};
  document.addEventListener('keydown',e=>{if(!started||e.altKey||e.ctrlKey||e.metaKey)return;
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();keys.add(e.key);}
    if(e.code==='Space'&&e.target===canvas&&!e.repeat){e.preventDefault();pause.click();}
    if(e.key==='Escape'&&running){e.preventDefault();halt('Paused. Use Close snow day above to return.');}
  });
  document.addEventListener('keyup',e=>keys.delete(e.key));
  for(const [id,direction] of [['left',-1],['right',1]]){const button=document.getElementById(id);
    button.addEventListener('pointerdown',e=>{e.preventDefault();if(!running)return;pointers.set(e.pointerId,direction);button.setPointerCapture(e.pointerId);});
    for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,e=>pointers.delete(e.pointerId));
  }
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&running)halt('Paused while away.');});
  window.addEventListener('blur',()=>{if(running)halt('Paused while away.');});
  window.addEventListener('pagehide',()=>halt(''));
  hud();draw();
})();
