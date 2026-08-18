const ROOT = './archive';
const COLORS = ['#7aa8ff','#73c9a4','#f2ad67','#aa91e8','#e88383','#6cc4d9','#d8b45c'];
const state = { index: [], issues: [], papers: [], latest: null, graphScope: 'latest', graphFocus: null };
const $ = (s) => document.querySelector(s);
const esc = (s='') => String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

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

function renderHero(){
  const x=state.latest; if(!x)return;
  const topicCount=new Set(state.papers.map(p=>p.topic_name).filter(Boolean)).size;
  $('#latestHeadline').textContent=x.headline;
  $('#latestDate').textContent=`LATEST — ${x.date}`;
  $('#latestIssueLink').href=`${ROOT}/issues/${x.date}/email.html`;
  $('#latestCount').textContent=`${x.papers.length} 条结构化记录`;
  $('#heroIssueCount').textContent=state.issues.length;
  $('#heroSignalCount').textContent=state.papers.length;
  $('#heroTopicCount').textContent=topicCount;
}

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

document.querySelectorAll('.segmented button').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('.segmented button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  state.graphScope=btn.dataset.scope;
  state.graphFocus=null;
  renderGraph();
}));

function buildGraphModel(){
  const scopeIssues=state.graphScope==='latest'?[state.latest]:state.issues;
  const topicAgg=new Map();
  scopeIssues.forEach(issue=>issue.papers.forEach(p=>{
    const topic=p.topic_name||'未分类';
    if(!topicAgg.has(topic))topicAgg.set(topic,{topic,papers:[],dates:new Set(),issueCounts:new Map()});
    const a=topicAgg.get(topic);
    a.papers.push(p); a.dates.add(issue.date); a.issueCounts.set(issue.date,(a.issueCounts.get(issue.date)||0)+1);
  }));
  const topicLimit=state.graphScope==='latest'?7:8;
  const paperPerTopic=state.graphScope==='latest'?3:2;
  const selected=[...topicAgg.values()].sort((a,b)=>b.papers.length-a.papers.length).slice(0,topicLimit);
  const selectedNames=new Set(selected.map(x=>x.topic));
  const nodes=[],edges=[],nodeMap=new Map();
  const add=(id,type,label,data={})=>{if(!nodeMap.has(id)){const n={id,type,label,data};nodeMap.set(id,n);nodes.push(n)}return nodeMap.get(id)};
  scopeIssues.forEach(issue=>add(`issue:${issue.date}`,'issue',issue.date,{url:`${ROOT}/issues/${issue.date}/email.html`,headline:issue.headline,total:issue.papers.length}));
  selected.forEach(a=>{
    const dates=[...a.dates].sort();
    const unique=new Map();
    a.papers.forEach(p=>unique.set(p.paper_key||p.url,p));
    const reps=[...unique.values()].sort((x,y)=>(+y.score||0)-(+x.score||0)).slice(0,paperPerTopic);
    add(`topic:${a.topic}`,'topic',a.topic,{count:a.papers.length,issueCount:dates.length,first:dates[0],last:dates.at(-1),representatives:reps});
    reps.forEach(p=>add(`paper:${p.paper_key||p.url}`,'paper',p.title,{url:p.url,score:p.score,topic:a.topic,role:p.role,source:p.source_level}));
  });
  scopeIssues.forEach(issue=>{
    const counts={};issue.papers.forEach(p=>{const t=p.topic_name||'未分类';if(selectedNames.has(t))counts[t]=(counts[t]||0)+1});
    Object.entries(counts).forEach(([topic,weight])=>edges.push({a:`issue:${issue.date}`,b:`topic:${topic}`,kind:'issue-topic',weight}));
  });
  selected.forEach(a=>{
    const tn=nodeMap.get(`topic:${a.topic}`); if(!tn)return;
    tn.data.representatives.forEach(p=>edges.push({a:tn.id,b:`paper:${p.paper_key||p.url}`,kind:'topic-paper',weight:1}));
  });
  return {scopeIssues,selected,nodes,edges,nodeMap,totalPapers:scopeIssues.reduce((s,i)=>s+i.papers.length,0)};
}

function layoutGraph(model,W,H){
  const issues=model.nodes.filter(n=>n.type==='issue');
  const topics=model.nodes.filter(n=>n.type==='topic').sort((a,b)=>b.data.count-a.data.count);
  const papers=model.nodes.filter(n=>n.type==='paper');
  const yMin=95,yMax=H-70;
  issues.forEach((n,i)=>{n.x=105;n.y=issues.length===1?H/2:yMin+(i/(issues.length-1))*(yMax-yMin)});
  topics.forEach((n,i)=>{n.x=470;n.y=topics.length===1?H/2:yMin+(i/(topics.length-1))*(yMax-yMin);n.w=180;n.h=44});
  const parent={};model.edges.forEach(e=>{if(e.kind==='topic-paper')parent[e.b]=e.a});
  const buckets={};papers.forEach(p=>(buckets[parent[p.id]]||(buckets[parent[p.id]]=[])).push(p));
  Object.entries(buckets).forEach(([tid,ps])=>{
    const t=model.nodeMap.get(tid); if(!t)return;
    const spots=ps.length===1?[[900,t.y]]:ps.length===2?[[790,t.y],[1020,t.y]]:[[770,t.y-20],[1000,t.y-20],[885,t.y+24]];
    ps.forEach((p,i)=>{p.x=spots[i][0];p.y=spots[i][1];p.w=198;p.h=30});
  });
}

function svgEl(tag,attrs={}){
  const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
  Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));
  return el;
}

function renderGraph(){
  const svg=$('#knowledgeGraph'); const W=1200,H=720; svg.innerHTML='';
  const model=buildGraphModel(); layoutGraph(model,W,H);
  const focus=state.graphFocus;
  const related=new Set();
  if(focus){related.add(focus);model.edges.forEach(e=>{if(e.a===focus)related.add(e.b);if(e.b===focus)related.add(e.a)})}
  model.edges.forEach(e=>{
    const A=model.nodeMap.get(e.a),B=model.nodeMap.get(e.b); if(!A||!B)return;
    const x1=A.type==='topic'?A.x+A.w/2:A.x+12;
    const x2=B.type==='topic'?B.x-B.w/2:B.x-B.w/2;
    const y1=A.y,y2=B.y,mid=x1+(x2-x1)*.48;
    const path=svgEl('path',{d:`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`,'stroke-width':e.kind==='issue-topic'?(1.2+Math.min(5,e.weight)*.65):1.1,class:`edge ${e.kind==='topic-paper'?'paper-edge':''}${focus&&e.a!==focus&&e.b!==focus?' edge-muted':''}${focus&&(e.a===focus||e.b===focus)?' edge-highlight':''}`});
    svg.appendChild(path);
  });
  model.nodes.forEach(n=>{
    const muted=focus&&!related.has(n.id);
    const highlighted=focus&&related.has(n.id);
    const g=svgEl('g',{class:`node${muted?' node-muted':''}${highlighted?' node-highlight':''}`});
    if(n.type==='issue')drawIssueNode(g,n);
    if(n.type==='topic')drawTopicNode(g,n);
    if(n.type==='paper')drawPaperNode(g,n);
    g.addEventListener('mouseenter',e=>tip(e,n));
    g.addEventListener('mouseleave',()=>$('#graphTooltip').style.display='none');
    g.addEventListener('click',()=>{
      if(n.type==='topic'){
        state.graphFocus=state.graphFocus===n.id?null:n.id;
        renderGraph();
      }else if(n.data.url)window.open(n.data.url,'_blank');
    });
    svg.appendChild(g);
  });
  renderGraphStats(model);
  renderInspector(model);
}

function drawIssueNode(g,n){
  g.appendChild(svgEl('circle',{cx:n.x,cy:n.y,r:15,fill:'#f2ad67',stroke:'#f8d4aa','stroke-width':1.2}));
  const date=svgEl('text',{x:n.x+25,y:n.y+4,fill:'#dce6ed','font-size':12,'font-weight':800,class:'node-label'});date.textContent=n.label.slice(5);g.appendChild(date);
  const count=svgEl('text',{x:n.x+25,y:n.y+19,fill:'#64788b','font-size':8,class:'node-label'});count.textContent=`${n.data.total} items`;g.appendChild(count);
}

function drawTopicNode(g,n){
  g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:13,class:'node-card topic-card'}));
  const label=svgEl('text',{x:n.x-n.w/2+13,y:n.y-2,fill:'#e8f4ef','font-size':11,'font-weight':750,class:'node-label'});label.textContent=n.label.length>16?n.label.slice(0,16)+'…':n.label;g.appendChild(label);
  const meta=svgEl('text',{x:n.x-n.w/2+13,y:n.y+13,fill:'#789889','font-size':8,class:'node-label'});meta.textContent=`${n.data.count} 条 · ${n.data.issueCount} 期`;g.appendChild(meta);
  const badge=svgEl('circle',{cx:n.x+n.w/2-16,cy:n.y,r:10,fill:'#244a42'});g.appendChild(badge);
  const num=svgEl('text',{x:n.x+n.w/2-16,y:n.y+3.5,fill:'#a8d9c5','font-size':8,'font-weight':850,'text-anchor':'middle',class:'node-label'});num.textContent=n.data.count;g.appendChild(num);
}

function drawPaperNode(g,n){
  g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:9,class:'node-card paper-card'}));
  const title=svgEl('text',{x:n.x-n.w/2+10,y:n.y+3,fill:'#c7d5e0','font-size':8.4,'font-weight':650,class:'node-label'});title.textContent=n.label.length>22?n.label.slice(0,22)+'…':n.label;g.appendChild(title);
  if(Number.isFinite(+n.data.score)){
    g.appendChild(svgEl('rect',{x:n.x+n.w/2-37,y:n.y-9,width:28,height:18,rx:6,class:'node-score'}));
    const score=svgEl('text',{x:n.x+n.w/2-23,y:n.y+3,fill:'#9cc5e2','font-size':8,'font-weight':850,'text-anchor':'middle',class:'node-label'});score.textContent=Math.round(+n.data.score);g.appendChild(score);
  }
}

function renderGraphStats(model){
  const representative=model.nodes.filter(n=>n.type==='paper').length;
  $('#graphStats').innerHTML=[['日报',model.scopeIssues.length],['专题',model.selected.length],['范围内条目',model.totalPapers],['代表工作',representative]].map(([k,v])=>`<span class="graph-stat"><b>${v}</b>${k}</span>`).join('');
}

function renderInspector(model){
  const box=$('#graphInspector');
  if(!state.graphFocus){
    box.innerHTML='<span class="inspector-kicker">RELATION LENS</span><h3>点击专题查看关联</h3><p>专题节点聚合跨期出现次数、关联论文数量和时间跨度；点击后只高亮真正有归档数据支撑的关系。</p><div class="inspector-tip">Issue → Topic 表示该期实际收录；Topic → Paper 表示归档中明确的专题归属。</div>';
    return;
  }
  const n=model.nodeMap.get(state.graphFocus); if(!n)return;
  const reps=n.data.representatives||[];
  box.innerHTML=`<span class="inspector-kicker">TOPIC FOCUS</span><h3>${esc(n.label)}</h3><p>${n.data.first===n.data.last?`本期首次/最近出现：${esc(n.data.last)}`:`从 ${esc(n.data.first)} 到 ${esc(n.data.last)} 持续出现`}。</p><div class="inspector-metrics"><div><b>${n.data.count}</b><small>关联条目</small></div><div><b>${n.data.issueCount}</b><small>涉及日报</small></div></div><div class="inspector-list">${reps.map(p=>`<span>${esc(p.title)}</span>`).join('')}</div><div class="inspector-tip">再次点击该专题可退出聚焦；高亮边均来自归档中的确定性归属。</div>`;
}

function tip(e,n){
  const box=$('#graphTooltip');let html=`<strong>${esc(n.label)}</strong>`;
  if(n.type==='paper') html+=`<br><span>${esc(n.data.topic||'')}</span>${n.data.score!=null?` · ${esc(n.data.score)}`:''}<br><em>点击打开原始来源</em>`;
  else if(n.type==='issue')html+=`<br>${esc(n.data.headline||'')}<br><em>点击打开已发送日报</em>`;
  else html+=`<br>${n.data.count} 条关联 · ${n.data.issueCount} 期<br><span>${esc(n.data.first)} → ${esc(n.data.last)}</span><br><em>点击聚焦专题关系</em>`;
  box.innerHTML=html;box.style.display='block';
  const rect=$('.graph-shell').getBoundingClientRect();
  box.style.left=Math.min(rect.width-315,Math.max(10,e.clientX-rect.left+14))+'px';
  box.style.top=Math.min(rect.height-120,Math.max(10,e.clientY-rect.top+14))+'px';
}

load().catch(err=>{console.error(err);$('#latestHeadline').textContent='归档数据读取失败，请刷新页面。';$('#kpis').innerHTML=`<div class="empty">${esc(err.message)}</div>`;});
