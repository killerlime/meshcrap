/** LNA state annotations for the existing Chart.js category timelines. */
(() => {
  let transitions = [];
  /** Map an exact switch time into the chart's existing sample-index scale. */
  function indexAt(times, time) {
    if (!times.length || !Number.isFinite(time)) return null;
    if (time < times[0] || time > times[times.length - 1]) return null;
    for (let i = 0; i < times.length; i++) {
      if (time === times[i]) return i;
      if (time < times[i]) return i - 1 + (time - times[i - 1]) / (times[i] - times[i - 1]);
    }
    return null;
  }
  const plugin = {
    id: 'lnaSwitches',
    beforeDatasetsDraw(chart, args, options) {
      const times = (options.timestamps || []).map(t => Date.parse(t));
      if (!times.length || times.some(t => !Number.isFinite(t)) || !chart.chartArea) return;
      const {ctx, chartArea:area, scales:{x}} = chart;
      const visible = transitions.filter(t => t.time >= times[0] && t.time <= times.at(-1));
      let prior = transitions.filter(t => t.time <= times[0]).at(-1);
      let left = area.left;
      ctx.save();
      ctx.beginPath();ctx.rect(area.left,area.top,area.right-area.left,area.bottom-area.top);ctx.clip();
      for (const t of [...visible, {time:times.at(-1),end:true}]) {
        const right = t.end ? area.right : x.getPixelForValue(indexAt(times,t.time));
        if (prior) {
          ctx.fillStyle = prior.state === 'ON' ? 'rgba(103,234,148,0.08)' : 'rgba(242,201,76,0.08)';
          ctx.fillRect(left,area.top,right-left,area.bottom-area.top);
        }
        prior=t;left=right;
      }
      ctx.restore();
    },
    afterDatasetsDraw(chart, args, options) {
      const times=(options.timestamps || []).map(t=>Date.parse(t));
      if (!times.length || times.some(t=>!Number.isFinite(t)) || !chart.chartArea) return;
      const {ctx,chartArea:a,scales:{x}}=chart;
      let row=0;
      ctx.save();
      for (const t of transitions) {
        const index=indexAt(times,t.time);if(index===null)continue;
        const px=x.getPixelForValue(index),color=t.state==='ON'?'#67ea94':'#f2c94c';
        ctx.strokeStyle=color;ctx.lineWidth=2;ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(px,a.top);ctx.lineTo(px,a.bottom);ctx.stroke();
        ctx.setLineDash([]);ctx.font='bold 11px sans-serif';
        const text='LNA '+t.state+(t.initial?' · start':'');
        const width=ctx.measureText(text).width+8,tx=Math.max(a.left,Math.min(px+4,a.right-width)),ty=a.top+4+(row++%3)*17;
        ctx.fillStyle='#172019';ctx.fillRect(tx,ty,width,15);ctx.fillStyle=color;ctx.textBaseline='top';ctx.fillText(text,tx+4,ty+2);
      }
      ctx.restore();
    }
  };
  /** Accept recorded history; ignore malformed entries and repeated same-state records. */
  function update(records) {
    transitions=[];
    for (const r of [...records].sort((a,b)=>Date.parse(a.time_utc)-Date.parse(b.time_utc))) {
      const time=Date.parse(r.time_utc);
      if (!Number.isFinite(time) || !['ON','OFF'].includes(r.state) || transitions.at(-1)?.state===r.state) continue;
      transitions.push({time,state:r.state,initial:transitions.length===0});
    }
    for (const chart of Object.values(Chart.instances)) {
      if (chart.options.plugins.lnaSwitches?.timestamps) chart.draw();
    }
    let legend=document.getElementById('lnaSwitchLegend');
    const note=document.getElementById('rfHealthHourlyNote');
    if (!legend && note) {legend=document.createElement('p');legend.id='lnaSwitchLegend';legend.className='muted';note.after(legend);}
    if (legend) legend.textContent='Graph markers: green = LNA ON; amber = LNA OFF. Dashed lines mark recorded changes; shaded areas show state. '+transitions.slice(-8).map(t=>`${t.initial?'Start':'Switch'} ${new Date(t.time).toLocaleString()} → ${t.state}`).join(' · ');
  }
  Chart.register(plugin);
  window.LnaSwitches={update,indexAt};
})();
