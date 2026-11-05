(function(){
  var b=document.body, burger=document.querySelector('.burger'), m=document.getElementById('mnav');
  function setMenu(open){b.classList.toggle('menu-open',open);burger.setAttribute('aria-expanded',open);m.setAttribute('aria-hidden',!open)}
  burger.addEventListener('click',function(){var o=!b.classList.contains('menu-open');setMenu(o);burger.setAttribute('aria-label',o?'Close menu':'Open menu')});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&b.classList.contains('menu-open')){setMenu(false);burger.focus()}});
  m.querySelectorAll('a').forEach(function(a){a.addEventListener('click',function(){setMenu(false)})});
  var mbar=document.querySelector('.mbar'),hero=document.querySelector('.hero');
  if(mbar&&hero&&'IntersectionObserver' in window){
    new IntersectionObserver(function(en){var x=en[0];mbar.classList.toggle('on',!x.isIntersecting&&x.boundingClientRect.top<0)}).observe(hero);
  } else if(mbar) mbar.classList.add('on');
  // live open/closed line (Mon-Sat 9-7, Corpus Christi time)
  var oh=document.querySelector('[data-hours]');
  if(oh&&window.Intl){try{
    var p={};new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',weekday:'short',hour:'numeric',minute:'numeric',hourCycle:'h23'}).formatToParts(new Date()).forEach(function(x){p[x.type]=x.value});
    var D=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],d=D.indexOf(p.weekday),t=(+p.hour%24)+(+p.minute)/60,openDay=d>=1&&d<=6,txt;
    var nextOpen=function(){var n=(d+1)%7;if(n===0)n=1;return n===(d+1)%7?'tomorrow':['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][n]};
    if(openDay&&t>=9&&t<19){txt='Open now until 7 PM'}
    else if(openDay&&t<9){txt='Opens today at 9 AM'}
    else{txt='Closed, opens '+nextOpen()+' 9 AM'}
    oh.querySelector('b').textContent=txt;
  }catch(e){}}
  var els=document.querySelectorAll('.rv');
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(en){en.forEach(function(x){if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},{rootMargin:'0px 0px -8% 0px'});
    els.forEach(function(e){io.observe(e)});
  } else els.forEach(function(e){e.classList.add('in')});
  (function(){
    var mq=matchMedia('(max-width:760px)'),still=matchMedia('(prefers-reduced-motion:reduce)');
    if(still.matches||!('IntersectionObserver' in window)) return;
    document.querySelectorAll('[data-drift]').forEach(function(row){
      var kids=[].slice.call(row.children);
      kids.forEach(function(k){var c=k.cloneNode(true);c.classList.add('is-clone');c.setAttribute('aria-hidden','true');c.querySelectorAll('a,button').forEach(function(a){a.tabIndex=-1});if(c.tagName==='A')c.tabIndex=-1;row.appendChild(c)});
      row.classList.add('drift');
      var dx=0,last=0,seen=false,held=false,timer=0,raf=0,SPEED=18;
      function period(){var c=row.querySelector('.is-clone');return c?c.offsetLeft-kids[0].offsetLeft:0}
      function setDx(v){dx=v;row.style.setProperty('--dx',v.toFixed(2))}
      function step(t){raf=0;if(!seen||held||!mq.matches){last=0;return}
        var dt=last?Math.min(50,t-last):0;last=t;var v=dx+SPEED*dt/1000,P=period();if(P>0&&v>=P)v-=P;setDx(v);raf=requestAnimationFrame(step)}
      function go(){if(!raf&&seen&&!held&&mq.matches){last=0;raf=requestAnimationFrame(step)}}
      function hold(){clearTimeout(timer);if(held)return;held=true;if(raf){cancelAnimationFrame(raf);raf=0}if(dx){var x=row.scrollLeft+dx;setDx(0);row.scrollLeft=x}}
      function release(){clearTimeout(timer);timer=setTimeout(function(){var P=period(),x=row.scrollLeft;if(P>0&&x>=P)x-=P;row.scrollLeft=0;setDx(x);held=false;go()},3500)}
      row.addEventListener('touchstart',hold,{passive:true});
      row.addEventListener('pointerdown',hold,{passive:true});
      row.addEventListener('wheel',function(){hold();release()},{passive:true});
      ['touchend','touchcancel','pointerup'].forEach(function(ev){row.addEventListener(ev,release,{passive:true})});
      row.addEventListener('scroll',function(){if(held)release()},{passive:true});
      new IntersectionObserver(function(en){seen=en[0].isIntersecting;if(seen)setTimeout(go,700)},{threshold:.3}).observe(row);
    });
  })();
  // Google reviews with text, 4 and 5 stars, verbatim (trimmed to whole sentences), scraped 10/22/26 (most relevant 150 of 1,770)
  var R=window.R||[];
  // the featured quote above the rows isn't repeated as a card
  var fc=document.querySelector('.quote-big cite'),fn=fc?fc.textContent.split(',')[0].trim():'';
  R=R.filter(function(r){return r.n!==fn});
  // last two words share a line, so a quote never ends on one lone word
  function glue(t){return t.replace(/ (\S{1,16})$/,' $1')}
  function esc(t){return t.replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function stars(n){var h='';for(var i=0;i<5;i++)h+='<svg class="st'+(i<n?'':' off')+'"><use href="#i-star"/></svg>';return h}
  function card(r){return '<figure class="rc"><span class="stars" role="img" aria-label="'+r.s+' out of 5 stars">'+stars(r.s)+'</span><p>&ldquo;'+esc(glue(r.t))+'&rdquo;</p><cite>'+(r.a?'<img class="av" src="'+r.a+'" alt="" width="40" height="40" loading="lazy" decoding="async">':'<span class="av" style="background:'+r.c+'" aria-hidden="true">'+esc(r.l)+'</span>')+'<span>'+esc(r.n)+', Google review</span></cite></figure>'}
  var half=Math.ceil(R.length/2),a=R.slice(0,half),c=R.slice(half);
  [['row1',a],['row2',c]].forEach(function(p){var el=document.getElementById(p[0]);if(!el||!p[1].length)return;var h=p[1].map(card).join('');el.innerHTML=h+h;el.querySelectorAll('figure').forEach(function(f,i){if(i>=p[1].length)f.setAttribute('aria-hidden','true')})});
})();

(function(){
  var f=document.getElementById('quoteWizard'); if(!f) return;
  var steps=f.querySelectorAll('.qw-step'), bar=f.querySelector('.qw-bar i'), cnt=f.querySelector('.qw-count b'), back=f.querySelector('.qw-back'), cur=1;
  var NEXT={
    'Buying a gun':['What kind?',['Handgun','Rifle','Shotgun','A special order']],
    'Suppressor':['What are you after?',['A suppressor','A short-barreled rifle','Both','Not sure yet']],
    'FFL transfer':['Where is it coming from?',['An online store','A private seller','Out of state','Not sure']],
    'Pawn loan':['What is the item?',['A firearm','Jewelry or gold','Something else']],
    'Selling a gun':['What kind?',['Handgun','Rifle','Shotgun','More than one']]
  };
  function go(n){cur=n;steps.forEach(function(s){s.classList.toggle('is-on',+s.dataset.step===n)});bar.style.width=(n*25)+'%';cnt.textContent=n;back.hidden=n===1;
    if(n>1&&window.innerWidth<761){f.scrollIntoView({behavior:'smooth',block:'start'})}}
  function pick(btn){var fld=btn.dataset.field;f.querySelectorAll('.qw-opt[data-field="'+fld+'"]').forEach(function(b){b.classList.toggle('is-picked',b===btn)});f.elements[fld].value=btn.dataset.value}
  function buildStep2(item){var s=f.querySelector('[data-step="2"]'),q=s.querySelector('[data-q]'),o=s.querySelector('[data-opts]'),els=s.querySelectorAll('.qw-else');o.innerHTML='';f.elements.need.value='';
    if(NEXT[item]){q.textContent=NEXT[item][0];NEXT[item][1].forEach(function(v,i,a){var b=document.createElement('button');b.type='button';b.className='qw-opt'+(a.length%2&&i===a.length-1?' qw-wide':'');b.dataset.field='need';b.dataset.value=v;b.textContent=v;o.appendChild(b)});o.hidden=false;els.forEach(function(e){e.hidden=true})}
    else{q.textContent='What can we help with?';o.hidden=true;els.forEach(function(e){e.hidden=false})}}
  f.addEventListener('click',function(e){
    var b=e.target.closest('.qw-opt');
    if(b){pick(b);if(b.dataset.field==='item'){buildStep2(b.dataset.value)}setTimeout(function(){go(cur+1)},230);return}
    if(e.target.closest('.qw-back')){go(cur-1);return}
    if(e.target.closest('.qw-next')){
      if(cur===3){var ph=f.elements.phone.value.replace(/\D/g,'').replace(/^1(?=\d{10}$)/,''),err=f.querySelector('.qw-err');err.hidden=ph.length===10;if(ph.length!==10){f.elements.phone.focus();return}}
      go(cur+1)}
  });
  f.addEventListener('keydown',function(e){if(e.key==='Enter'&&e.target.tagName==='INPUT'){e.preventDefault();var n=f.querySelector('.qw-step.is-on .qw-next');if(n)n.click()}});
  var file=f.querySelector('input[type=file]'),th=f.querySelector('.qw-thumbs');
  file.addEventListener('change',function(){th.innerHTML='';[].slice.call(file.files,0,6).forEach(function(x){var i=document.createElement('img');i.src=URL.createObjectURL(x);i.alt='';th.appendChild(i)});f.querySelector('.qw-drop b').textContent=file.files.length?file.files.length+' photo'+(file.files.length>1?'s':'')+' added':'Add photos'});
  f.addEventListener('submit',function(e){e.preventDefault();var nm=f.elements.name.value.trim().split(' ')[0];if(nm)f.querySelector('[data-name]').textContent=nm;
    steps.forEach(function(s){s.classList.remove('is-on')});f.querySelector('.qw-top').hidden=true;f.querySelector('.qw-bar').hidden=true;back.hidden=true;f.querySelector('.qw-done').hidden=false});
})();
