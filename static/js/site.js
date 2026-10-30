document.addEventListener('DOMContentLoaded',()=>{
 const toggle=document.querySelector('.menu-toggle');const nav=document.querySelector('.nav');
 if(toggle&&nav)toggle.addEventListener('click',()=>{const open=nav.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));});
 document.querySelectorAll('form[data-confirm]').forEach(f=>f.addEventListener('submit',e=>{if(!window.confirm(f.dataset.confirm))e.preventDefault();}));
 document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
 document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText(b.dataset.copy);b.textContent='복사 완료 ✓';}catch(e){window.prompt('복사할 이미지 경로',b.dataset.copy);}
 }));
});
