const ROOT = './archive';
const COLORS = ['#7aa8ff','#73c9a4','#f2ad67','#aa91e8','#e88383','#6cc4d9','#d8b45c'];
const state = { issues: [], items: [], latest: null, graphScope: 'latest', graphMode: 'topic', roles: new Set(['core','supplement','radar']), keyword: '', keywordSuggestions: [], view: null, drag: null, lastLayout: null };
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s='') => String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const norm = (s='') => String(s).toLowerCase().replace(/[\s_\-\/、，。:：()（）]+/g,'');
const clamp = (v,a,b) => Math.max(a,Math.min(b,v));

async function getJson(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); }
async function getText(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`${r.status} ${url}`); return r.text(); }

function collectDetailMap(doc){
  const map=new Map();
  const seen=new Set();
  function walk(x){
    if(!x||typeof x!=='object'||seen.has(x))return; seen.add(x);
    if(!Array.isArray(x)&&x.brief_item_id){
      const prev=map.get(x.brief_item_id)||{};
      map.set(x.brief_item_id,{...prev,...x,keywords:[...new Set([...(prev.keywords||[]),...(x.keywords||[])])]});
    }
    if(Array.isArray(x))x.forEach(walk);else Object.values(x).forEach(walk);
  }
  walk(doc); return map;
}

function inferKeywords(item){
  const out=new Set((item.keywords||[]).filter(Boolean));
  if(item.topic_name)out.add(item.topic_name);
  if(item.direction_name)out.add(item.direction_name);
  const hay=[item.title,item.summary,item.topic_name,item.direction_name].filter(Boolean).join(' ');
  const lexicon=['KVCache','KV Cache','Agent','RDMA','DPU','CXL','MoE','GPU','NPU','TPN','Fabric','MCP','Prefill','Decode','S3','harness','FlashAttention','NAND','推理','存储','网络','内存','跨域','调度','缓存','确定性','工具链'];
  lexicon.forEach(k=>{if(norm(hay).includes(norm(k)))out.add(k)});
  (hay.match(/[A-Za-z][A-Za-z0-9+._-]{2,}/g)||[]).filter(x=>x.length<=24).forEach(x=>out.add(x));
  return [...out].slice(0,24);
}

function radarItems(issue){
  const rows=issue.issueDoc?.synthesis?.radar_signals||[];
  return rows.map((r,i)=>({
    id:`radar:${issue.date}:${i}`,paper_key:`radar:${issue.date}:${i}`,item_id:`radar:${issue.date}:${i}`,
    title:r.signal||r.summary||'Radar signal',summary:r.summary||'',url:(r.source_urls||[])[0]||'',
    topic_name:r.category||'今日雷达',topic_id:`radar-${r.category||'other'}`,direction_name:'今日雷达',role:'radar',score:null,
    issue_date:issue.date,keywords:inferKeywords({title:r.signal,summary:r.summary,topic_name:r.category})
  }));
}

async function load(){
  const archive = await getJson(`${ROOT}/index.json`);
  const payloads = await Promise.all((archive.issues||[]).map(async meta => {
    const [papers,issueDoc] = await Promise.all([
      getJson(`${ROOT}/${meta.papers_file}`),
      getJson(`${ROOT}/issues/${meta.date}/issue.json`).catch(()=>({}))
    ]);
    const detailMap=collectDetailMap(issueDoc);
    const enriched=papers.map((p,i)=>{
      const d=detailMap.get(p.item_id)||{};
      const item={...p,id:p.paper_key||p.item_id||`${meta.date}:${i}`,issue_date:meta.date,summary:d.core_conclusion||d.summary||d.project_relevance||'',direction_name:d.direction_name||p.direction_id,keywords:d.keywords||[],detail:d};
      item.keywords=inferKeywords(item); return item;
    });
    const issue={...meta,papers:enriched,issueDoc};
    issue.radar=radarItems(issue);
    return issue;
  }));
  state.issues=payloads;
  state.items=payloads.flatMap(i=>[...i.papers,...i.radar]);
  state.latest=payloads.at(-1);
  state.keywordSuggestions=buildKeywordSuggestions();
  await renderHero();
  renderKpis(); renderTrend(); renderLatest(); renderTopics(); renderArchive(); bindControls(); renderKeywordChips(); renderGraph(true);
  $('#buildStamp').textContent = new Date().toLocaleDateString('zh-CN');
}

async function renderHero(){
  const x=state.latest; if(!x)return;
  $('#latestHeadline').textContent=x.headline;
  $('#latestDate').textContent=`LATEST — ${x.date}`;
  const href=`${ROOT}/issues/${x.date}/email.html`;
  $('#latestIssueLink').href=href; $('#heroStackLink').href=href;
  $('#latestCount').textContent=`${x.papers.length} 条结构化主记录 + ${x.radar.length} 条雷达`;
  let imgs=[];
  try{
    const html=await getText(href); const doc=new DOMParser().parseFromString(html,'text/html');
    imgs=[...doc.querySelectorAll('tr[data-reader-role="explanatory-illustration"] img')].map(img=>({src:img.getAttribute('src'),alt:img.getAttribute('alt')||'本期技术图解'})).filter(x=>x.src);
    if(!imgs.length) imgs=[...doc.querySelectorAll('img')].map(img=>({src:img.getAttribute('src'),alt:img.getAttribute('alt')||'本期技术图解'})).filter(x=>x.src);
  }catch(e){ console.warn('hero images',e); }
  imgs=imgs.slice(0,4);
  $('#heroImageCount').textContent=imgs.length?`${imgs.length} 张已发布插图`:'暂无插图';
  $('#heroImageStack').innerHTML=imgs.length?imgs.map(img=>`<figure class="stack-card"><img src="${esc(img.src)}" alt="${esc(img.alt)}" loading="eager"/><figcaption>${esc(img.alt)}</figcaption></figure>`).join(''):'<div class="stack-empty">最新一期没有可复用插图<br/>首页会在下一期出现插图时自动更新</div>';
}

function renderKpis(){
  const topics=new Set(state.items.map(p=>p.topic_name).filter(Boolean));
  const core=state.items.filter(p=>p.role==='core').length;
  const supp=state.items.filter(p=>p.role==='supplement').length;
  const radar=state.items.filter(p=>p.role==='radar').length;
  const scored=state.items.filter(p=>Number.isFinite(+p.score));
  const avg=scored.reduce((a,p)=>a+(+p.score),0)/(scored.length||1);
  const cards=[['已归档日报',state.issues.length,'真实已发送版本','#dce8ff'],['结构化条目',state.items.length,`${core} 深度 · ${supp} 简要 · ${radar} 雷达`,'#dff3e8'],['持续专题',topics.size,'跨期确定性聚合','#f8dfc1'],['平均评分',avg.toFixed(1),'仅统计有评分条目','#e9e0fb']];
  $('#kpis').innerHTML=cards.map(([l,v,n,c])=>`<div class="kpi" style="--accent:${c}"><div class="kpi-label">${l}</div><div class="kpi-value">${v}</div><div class="kpi-note">${n}</div></div>`).join('');
}

function renderTrend(){
  const topics=[...new Set(state.items.filter(p=>p.role!=='radar').map(p=>p.topic_name).filter(Boolean))];
  const rows=topics.map(t=>({t,vals:state.issues.map(i=>i.papers.filter(p=>p.topic_name===t).length)})).sort((a,b)=>b.vals.reduce((x,y)=>x+y,0)-a.vals.reduce((x,y)=>x+y,0)).slice(0,7);
  const max=Math.max(1,...rows.flatMap(r=>r.vals));
  $('#topicTrend').innerHTML=rows.map((r,idx)=>`<div class="trend-row"><div class="trend-label" title="${esc(r.t)}">${esc(r.t)}</div><div class="spark" style="--bar:${COLORS[idx%COLORS.length]}">${r.vals.map(v=>`<i style="height:${Math.max(3,(v/max)*23)}px" title="${v}"></i>`).join('')}</div><div class="trend-total">${r.vals.reduce((a,b)=>a+b,0)}</div></div>`).join('');
}

function renderLatest(){
  const list=[...state.latest.papers].sort((a,b)=>(+b.score||0)-(+a.score||0)).slice(0,6);
  $('#latestPapers').innerHTML=list.map(p=>`<div class="paper-item"><div class="paper-score">${Number.isFinite(+p.score)?(+p.score).toFixed(0):'—'}</div><div><div class="paper-title">${esc(p.title)}</div><div class="paper-meta">${esc(p.topic_name||'未分类')} · ${p.role==='core'?'深度':'简要'} · ${esc(p.source_level||'')}</div></div><a href="${esc(p.url)}" target="_blank" rel="noreferrer">↗</a></div>`).join('');
}

function renderTopics(){
  const counts={}; state.items.filter(p=>p.role!=='radar').forEach(p=>{if(p.topic_name)counts[p.topic_name]=(counts[p.topic_name]||0)+1});
  $('#topicChips').innerHTML=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([t,n])=>`<button class="topic-chip" data-topic="${esc(t)}">${esc(t)} <b>${n}</b></button>`).join('');
  $$('.topic-chip').forEach(b=>b.addEventListener('click',()=>{ $('#searchInput').value=b.dataset.topic; renderArchive(b.dataset.topic); location.hash='archive'; }));
}

function renderArchive(q=''){
  const needle=q.trim().toLowerCase();
  const filtered=state.issues.filter(i=>!needle || [i.headline,i.date,...i.papers.flatMap(p=>[p.title,p.topic_name,p.direction_name])].join(' ').toLowerCase().includes(needle));
  $('#archiveSummary').textContent=`${filtered.length} / ${state.issues.length} 期`;
  $('#issueTimeline').innerHTML=state.issues.map((i,idx)=>`${idx?'<span class="timeline-line"></span>':''}<span class="timeline-node"><a href="${ROOT}/issues/${i.date}/email.html" target="_blank">${i.date.slice(5)}</a></span>`).join('');
  $('#archiveGrid').innerHTML=filtered.map(i=>{
    const tc={}; i.papers.forEach(p=>{if(p.topic_name)tc[p.topic_name]=(tc[p.topic_name]||0)+1});
    const tops=Object.entries(tc).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([t,n])=>`${t} ${n}`).join(' · ');
    const pills=Object.entries(i.counts||{}).map(([k,v])=>`<span class="pill">${k} ${v}</span>`).join('');
    return `<article class="issue-card"><div class="issue-date">${i.date}</div><div class="issue-headline">${esc(i.headline)}</div><div class="issue-counts">${pills}</div><div class="issue-topics">${esc(tops)}</div><a class="issue-link" href="${ROOT}/issues/${i.date}/email.html" target="_blank"><span>打开已发送日报</span><span>↗</span></a></article>`;
  }).join('') || '<div class="empty">没有匹配的归档。</div>';
}

function buildKeywordSuggestions(){
  const freq=new Map();
  state.items.forEach(i=>i.keywords.forEach(k=>{if(k&&k.length>1&&k.length<28)freq.set(k,(freq.get(k)||0)+1)}));
  return [...freq.entries()].filter(([,n])=>n>=2).sort((a,b)=>b[1]-a[1]||a[0].length-b[0].length).slice(0,18);
}
function renderKeywordChips(){
  $('#keywordChips').innerHTML=state.keywordSuggestions.map(([k,n])=>`<button class="keyword-chip${norm(k)===norm(state.keyword)?' active':''}" data-keyword="${esc(k)}">${esc(k)} · ${n}</button>`).join('');
  $$('.keyword-chip').forEach(b=>b.addEventListener('click',()=>{state.keyword=b.dataset.keyword;$('#keywordInput').value=state.keyword;renderKeywordChips();renderGraph(true)}));
}

function bindControls(){
  $('#searchInput').addEventListener('input',e=>renderArchive(e.target.value));
  $$('#scopeSwitch button').forEach(btn=>btn.addEventListener('click',()=>{$$('#scopeSwitch button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');state.graphScope=btn.dataset.scope;renderGraph(true)}));
  $$('#modeSwitch button').forEach(btn=>btn.addEventListener('click',()=>{$$('#modeSwitch button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');state.graphMode=btn.dataset.mode;$('#keywordPanel').hidden=state.graphMode!=='keyword';if(state.graphMode==='keyword'&&!state.keyword){state.keyword=state.keywordSuggestions[0]?.[0]||'Agent';$('#keywordInput').value=state.keyword;renderKeywordChips()}renderGraph(true)}));
  $$('.role-control input').forEach(cb=>cb.addEventListener('change',()=>{cb.checked?state.roles.add(cb.dataset.role):state.roles.delete(cb.dataset.role);renderGraph(true)}));
  $('#keywordApply').addEventListener('click',()=>{state.keyword=$('#keywordInput').value.trim()||state.keywordSuggestions[0]?.[0]||'Agent';renderKeywordChips();renderGraph(true)});
  $('#keywordInput').addEventListener('keydown',e=>{if(e.key==='Enter')$('#keywordApply').click()});
  $('#zoomIn').addEventListener('click',()=>zoomGraph(.78)); $('#zoomOut').addEventListener('click',()=>zoomGraph(1.28)); $('#zoomReset').addEventListener('click',resetGraphView);
  initPanZoom();
}

function scopedItems(){
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const dates=new Set(issues.map(i=>i.date));
  return state.items.filter(i=>dates.has(i.issue_date)&&state.roles.has(i.role));
}
function matchesKeyword(item,q){
  const n=norm(q); if(!n)return true;
  return [item.title,item.summary,item.topic_name,item.direction_name,...(item.keywords||[])].some(v=>{const x=norm(v);return x.includes(n)||(x.length>2&&n.includes(x))});
}
function topicModel(){
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const items=scopedItems(); const topics=new Map();
  items.forEach(item=>{const t=item.topic_name||'未分类';if(!topics.has(t))topics.set(t,{name:t,items:[],dates:new Set()});const x=topics.get(t);x.items.push(item);x.dates.add(item.issue_date)});
  const groups=[...topics.values()].sort((a,b)=>b.items.length-a.items.length);
  const issueCounts=new Map(); items.forEach(i=>{const k=`${i.issue_date}|||${i.topic_name||'未分类'}`;issueCounts.set(k,(issueCounts.get(k)||0)+1)});
  return {mode:'topic',issues,items,groups,issueCounts};
}
function keywordModel(){
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const all=scopedItems(); const q=state.keyword||state.keywordSuggestions[0]?.[0]||'Agent';
  const items=all.filter(i=>matchesKeyword(i,q)); const map=new Map();
  items.forEach(item=>{const t=item.topic_name||'未分类';if(!map.has(t))map.set(t,{name:t,items:[],dates:new Set()});const g=map.get(t);g.items.push(item);g.dates.add(item.issue_date)});
  return {mode:'keyword',issues,items,groups:[...map.values()].sort((a,b)=>b.items.length-a.items.length),keyword:q};
}

function renderGraph(reset=false){
  const model=state.graphMode==='keyword'?keywordModel():topicModel();
  const layout=state.graphMode==='keyword'?layoutKeyword(model):layoutTopic(model);
  drawGraph(model,layout); renderGraphStats(model); renderInspector(null,model); if(reset)fitGraph(layout);
}

function layoutTopic(model){
  const colX={issue:95,topic:480,item0:760}; const itemCols=3,itemW=205,itemGapX=220,rowH=39,groupGap=52;
  let y=82; const nodes=[],edges=[]; const issueNodes=new Map();
  model.issues.forEach((i,idx)=>{const n={id:`issue:${i.date}`,type:'issue',label:i.date,x:colX.issue,y:100+idx*78,data:i};issueNodes.set(i.date,n);nodes.push(n)});
  model.groups.forEach(g=>{
    const rows=Math.ceil(g.items.length/itemCols); const blockH=Math.max(64,rows*rowH); const mid=y+blockH/2;
    const tn={id:`topic:${g.name}`,type:'topic',label:g.name,x:colX.topic,y:mid,w:190,h:46,data:g}; nodes.push(tn);
    g.items.forEach((item,j)=>{const row=Math.floor(j/itemCols),col=j%itemCols;const n={id:`item:${item.issue_date}:${item.id}`,type:'item',label:item.title,x:colX.item0+col*itemGapX,y:y+20+row*rowH,w:itemW,h:28,data:item};nodes.push(n);edges.push({a:tn,b:n,kind:'item',weight:1})});
    model.issues.forEach(issue=>{const weight=model.issueCounts.get(`${issue.date}|||${g.name}`)||0;if(weight)edges.push({a:issueNodes.get(issue.date),b:tn,kind:'issue',weight})});
    y+=blockH+groupGap;
  });
  return {nodes,edges,W:1450,H:Math.max(760,y+30)};
}

function layoutKeyword(model){
  const W=1500,H=Math.max(900,520+model.groups.length*22); const nodes=[],edges=[];
  const center={id:`keyword:${model.keyword}`,type:'keyword',label:model.keyword,x:W/2,y:H/2,w:220,h:58,data:{count:model.items.length}}; nodes.push(center);
  const n=Math.max(1,model.groups.length),topicR=Math.min(310,210+n*12),itemR=topicR+235;
  model.groups.forEach((g,i)=>{
    const ang=-Math.PI/2+(Math.PI*2*i/n); const tx=center.x+Math.cos(ang)*topicR,ty=center.y+Math.sin(ang)*topicR;
    const tn={id:`topic:${g.name}`,type:'topic',label:g.name,x:tx,y:ty,w:180,h:44,data:g}; nodes.push(tn); edges.push({a:center,b:tn,kind:'keyword',weight:g.items.length});
    const spread=Math.min(.72,Math.max(.22,g.items.length*.06));
    g.items.forEach((item,j)=>{const local=g.items.length===1?0:(j/(g.items.length-1)-.5)*spread;const a2=ang+local;const rr=itemR+(j%2)*45;const inode={id:`item:${item.issue_date}:${item.id}`,type:'item',label:item.title,x:center.x+Math.cos(a2)*rr,y:center.y+Math.sin(a2)*rr,w:190,h:28,data:item};nodes.push(inode);edges.push({a:tn,b:inode,kind:'item',weight:1})});
  });
  return {nodes,edges,W,H};
}

function svgEl(tag,attrs={}){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));return el}
function drawGraph(model,layout){
  const svg=$('#knowledgeGraph'); svg.innerHTML='';
  const edgesG=svgEl('g'),nodesG=svgEl('g'); svg.append(edgesG,nodesG);
  layout.edges.forEach(e=>{const a=e.a,b=e.b;const path=svgEl('path',{d:`M ${a.x} ${a.y} C ${(a.x+b.x)/2} ${a.y}, ${(a.x+b.x)/2} ${b.y}, ${b.x} ${b.y}`,class:`edge ${e.kind==='keyword'?'keyword-edge':e.kind==='item'?'item-edge':''}`,'stroke-width':e.kind==='item'?1:1.2+Math.min(6,e.weight)*.45});edgesG.appendChild(path)});
  layout.nodes.forEach(n=>{const g=svgEl('g',{class:'node'});drawNode(g,n);g.addEventListener('mouseenter',ev=>showTip(ev,n));g.addEventListener('mouseleave',()=>$('#graphTooltip').style.display='none');g.addEventListener('click',ev=>{ev.stopPropagation();renderInspector(n,model);if(n.type==='item'&&n.data.url)window.open(n.data.url,'_blank');if(n.type==='issue')window.open(`${ROOT}/issues/${n.data.date}/email.html`,'_blank')});nodesG.appendChild(g)});
  state.lastLayout=layout;
}
function drawNode(g,n){
  if(n.type==='issue'){g.appendChild(svgEl('circle',{cx:n.x,cy:n.y,r:14,class:'node-shape issue-node'}));textNode(g,n.label.slice(5),n.x+23,n.y+4,11,'node-title');textNode(g,`${(n.data.papers?.length||0)+(n.data.radar?.length||0)} items`,n.x+23,n.y+18,8,'node-sub');return}
  if(n.type==='keyword'){g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:19,class:'node-shape keyword-node'}));textNode(g,`⌕  ${truncate(n.label,22)}`,n.x-n.w/2+16,n.y-2,15,'node-title');textNode(g,`${n.data.count} matching items`,n.x-n.w/2+16,n.y+17,9,'node-sub');return}
  if(n.type==='topic'){g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:13,class:'node-shape topic-node'}));textNode(g,truncate(n.label,18),n.x-n.w/2+12,n.y-2,11,'node-title');textNode(g,`${n.data.items.length} 条 · ${n.data.dates.size} 期`,n.x-n.w/2+12,n.y+14,8,'node-sub');return}
  const role=n.data.role||'supplement'; g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:8,class:`node-shape item-${role}`}));g.appendChild(svgEl('circle',{cx:n.x-n.w/2+10,cy:n.y,r:4,class:`role-badge-${role}`}));textNode(g,truncate(n.label,25),n.x-n.w/2+20,n.y+3,8.5,'node-title');
}
function textNode(g,s,x,y,size,cls){const t=svgEl('text',{x,y,'font-size':size,class:cls});t.textContent=s;g.appendChild(t)}
function truncate(s,n){s=String(s||'');return s.length>n?s.slice(0,n-1)+'…':s}
function roleName(r){return r==='core'?'深度解读':r==='supplement'?'专题补充':'今日雷达'}

function showTip(ev,n){const tip=$('#graphTooltip');let html=`<b>${esc(n.label)}</b>`;if(n.type==='item')html+=`<br><small>${roleName(n.data.role)} · ${esc(n.data.topic_name||'')}</small>${n.data.score?`<br>score ${n.data.score}`:''}`;if(n.type==='topic')html+=`<br><small>${n.data.items.length} 条 · ${n.data.dates.size} 期</small>`;tip.innerHTML=html;tip.style.display='block';tip.style.left=`${Math.min(window.innerWidth-330,ev.clientX+14)}px`;tip.style.top=`${Math.min(window.innerHeight-120,ev.clientY+14)}px`}
function renderInspector(n,model){
  const box=$('#graphInspector');
  if(!n){box.innerHTML=`<span class="inspector-kicker">RELATION LENS</span><h3>${model.mode==='keyword'?`关键词「${esc(model.keyword)}」聚类`:'选择一个专题或条目'}</h3><p>${model.mode==='keyword'?`当前找到 ${model.items.length} 条显式匹配记录，按专题聚类。`:'专题模式展示 Issue → Topic → 全量条目。点击节点查看详情。'}</p><div class="inspector-tip">图中关系来自归档结构与显式关键词，不推断归档没有证明的语义边。</div>`;return}
  if(n.type==='topic'){const roles=countRoles(n.data.items);box.innerHTML=`<span class="inspector-kicker">TOPIC CLUSTER</span><h3>${esc(n.label)}</h3><div class="inspector-grid"><div><b>${n.data.items.length}</b><small>条目</small></div><div><b>${n.data.dates.size}</b><small>涉及日报</small></div><div><b>${roles.core}</b><small>深度</small></div><div><b>${roles.supplement+roles.radar}</b><small>简要/雷达</small></div></div><ul class="inspector-list">${n.data.items.slice(0,8).map(i=>`<li>${roleName(i.role)} · ${esc(truncate(i.title,32))}</li>`).join('')}</ul>`;return}
  if(n.type==='item'){box.innerHTML=`<span class="inspector-kicker">${n.data.role.toUpperCase()}</span><h3>${esc(n.label)}</h3><p>${esc(n.data.summary||'归档中暂无额外摘要。')}</p><div class="inspector-grid"><div><b>${n.data.score??'—'}</b><small>评分</small></div><div><b>${esc(n.data.issue_date.slice(5))}</b><small>日报日期</small></div></div><div class="inspector-tip">${esc((n.data.keywords||[]).slice(0,8).join(' · '))}</div>`;return}
  if(n.type==='keyword'){box.innerHTML=`<span class="inspector-kicker">KEYWORD CENTER</span><h3>${esc(n.label)}</h3><p>当前范围内共有 ${n.data.count} 条记录显式匹配该关键词。</p><div class="inspector-tip">匹配字段：归档关键词、标题、专题、方向与摘要。</div>`;return}
  box.innerHTML=`<span class="inspector-kicker">BRIEFING</span><h3>${esc(n.data.date)}</h3><p>${esc(n.data.headline||'')}</p><div class="inspector-tip">点击日报节点可打开已发送 HTML。</div>`;
}
function countRoles(items){return items.reduce((a,i)=>(a[i.role]=(a[i.role]||0)+1,a),{core:0,supplement:0,radar:0})}
function renderGraphStats(model){const roles=countRoles(model.items);const topics=new Set(model.items.map(i=>i.topic_name));$('#graphStats').innerHTML=[['可见条目',model.items.length],['专题',topics.size],['深度',roles.core],['简要',roles.supplement],['雷达',roles.radar],...(model.mode==='keyword'?[['中心关键词',model.keyword]]:[])].map(([k,v])=>`<span class="graph-stat"><b>${esc(v)}</b>${k}</span>`).join('')}

function fitGraph(layout=state.lastLayout){if(!layout)return;state.view={x:0,y:0,w:layout.W,h:layout.H};applyView()}
function resetGraphView(){fitGraph()}
function applyView(){if(!state.view)return;$('#knowledgeGraph').setAttribute('viewBox',`${state.view.x} ${state.view.y} ${state.view.w} ${state.view.h}`)}
function zoomGraph(factor,cx=.5,cy=.5){if(!state.view)return;const v=state.view;const nw=v.w*factor,nh=v.h*factor;v.x+=v.w*cx-nw*cx;v.y+=v.h*cy-nh*cy;v.w=nw;v.h=nh;applyView()}
function initPanZoom(){
  const svg=$('#knowledgeGraph');
  svg.addEventListener('wheel',e=>{e.preventDefault();const r=svg.getBoundingClientRect();zoomGraph(e.deltaY<0?.82:1.22,clamp((e.clientX-r.left)/r.width,0,1),clamp((e.clientY-r.top)/r.height,0,1))},{passive:false});
  svg.addEventListener('pointerdown',e=>{if(e.button!==0)return;svg.setPointerCapture(e.pointerId);state.drag={x:e.clientX,y:e.clientY,view:{...state.view}};svg.classList.add('dragging')});
  svg.addEventListener('pointermove',e=>{if(!state.drag)return;const r=svg.getBoundingClientRect(),dx=(e.clientX-state.drag.x)/r.width*state.drag.view.w,dy=(e.clientY-state.drag.y)/r.height*state.drag.view.h;state.view={...state.drag.view,x:state.drag.view.x-dx,y:state.drag.view.y-dy};applyView()});
  const end=()=>{state.drag=null;svg.classList.remove('dragging')};svg.addEventListener('pointerup',end);svg.addEventListener('pointercancel',end);
}

load().catch(err=>{console.error(err);document.body.insertAdjacentHTML('afterbegin',`<div style="background:#7d1f1f;color:#fff;padding:10px;text-align:center">站点数据加载失败：${esc(err.message)}</div>`)});
