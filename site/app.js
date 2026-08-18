const ROOT = './archive';
const COLORS = ['#7aa8ff','#73c9a4','#f2ad67','#aa91e8','#e88383','#6cc4d9','#d8b45c'];
const state = { index: [], issues: [], papers: [], latest: null, graphScope: 'latest' };
const $ = (s) => document.querySelector(s);
const esc = (s='') => String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));

async function getJson(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); }

async function load(){
  const archive = await getJson(`${ROOT}/index.json`);
  state.index = archive.issues || [];
  const payloads = await Promise.all(state.index.map(async meta => {
    const papers = await getJson(`${ROOT}/${meta.papers_file}`);
    return {...meta, papers};
  }));
  state.issues = payloads;
  state.papers = payloads.flatMap(i=>i.papers.map(p=>({...p, issue_date:i.date})));
  state.latest = payloads.at(-1);
  render();
}

function render(){
  renderHero(); renderKpis(); renderTrend(); renderLatest(); renderTopics(); renderArchive(); renderGraph();
  $('#buildStamp').textContent = new Date().toLocaleDateString('zh-CN');
}

function renderHero(){ const x=state.latest; if(!x)return; $('#latestHeadline').textContent=x.headline; $('#latestDate').textContent=`LATEST — ${x.date}`; $('#latestIssueLink').href=`${ROOT}/issues/${x.date}/email.html`; $('#latestCount').textContent=`${x.papers.length} 条结构化记录`; }

function renderKpis(){
  const topics = new Set(state.papers.map(p=>p.topic_name).filter(Boolean));
  const core = state.papers.filter(p=>p.role==='core').length;
  const scored=state.papers.filter(p=>Number.isFinite(+p.score));
  const avg = scored.reduce((a,p)=>a+(+p.score),0)/(scored.length||1);
  const cards=[['已归档日报',state.issues.length,'真实已发送版本','#dce8ff'],['结构化条目',state.papers.length,`${core} 条核心解读`,'#dff3e8'],['持续专题',topics.size,'跨期自动聚合','#f8dfc1'],['平均评分',avg.toFixed(1),'来自 papers.json','#e9e0fb']];
  $('#kpis').innerHTML=cards.map(([l,v,n,c])=>`<div class="kpi" style="--accent:${c}"><div class="kpi-label">${l}</div><div class="kpi-value">${v}</div><div class="kpi-note">${n}</div></div>`).join('');
}

function renderTrend(){
  const topics=[...new Set(state.papers.map(p=>p.topic_name).filter(Boolean))];
  const rows=topics.map(t=>({t,vals:state.issues.map(i=>i.papers.filter(p=>p.topic_name===t).length)})).sort((a,b)=>b.vals.reduce((x,y)=>x+y,0)-a.vals.reduce((x,y)=>x+y,0)).slice(0,7);
  const max=Math.max(1,...rows.flatMap(r=>r.vals));
  $('#topicTrend').innerHTML=rows.map((r,idx)=>`<div class="trend-row"><div class="trend-label" title="${esc(r.t)}">${esc(r.t)}</div><div class="spark" style="--bar:${COLORS[idx%COLORS.length]}">${r.vals.map(v=>`<i style="height:${Math.max(3,(v/max)*23)}px" title="${v}"></i>`).join('')}</div><div class="trend-total">${r.vals.reduce((a,b)=>a+b,0)}</div></div>`).join('');
}

function renderLatest(){
  const list=[...state.latest.papers].sort((a,b)=>(+b.score||0)-(+a.score||0)).slice(0,6);
  $('#latestPapers').innerHTML=list.map(p=>`<div class="paper-item"><div class="paper-score">${(+p.score||0).toFixed(0)}</div><div><div class="paper-title">${esc(p.title)}</div><div class="paper-meta">${esc(p.topic_name||'未分类')} · ${esc(p.role||'item')} · ${esc(p.source_level||'')}</div></div><a href="${esc(p.url)}" target="_blank" rel="noreferrer">↗</a></div>`).join('');
}

function renderTopics(){
  const counts={}; state.papers.forEach(p=>{if(p.topic_name)counts[p.topic_name]=(counts[p.topic_name]||0)+1});
  $('#topicChips').innerHTML=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([t,n])=>`<button class="topic-chip" data-topic="${esc(t)}">${esc(t)} <b>${n}</b></button>`).join('');
  document.querySelectorAll('.topic-chip').forEach(b=>b.addEventListener('click',()=>{ $('#searchInput').value=b.dataset.topic; filterArchive(b.dataset.topic); location.hash='archive'; }));
}

function renderArchive(q=''){
  const needle=q.trim().toLowerCase();
  const filtered=state.issues.filter(i=>!needle || [i.headline,i.date,...i.papers.flatMap(p=>[p.title,p.topic_name,p.direction_id])].join(' ').toLowerCase().includes(needle));
  $('#archiveSummary').textContent=`${filtered.length} / ${state.issues.length} 期`;
  $('#issueTimeline').innerHTML=state.issues.map((i,idx)=>`${idx?'<span class="timeline-line"></span>':''}<span class="timeline-node"><a href="${ROOT}/issues/${i.date}/email.html" target="_blank">${i.date.slice(5)}</a></span>`).join('');
  $('#archiveGrid').innerHTML=filtered.map(i=>{
    const tc={};i.papers.forEach(p=>{if(p.topic_name)tc[p.topic_name]=(tc[p.topic_name]||0)+1});
    const tops=Object.entries(tc).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([t,n])=>`${t} ${n}`).join(' · ');
    const pills=Object.entries(i.counts||{}).map(([k,v])=>`<span class="pill">${k} ${v}</span>`).join('');
    return `<article class="issue-card"><div class="issue-date">${i.date}</div><div class="issue-headline">${esc(i.headline)}</div><div class="issue-counts">${pills}</div><div class="issue-topics">${esc(tops)}</div><a class="issue-link" href="${ROOT}/issues/${i.date}/email.html" target="_blank"><span>打开已发送日报</span><span>↗</span></a></article>`;
  }).join('') || '<div class="empty">没有匹配的归档。</div>';
}

function filterArchive(q){ renderArchive(q); }
$('#searchInput').addEventListener('input',e=>filterArchive(e.target.value));

document.querySelectorAll('.segmented button').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('.segmented button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');state.graphScope=btn.dataset.scope;renderGraph();}));

function renderGraph(){
  const svg=$('#knowledgeGraph'); const W=1200,H=680; svg.innerHTML='';
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const paperCap=state.graphScope==='latest'?26:60;
  let nodes=[],edges=[]; const nodeMap=new Map();
  const add=(id,type,label,data={})=>{if(!nodeMap.has(id)){const n={id,type,label,data};nodeMap.set(id,n);nodes.push(n)}return nodeMap.get(id)};
  issues.forEach(issue=>{const inod=add(`issue:${issue.date}`,'issue',issue.date,{url:`${ROOT}/issues/${issue.date}/email.html`,headline:issue.headline}); const grouped={};issue.papers.forEach(p=>(grouped[p.topic_name||'未分类']??=[]).push(p));Object.entries(grouped).forEach(([topic,ps])=>{const tn=add(`topic:${topic}`,'topic',topic,{count:ps.length});edges.push([inod.id,tn.id]);ps.sort((a,b)=>(+b.score||0)-(+a.score||0)).slice(0,state.graphScope==='latest'?8:3).forEach(p=>{if(nodes.filter(n=>n.type==='paper').length>=paperCap)return;const pn=add(`paper:${p.paper_key||p.url}`,'paper',p.title,{url:p.url,score:p.score,topic});edges.push([tn.id,pn.id])})})});
  layout(nodes,edges,W,H);
  const NS='http://www.w3.org/2000/svg';
  edges.forEach(([a,b])=>{const A=nodeMap.get(a),B=nodeMap.get(b);const line=document.createElementNS(NS,'line');line.setAttribute('x1',A.x);line.setAttribute('y1',A.y);line.setAttribute('x2',B.x);line.setAttribute('y2',B.y);line.setAttribute('class','edge');svg.appendChild(line)});
  nodes.forEach(n=>{const g=document.createElementNS(NS,'g');g.setAttribute('class','node'); const c=document.createElementNS(NS,'circle');const r=n.type==='issue'?16:n.type==='topic'?11:5.5;c.setAttribute('cx',n.x);c.setAttribute('cy',n.y);c.setAttribute('r',r);c.setAttribute('fill',n.type==='issue'?'#f2ad67':n.type==='topic'?'#73c9a4':'#7aa8ff');c.setAttribute('stroke',n.type==='paper'?'none':'#dce5ec');c.setAttribute('stroke-width','1.2');g.appendChild(c); if(n.type!=='paper'){const t=document.createElementNS(NS,'text');t.setAttribute('x',n.x+(n.type==='issue'?24:17));t.setAttribute('y',n.y+4);t.setAttribute('fill','#e8eef4');t.setAttribute('font-size',n.type==='issue'?'14':'12');t.setAttribute('font-weight',n.type==='issue'?'800':'650');t.setAttribute('class','node-label');t.textContent=n.label.length>18?n.label.slice(0,18)+'…':n.label;g.appendChild(t)};g.addEventListener('mouseenter',e=>tip(e,n));g.addEventListener('mouseleave',()=>$('#graphTooltip').style.display='none');g.addEventListener('click',()=>{if(n.data.url)window.open(n.data.url,'_blank')});svg.appendChild(g)});
}

function layout(nodes,edges,W,H){
  const issues=nodes.filter(n=>n.type==='issue'), topics=nodes.filter(n=>n.type==='topic'), papers=nodes.filter(n=>n.type==='paper');
  issues.forEach((n,i)=>{n.x=120;n.y=(H/(issues.length+1))*(i+1)});
  topics.forEach((n,i)=>{n.x=430+(i%2)*70;n.y=70+(i/(Math.max(1,topics.length-1)))*(H-140)});
  const topicPos=new Map(topics.map(n=>[n.id,n])); const parent={};edges.forEach(([a,b])=>{if(a.startsWith('topic:')&&b.startsWith('paper:'))parent[b]=a});
  const buckets={};papers.forEach(p=>(buckets[parent[p.id]]??=[]).push(p));
  Object.entries(buckets).forEach(([tid,ps])=>{const t=topicPos.get(tid);ps.forEach((p,i)=>{const angle=(-1.1)+(2.2*(i+1)/(ps.length+1));const rad=250+(i%3)*28;p.x=Math.min(W-60,Math.max(650,t.x+Math.cos(angle)*rad));p.y=Math.min(H-35,Math.max(35,t.y+Math.sin(angle)*rad));})});
  if(issues.length>1){issues.forEach(iss=>{const linked=edges.filter(e=>e[0]===iss.id).map(e=>topicPos.get(e[1])).filter(Boolean);if(linked.length)iss.y=linked.reduce((s,t)=>s+t.y,0)/linked.length})}
}

function tip(e,n){const box=$('#graphTooltip');let html=`<strong>${esc(n.label)}</strong>`; if(n.type==='paper') html+=`<br><span>${esc(n.data.topic||'')}</span>${n.data.score!=null?` · ${esc(n.data.score)}`:''}<br><em>点击打开原始来源</em>`; else if(n.type==='issue')html+=`<br>${esc(n.data.headline||'')}<br><em>点击打开已发送日报</em>`; else html+=`<br>${n.data.count||''} 条关联记录`;box.innerHTML=html;box.style.display='block';const rect=$('.graph-shell').getBoundingClientRect();box.style.left=Math.min(rect.width-330,Math.max(10,e.clientX-rect.left+14))+'px';box.style.top=Math.min(rect.height-110,Math.max(10,e.clientY-rect.top+14))+'px';}

load().catch(err=>{console.error(err);$('#latestHeadline').textContent='归档数据读取失败，请刷新页面。';$('#kpis').innerHTML=`<div class="empty">${esc(err.message)}</div>`;});
