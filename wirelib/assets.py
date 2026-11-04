"""Styles and behaviour for every page. Plain CSS and a little JavaScript."""

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Public+Sans:wght@400;500;600;700&'
    'family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap">'
)

CSS = r"""
:root{
  --paper:#ffffff; --ink:#16191d; --ink-2:#4d5561; --ink-3:#7f8792; --rule:#e4e7eb;
  --wash:#f3f5f7; --link:#16191d;
  --spotted:#8a929d; --spreading:#d9431a; --confirmed:#11795a; --changed:#a8610b;
  --serif:"Source Serif 4",Georgia,"Times New Roman",serif;
  --sans:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#121519; --ink:#e8ebee; --ink-2:#a9b1bb; --ink-3:#737c87; --rule:#262b31;
  --wash:#191d22; --link:#e8ebee;
  --spotted:#8a929d; --spreading:#ff6a3d; --confirmed:#35b884; --changed:#e5a04a;
  color-scheme:dark;
}}
:root[data-theme="dark"]{
  --paper:#121519; --ink:#e8ebee; --ink-2:#a9b1bb; --ink-3:#737c87; --rule:#262b31;
  --wash:#191d22; --link:#e8ebee;
  --spotted:#8a929d; --spreading:#ff6a3d; --confirmed:#35b884; --changed:#e5a04a;
  color-scheme:dark;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 var(--sans);
  font-feature-settings:"tnum" 1;-webkit-font-smoothing:antialiased}
a{color:var(--link);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:1px}
:focus-visible{outline:2px solid var(--spreading);outline-offset:2px;border-radius:2px}
.page{max-width:1240px;margin:0 auto;padding:0 24px}
@media (max-width:640px){.page{padding:0 16px}}

/* ---------- masthead ---------- */
.top{display:flex;align-items:baseline;gap:24px;padding:22px 0 14px;flex-wrap:wrap}
.wordmark{font:700 30px/1 var(--serif);letter-spacing:-.02em;margin:0}
.wordmark a{text-decoration:none}
.wordmark .live{display:inline-block;width:9px;height:9px;border-radius:50%;
  background:var(--spreading);margin:0 0 4px 8px;vertical-align:middle}
.stamp{color:var(--ink-2);font-size:13.5px}
.stamp b{color:var(--ink);font-weight:600}
.top .find{margin-left:auto;display:flex;gap:8px;align-items:center}
.find input{font:inherit;font-size:14px;color:var(--ink);background:var(--wash);
  border:1px solid transparent;border-radius:6px;padding:7px 11px;width:220px}
.find input:focus{border-color:var(--rule);outline:none;background:var(--paper)}
.btn{font:500 13px/1 var(--sans);color:var(--ink-2);background:none;border:1px solid var(--rule);
  border-radius:6px;padding:8px 10px;cursor:pointer}
.btn:hover{color:var(--ink);border-color:var(--ink-3)}
.btn[aria-pressed="true"]{color:var(--ink);background:var(--wash)}
@media (max-width:720px){.top .find{margin-left:0;width:100%}.find input{flex:1;width:auto}}

.topics{display:flex;gap:4px;overflow-x:auto;border-bottom:1px solid var(--rule);
  scrollbar-width:none;margin:0 -4px}
.topics::-webkit-scrollbar{display:none}
.topics button{font:500 14px/1 var(--sans);color:var(--ink-2);background:none;border:0;
  padding:12px 10px 13px;cursor:pointer;white-space:nowrap;border-bottom:2px solid transparent;
  margin-bottom:-1px}
.topics button:hover{color:var(--ink)}
.topics button[aria-pressed="true"]{color:var(--ink);border-bottom-color:var(--ink)}

/* ---------- since you looked ---------- */
.since{display:none;align-items:center;gap:14px;margin:18px 0 0;padding:10px 14px;
  background:var(--wash);border-radius:8px;font-size:14px}
.since.on{display:flex}
.since b{font-weight:600}
.since .btn{margin-left:auto;background:var(--paper)}

/* ---------- stage marker: signal bars = independent newsrooms ---------- */
.stage{display:inline-flex;align-items:center;gap:6px;font-weight:600;font-size:12.5px;
  color:var(--c)}
.sig{display:inline-flex;align-items:flex-end;gap:2px;height:11px}
.sig i{display:block;width:3px;border-radius:1px;background:var(--rule)}
.sig i:nth-child(1){height:4px}.sig i:nth-child(2){height:6px}
.sig i:nth-child(3){height:8.5px}.sig i:nth-child(4){height:11px}
.sig[data-n="1"] i:nth-child(-n+1),.sig[data-n="2"] i:nth-child(-n+2),
.sig[data-n="3"] i:nth-child(-n+3),.sig[data-n="4"] i:nth-child(-n+4){background:var(--c)}
.st-spotted{--c:var(--spotted)} .st-spreading{--c:var(--spreading)}
.st-confirmed{--c:var(--confirmed)} .st-changed{--c:var(--changed)}

/* ---------- lead ---------- */
.lead{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:32px;padding:28px 0 26px;
  border-bottom:1px solid var(--rule)}
.lead.solo{grid-template-columns:1fr}
.lead .hl{font:600 clamp(26px,3.4vw,40px)/1.12 var(--serif);letter-spacing:-.015em;
  display:block;margin:10px 0 12px;max-width:24ch;text-wrap:balance}
.lead p{margin:0;color:var(--ink-2);max-width:62ch}
.lead .curve{align-self:end}
.lead .curve .cap{font-size:12.5px;color:var(--ink-3);margin-top:6px}
@media (max-width:820px){.lead{grid-template-columns:1fr;gap:16px}.lead.solo{grid-template-columns:1fr}
.lead .hl{max-width:none}}

/* ---------- desk ---------- */
.desk{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);column-gap:48px;
  padding:8px 0 40px;grid-template-areas:"now rail" "latest rail";align-items:start}
.nowcol{grid-area:now}.latest{grid-area:latest}.rail{grid-area:rail}
@media (max-width:900px){.desk{grid-template-columns:1fr;
  grid-template-areas:"now" "rail" "latest"}}
/* right now: live posts pulled in the browser */
.nowlist li{display:grid;grid-template-columns:62px minmax(0,1fr);gap:14px;padding:9px 0;
  border-bottom:1px solid var(--rule)}
.nowlist li.empty{display:block;color:var(--ink-3);font-size:14px}
.nowlist .t{font-size:13px;color:var(--spreading);font-weight:600;padding-top:2px}
.nowlist .t.old{color:var(--ink-3);font-weight:400}
.nowlist a.post{font:500 15px/1.35 var(--serif);color:var(--ink)}
.nowlist .who{font-size:12.5px;color:var(--ink-2);margin-top:2px}
.nowlist .more-now{display:block;border:0;padding:10px 0 0}
.nowlist .more-now button{font:500 13px var(--sans);background:none;border:0;padding:0;
  color:var(--ink-2);cursor:pointer;text-decoration:underline;text-underline-offset:3px}
.upd{margin-top:6px;padding-left:10px;border-left:2px solid var(--spreading);font-size:14px}
.upd span{display:block;font-size:12px;color:var(--ink-3)}
.upd a{font:500 15px/1.35 var(--serif);color:var(--ink)}
.upd .since-first{margin-top:2px}
.lane{padding-top:22px}
.lane>header{display:flex;align-items:baseline;flex-wrap:wrap;gap:2px 10px;margin-bottom:4px}
.lane h2{font:700 17px/1.2 var(--sans);letter-spacing:-.01em;margin:0;white-space:nowrap}
.lane .why{font-size:13px;color:var(--ink-3)}
.lane .empty{color:var(--ink-3);font-size:14px;padding:12px 0}
.lane ol{list-style:none;margin:0;padding:0}

/* latest: a timed log */
.log li{display:grid;grid-template-columns:62px minmax(0,1fr);gap:14px;padding:12px 0;
  border-bottom:1px solid var(--rule)}
.log time{font-size:13px;color:var(--ink-2);padding-top:3px;position:relative}
.log time small{display:block;color:var(--ink-3);font-size:12px}
.log li.new time::before{content:"";position:absolute;left:-12px;top:9px;width:6px;height:6px;
  border-radius:50%;background:var(--spreading)}
.hl{font:600 17px/1.3 var(--serif);color:var(--ink);text-wrap:pretty}
.by{display:flex;flex-wrap:wrap;align-items:center;gap:4px 14px;margin-top:5px;
  font-size:13px;color:var(--ink-2)}
.by .src{color:var(--ink)}
.by .more{color:var(--ink-3)}
.by .more:hover{color:var(--ink)}
.by .lang{color:var(--ink-3)}
.orig{font-size:13px;color:var(--ink-3);margin-top:3px}
li.read .hl,li.read .lead-hl{color:var(--ink-3)}
.hide-read li.read{display:none}
.log li.more-row{display:block;border:0;padding:14px 0}

/* rail: short lists with one fact each */
.rail ol li{padding:11px 0;border-bottom:1px solid var(--rule)}
.rail .hl{font-size:15.5px}
.rail .fact{font-size:13px;color:var(--ink-2);margin-top:4px}
.rail .fact b{font-weight:600;color:var(--c,var(--ink))}
del{color:var(--ink-3)} ins{text-decoration:none;background:color-mix(in srgb,var(--changed) 18%,transparent);
  padding:0 2px;border-radius:2px}

/* ---------- story page ---------- */
.back{display:inline-block;margin:24px 0 0;font-size:14px;color:var(--ink-2)}
.story{max-width:760px;padding:18px 0 48px}
.story h1{font:600 clamp(28px,4vw,42px)/1.12 var(--serif);letter-spacing:-.015em;
  margin:12px 0 14px;text-wrap:balance}
.story .dek{font-size:16px;color:var(--ink-2);margin:0 0 6px;max-width:62ch}
.story .open{display:inline-block;margin-top:12px;font-weight:600;font-size:14px;
  border-bottom:1px solid var(--ink);padding-bottom:1px}
.story .open:hover{text-decoration:none;color:var(--ink-2)}
.story h2{font:700 17px/1.2 var(--sans);margin:40px 0 4px}
.story h2+p{margin:0 0 14px;color:var(--ink-3);font-size:13.5px}
.chart svg{display:block;width:100%;height:auto}
.chart text{font:12px var(--sans);fill:var(--ink-3)}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;
  background:var(--rule);border:1px solid var(--rule);border-radius:8px;overflow:hidden;margin-top:26px}
.facts div{background:var(--paper);padding:12px 14px}
.facts b{display:block;font:600 22px/1.1 var(--serif)}
.facts span{font-size:12.5px;color:var(--ink-3)}
.unfold{list-style:none;margin:8px 0 0;padding:0;position:relative}
.unfold::before{content:"";position:absolute;left:69px;top:8px;bottom:8px;width:1px;background:var(--rule)}
.unfold li{display:grid;grid-template-columns:62px 16px minmax(0,1fr);gap:0 8px;padding:10px 0}
.unfold time{font-size:13px;color:var(--ink-2);padding-top:2px}
.unfold time small{display:block;color:var(--ink-3);font-size:11.5px}
.unfold .pin{width:9px;height:9px;border-radius:50%;margin:6px 0 0 3px;background:var(--paper);
  border:2px solid var(--c,var(--ink-3));position:relative;z-index:1}
.unfold li.indep .pin{background:var(--c,var(--ink))}
.unfold .what{font-size:12.5px;color:var(--c,var(--ink-3));font-weight:600;margin-bottom:2px}
.unfold .hl{font-size:16px}
.unfold .also{font-size:13px;color:var(--ink-3);margin-top:3px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:16px}
.chip{font-size:13px;padding:4px 10px;border-radius:99px;background:var(--wash);color:var(--ink-2)}
.chip:hover{color:var(--ink);text-decoration:none}

/* ---------- tables, beats, footer ---------- */
.intro{max-width:64ch;color:var(--ink-2);margin:6px 0 18px}
h1.title{font:600 32px/1.15 var(--serif);letter-spacing:-.015em;margin:22px 0 6px}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font-weight:600;text-align:left;color:var(--ink-2);font-size:12.5px;padding:8px 10px;
  border-bottom:1px solid var(--ink-3);white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid var(--rule)}
td.num,th.num{text-align:right}
.spikes{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin:10px 0 8px}
.spike{display:block;padding:12px 14px;border:1px solid var(--rule);border-radius:8px}
.spike:hover{border-color:var(--ink-3);text-decoration:none}
.spike b{display:block;font:600 16px/1.2 var(--serif)}
.spike span{font-size:13px;color:var(--ink-2)}
footer{border-top:1px solid var(--rule);padding:20px 0 40px;color:var(--ink-3);font-size:13px;
  display:flex;flex-wrap:wrap;gap:8px 20px}
footer a{color:var(--ink-2)}
footer .btn{padding:5px 8px;font-size:12px}
.banner{background:var(--changed);color:#fff;text-align:center;padding:7px 10px;font-size:13px;font-weight:600}
[hidden]{display:none!important}
@media (prefers-reduced-motion:no-preference){
  .wordmark .live{animation:pulse 2.4s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
}
"""

JS = r"""
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
"""
