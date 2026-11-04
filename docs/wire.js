
(function(){
 var root=document.documentElement;
 function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
 function set(k,v){try{localStorage.setItem(k,v)}catch(e){}}
 function getJ(k){try{return JSON.parse(get(k))||{}}catch(e){return {}}}
 var theme=get('wire.theme');if(theme)root.setAttribute('data-theme',theme);

 // ---- times: shown in the reader's own clock, kept fresh between rebuilds
 function clock(d){return d.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})}
 function ago(d){var m=Math.round((Date.now()-d)/60000);
   if(m<1)return 'just now'; if(m<60)return m+' min ago';
   var h=Math.floor(m/60); if(h<24)return h+' hr ago';
   return Math.floor(h/24)+' d ago'}
 function tick(){document.querySelectorAll('time[datetime]').forEach(function(t){
   var d=new Date(t.getAttribute('datetime')); if(isNaN(d))return;
   var mode=t.dataset.mode;
   if(mode==='ago'){t.textContent=ago(d);return}
   if(mode==='clock'){t.textContent=clock(d);return}
   var day=(Date.now()-d)>20*3600000?d.toLocaleDateString([], {month:'short',day:'numeric'})+' ':'';
   t.innerHTML=day+clock(d)+'<small>'+ago(d)+'</small>'})}
 tick(); setInterval(tick,30000);

 // ---- read state
 var read=getJ('wire.read');
 function markRead(){document.querySelectorAll('li[data-id]').forEach(function(li){
   if(read[li.dataset.id])li.classList.add('read')})}
 document.addEventListener('click',function(e){
   var a=e.target.closest('a.hl'); if(!a)return; var li=a.closest('li[data-id]');
   if(li){read[li.dataset.id]=Date.now();li.classList.add('read');
     var keep={},cut=Date.now()-5*86400000;
     for(var k in read)if(read[k]>cut)keep[k]=read[k];
     read=keep;set('wire.read',JSON.stringify(read))}
 });
 markRead();

 // ---- since you last looked
 var box=document.getElementById('since');
 if(box){
   var last=parseInt(get('wire.lastSeen')||'0',10), fresh=0, firstVisit=!last;
   document.querySelectorAll('.log li[data-first]').forEach(function(li){
     var t=Date.parse(li.dataset.first); if(last&&t>last){li.classList.add('new');fresh++}});
   if(fresh){box.querySelector('b').textContent=fresh+(fresh===1?' new story':' new stories');
     box.querySelector('span').textContent=' since '+clock(new Date(last));box.classList.add('on')}
   var stampNow=function(){set('wire.lastSeen',String(Date.now()))};
   if(firstVisit)stampNow();
   box.querySelector('button').addEventListener('click',function(){
     stampNow();box.classList.remove('on');
     document.querySelectorAll('li.new').forEach(function(li){li.classList.remove('new')})});
   // Leaving the page counts as having looked.
   document.addEventListener('visibilitychange',function(){if(document.hidden)stampNow()});
   window.addEventListener('pagehide',stampNow);
 }

 // ---- topic + search filters
 var topic=get('wire.topic')||'all', query='';
 var tabs=document.querySelectorAll('.topics button');
 function apply(){
   tabs.forEach(function(b){b.setAttribute('aria-pressed',b.dataset.topic===topic?'true':'false')});
   document.querySelectorAll('.lane').forEach(function(lane){
     var shown=0, cap=parseInt(lane.dataset.cap||'999',10);
     lane.querySelectorAll('li[data-id]').forEach(function(li){
       var ok=(topic==='all'||(' '+li.dataset.tags+' ').indexOf(' '+topic+' ')>-1)
         &&(!query||li.dataset.q.indexOf(query)>-1);
       if(ok&&shown<cap){li.hidden=false;shown++}else li.hidden=true});
     var empty=lane.querySelector('.empty-filter'); if(empty)empty.hidden=shown>0;
     if(lane.dataset.optional&&topic!=='all'&&!query)lane.hidden=shown===0;
   })}
 tabs.forEach(function(b){b.addEventListener('click',function(){
   topic=b.dataset.topic;set('wire.topic',topic);apply();if(window.wireNowDraw)window.wireNowDraw()})});
 var q=document.getElementById('q');
 if(q){q.addEventListener('input',function(){query=q.value.trim().toLowerCase();apply()});
   document.addEventListener('keydown',function(e){
     if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus()}
     if(e.key==='Escape'&&document.activeElement===q){q.value='';query='';apply();q.blur()}})}
 if(tabs.length)apply();

 var hr=document.getElementById('hide-read');
 if(hr){var on=get('wire.hideRead')==='1';
   var show=function(){document.body.classList.toggle('hide-read',on);hr.setAttribute('aria-pressed',on?'true':'false')};
   show();hr.addEventListener('click',function(){on=!on;set('wire.hideRead',on?'1':'0');show()})}

 var th=document.getElementById('theme');
 if(th)th.addEventListener('click',function(){
   var dark=root.getAttribute('data-theme')==='dark'||(!root.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);
   var next=dark?'light':'dark';root.setAttribute('data-theme',next);set('wire.theme',next)});

 // ---- right now: newsroom posts fetched live from Bluesky, every minute
 var nowList=document.getElementById('nowlist');
 if(nowList&&window.WIRE_LIVE&&window.fetch){
   var accts=window.WIRE_LIVE, posts={}, expanded=false, reached=0;
   function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
   function clean(t){t=t.replace(/(https?:\/\/\S+|\b[a-z0-9-]+\.[a-z]{2,6}\/\S+)/gi,'').replace(/\s{2,}/g,' ').trim();
     return t.length>220?t.slice(0,217).replace(/\s\S*$/,'')+'…':t}
   function pull(a){
     return fetch('https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor='+encodeURIComponent(a.handle)+'&limit=15&filter=posts_no_replies')
      .then(function(r){if(r.ok)reached++;return r.ok?r.json():{feed:[]}}).then(function(j){
        (j.feed||[]).forEach(function(it){
          if(it.reason)return; var p=it.post||{}, rec=p.record||{};
          var text=clean(rec.text||''); if(text.length<25)return;
          var rkey=(p.uri||'').split('/').pop();
          var ext=p.embed&&p.embed.external&&p.embed.external.uri;
          posts[p.uri]={t:Date.parse(rec.createdAt||p.indexedAt), text:text, who:a.name, tags:a.tags||[],
            url:ext||('https://bsky.app/profile/'+a.handle+'/post/'+rkey)};
        })}).catch(function(){})}
   function draw(){
     var cut=Date.now()-3*3600000, list=Object.keys(posts).map(function(k){return posts[k]})
       .filter(function(p){return p.t>cut&&p.t<Date.now()+120000})
       .filter(function(p){return topic==='all'||p.tags.indexOf(topic)>-1})
       .sort(function(a,b){return b.t-a.t});
     var few=window.innerWidth<700?5:8, show=expanded?list.slice(0,40):list.slice(0,few);
     if(!reached){nowList.innerHTML='<li class="empty">Couldn\'t reach the newsroom accounts just now. Trying again every minute.</li>';return}
     if(!list.length){nowList.innerHTML='<li class="empty">No newsroom posts in the last three hours'+(topic!=='all'?' for this topic':'')+'.</li>';return}
     nowList.innerHTML=show.map(function(p){var m=Math.round((Date.now()-p.t)/60000);
       return '<li><span class="t'+(m>30?' old':'')+'">'+(m<1?'now':m<60?m+' min':Math.floor(m/60)+' hr')+'</span><div>'
        +'<a class="post" href="'+esc(p.url)+'" target="_blank" rel="noopener">'+esc(p.text)+'</a>'
        +'<div class="who">'+esc(p.who)+'</div></div></li>'}).join('')
       +(list.length>few?'<li class="more-now"><button type="button">'+(expanded?'Show fewer':'Show '+Math.min(list.length,40)+' posts')+'</button></li>':'');
     var b=nowList.querySelector('.more-now button'); if(b)b.onclick=function(){expanded=!expanded;draw()};
   }
   function refresh(){Promise.all(accts.map(pull)).then(draw)}
   refresh(); setInterval(function(){if(!document.hidden)refresh()},60000);
   document.addEventListener('visibilitychange',function(){if(!document.hidden)refresh()});
   window.wireNowDraw=draw;
 }

 // ---- quietly pick up new rebuilds (never while you're typing or mid-scroll)
 var loaded=Date.now(), busy=0;
 window.addEventListener('scroll',function(){busy=Date.now()},{passive:true});
 setInterval(function(){
   if(!document.body.dataset.live)return;
   if(Date.now()-loaded<5*60000)return;
   if(document.activeElement===q)return;
   if(document.hidden||(window.scrollY<200&&Date.now()-busy>60000))location.reload();
 },60000);
})();
