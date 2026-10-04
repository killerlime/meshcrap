(() => {
 function init(){
  const select=document.getElementById('coverageArea'),nav=document.getElementById('coverageAreaNav'),map=document.getElementById('meshmap');
  if(!select||!map)return;
  const picker=select.closest('section'),summary=picker.closest('.card'),mapCard=map.closest('.card');
  summary.before(mapCard);mapCard.querySelector('h2').after(picker);
  picker.classList.add("coverage-area-picker");picker.removeAttribute("style");if(nav)nav.hidden=true;select.hidden=false;
  const label=document.querySelector('label[for="coverageArea"]');if(label){label.hidden=false;label.textContent='Grid overlay ';}
  const heading=picker.querySelector('h3');if(heading)heading.hidden=true;
  document.getElementById('dashboard-panel-map').classList.remove('western-theme');
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
