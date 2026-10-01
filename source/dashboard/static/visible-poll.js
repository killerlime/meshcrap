/* Only refresh displayed features; return immediately when reopened. */
(() => {
  const tasks = [];
  function visible(task) {
    const element = document.getElementById(task.id);
    return !document.hidden && element && element.getClientRects().length > 0 && task.enabled();
  }
  async function run(task) {
    if (task.busy || !visible(task)) return;
    task.busy = true;
    try { await task.load(); }
    catch (error) { console.error('Refresh failed', task.id, error); }
    finally { task.busy = false; }
  }
  function assess() {
    for (const task of tasks) {
      const shown = Boolean(visible(task));
      if (shown && !task.shown) run(task);
      task.shown = shown;
    }
  }
  window.MeshcrapPoll = {watch(id, load, interval, enabled = () => true) {
    const task = {id, load, enabled, busy:false, shown:false};
    tasks.push(task);
    setInterval(() => run(task), interval);
    if (document.readyState !== 'loading') assess();
  }};
  function start() {
    new MutationObserver(assess).observe(document.body, {subtree:true, attributes:true, attributeFilter:['hidden','class','style']});
    assess();
  }
  document.addEventListener('visibilitychange', assess);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
