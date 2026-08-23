const ROOT = './archive';
const KNOWLEDGE_ROOT = './knowledge';
const COLORS = ['#7697ef','#62b795','#e6a45e','#9b83d4','#db7474','#55afc2','#c6a247'];
const state = {
  issues: [], items: [], latest: null, itemById: new Map(),
  knowledge: null, knowledgeError: null, featurePlan: null, objectCache: new Map(),
  route: {name:'home',params:{}}, graphScope: 'latest', graphMode: 'topic',
  roles: new Set(['core','supplement','radar']), keyword: '', keywordSuggestions: [],
  view: null, drag: null, lastLayout: null, feedback: null,
};
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const esc = (value = '') => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const norm = BriefingData.norm;
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const truncate = (value, length) => { const text = String(value || ''); return text.length > length ? `${text.slice(0,length-1)}…` : text; };

async function getJson(url) {
  const response = await fetch(url, {cache:'no-store'});
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}
async function optionalJson(url) { try { return await getJson(url); } catch (_) { return null; } }

function inferKeywords(item) {
  const result = new Set((item.keywords || []).filter(Boolean));
  if (item.topic_name) result.add(item.topic_name);
  if (item.direction_name) result.add(item.direction_name);
  const haystack = [item.title,item.summary,item.topic_name,item.direction_name].filter(Boolean).join(' ');
  ['KVCache','KV Cache','Agent','agentic','RDMA','DPU','CXL','MoE','GPU','NPU','TPN','MCP','Prefill','Decode','harness','FlashAttention','NAND','推理','存储','网络','内存','跨域','调度','缓存','工具链'].forEach(keyword => {
    if (norm(haystack).includes(norm(keyword))) result.add(keyword);
  });
  (haystack.match(/[A-Za-z][A-Za-z0-9+._-]{2,}/g) || []).filter(word => word.length <= 24).forEach(word => result.add(word));
  return [...result].slice(0,24);
}

function itemSourceUrl(detail, paper) {
  return paper.url || detail.url || detail.sources?.find(source => source.primary)?.url || detail.sources?.[0]?.url || '';
}

async function loadArchiveIssue(meta) {
  const base = `${ROOT}/issues/${meta.date}`;
  const [papers, issueDoc, reader, manifest] = await Promise.all([
    getJson(`${ROOT}/${meta.papers_file}`),
    optionalJson(`${base}/issue.json`).then(value => value || {}),
    optionalJson(`${base}/reader.json`),
    optionalJson(`${base}/publication-manifest.json`),
  ]);
  const machineMap = BriefingData.collectItemMap(issueDoc);
  const readerMap = BriefingData.collectItemMap(reader);
  const paperRows = papers.map((paper,index) => {
    const id = BriefingData.itemId(paper) || `${meta.date}:${index}`;
    const detail = machineMap.get(id) || {};
    const machine = {
      ...paper,
      id: paper.paper_key || id,
      item_id: id,
      issue_date: meta.date,
      url: itemSourceUrl(detail,paper),
      summary: detail.core_conclusion || detail.summary || detail.project_relevance || '',
      direction_name: detail.direction_name || paper.direction_name || paper.direction_id || '',
      keywords: detail.keywords || paper.keywords || [],
      detail,
    };
    const merged = BriefingData.mergeReaderItem(machine, readerMap.get(id));
    merged.keywords = inferKeywords(merged);
    return merged;
  });
  const derivedRadar = BriefingData.radarFromIssue(issueDoc, meta.date).map(row => {
    const radarIdentity = BriefingData.canonicalIdentity(row, location.href);
    const readerRow = (reader?.radar || []).find(candidate =>
      BriefingData.canonicalIdentity(candidate, location.href) === radarIdentity
    );
    const merged = BriefingData.mergeReaderItem(row, readerRow);
    merged.keywords = inferKeywords(merged);
    return merged;
  });
  const allItems = BriefingData.mergeRadarWithoutDuplicates(paperRows, derivedRadar, location.href);
  return {
    ...meta,
    headline: BriefingData.readerHeadline(reader, meta.headline),
    machine_headline: meta.headline,
    papers: allItems,
    radar: allItems.filter(row => row.role === 'radar'),
    issueDoc, reader, manifest,
    public_href: `${base}/email.html`,
    illustrated_href: `${base}/email-illustrated.html`,
    original_href: BriefingData.originalEmailPath(manifest, meta.date),
  };
}

async function loadData() {
  const [archive, featurePlan] = await Promise.all([
    getJson(`${ROOT}/index.json`),
    optionalJson('./feature-plan.json'),
  ]);
  const issues = await Promise.all((archive.issues || []).map(loadArchiveIssue));
  issues.sort((a,b) => a.date.localeCompare(b.date));
  state.issues = issues;
  state.items = issues.flatMap(issue => issue.papers);
  state.latest = issues.at(-1) || null;
  state.items.forEach(item => {
    [item.item_id,item.brief_item_id,item.detail?.brief_item_id,item.id].filter(Boolean).forEach(id => state.itemById.set(String(id),item));
  });
  state.keywordSuggestions = buildKeywordSuggestions();
  state.featurePlan = featurePlan;
  try {
    state.knowledge = BriefingData.validateKnowledgeIndex(await getJson(`${KNOWLEDGE_ROOT}/index.json`));
  } catch (error) {
    state.knowledgeError = error;
  }
}

async function loadKnowledgeObject(path) {
  const url = BriefingData.knowledgePath(path);
  if (!url) throw new Error('知识对象缺少 path');
  if (!state.objectCache.has(url)) state.objectCache.set(url, getJson(url));
  return state.objectCache.get(url);
}

function issueHref(date) { return `${ROOT}/issues/${date}/email.html`; }
function roleName(role) { return role === 'core' ? '深度解读' : role === 'supplement' ? '专题补充' : '今日雷达'; }
function itemKey(item) { return String(item?.item_id || item?.brief_item_id || item?.detail?.brief_item_id || item?.id || ''); }
function evidenceItem(reference) {
  const id = typeof reference === 'string' ? reference : reference?.item_id || reference?.brief_item_id || reference?.evidence_item_id;
  return id ? state.itemById.get(String(id)) : null;
}

function buildKeywordSuggestions() {
  const frequency = new Map();
  state.items.forEach(item => (item.keywords || []).forEach(keyword => {
    if (keyword && keyword.length > 1 && keyword.length < 28) frequency.set(keyword,(frequency.get(keyword)||0)+1);
  }));
  return [...frequency.entries()].filter(([,count]) => count >= 2).sort((a,b) => b[1]-a[1] || a[0].length-b[0].length).slice(0,18);
}

function renderKeywordChips() {
  $('#keywordChips').innerHTML = state.keywordSuggestions.map(([keyword,count]) => `<button class="keyword-chip${norm(keyword)===norm(state.keyword)?' active':''}" data-keyword="${esc(keyword)}">${esc(keyword)} · ${count}</button>`).join('');
  $$('.keyword-chip').forEach(button => button.addEventListener('click',() => {
    state.keyword = button.dataset.keyword; $('#keywordInput').value = state.keyword; renderKeywordChips(); renderGraph(true);
  }));
}

function bindGraphControls() {
  $$('#scopeSwitch button').forEach(button => button.addEventListener('click',() => {
    $$('#scopeSwitch button').forEach(row => row.classList.remove('active')); button.classList.add('active'); state.graphScope=button.dataset.scope; renderGraph(true);
  }));
  $$('#modeSwitch button').forEach(button => button.addEventListener('click',() => {
    $$('#modeSwitch button').forEach(row => row.classList.remove('active')); button.classList.add('active'); state.graphMode=button.dataset.mode;
    $('#keywordPanel').hidden=state.graphMode!=='keyword';
    if(state.graphMode==='keyword'&&!state.keyword){state.keyword=state.keywordSuggestions[0]?.[0]||'Agent';$('#keywordInput').value=state.keyword;renderKeywordChips();}
    renderGraph(true);
  }));
  $$('.role-control input').forEach(input => input.addEventListener('change',() => { input.checked?state.roles.add(input.dataset.role):state.roles.delete(input.dataset.role);renderGraph(true); }));
  $('#keywordApply').addEventListener('click',() => {state.keyword=$('#keywordInput').value.trim()||state.keywordSuggestions[0]?.[0]||'Agent';renderKeywordChips();renderGraph(true);});
  $('#keywordInput').addEventListener('keydown',event => {if(event.key==='Enter')$('#keywordApply').click();});
  $('#zoomIn').addEventListener('click',()=>zoomGraph(.78)); $('#zoomOut').addEventListener('click',()=>zoomGraph(1.28)); $('#zoomReset').addEventListener('click',resetGraphView);
  initPanZoom();
}

function scopedItems() {
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const dates=new Set(issues.filter(Boolean).map(issue=>issue.date));
  return state.items.filter(item=>dates.has(item.issue_date)&&state.roles.has(item.role));
}
function matchesKeyword(item,query) {
  const needle=norm(query); if(!needle)return true;
  return [item.title,item.summary,item.topic_name,item.direction_name,...(item.keywords||[])].some(value=>{const candidate=norm(value);return candidate.includes(needle)||(candidate.length>2&&needle.includes(candidate));});
}
function topicModel() {
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const items=scopedItems(); const topics=new Map();
  items.forEach(item=>{const topic=item.topic_name||'未分类';if(!topics.has(topic))topics.set(topic,{name:topic,items:[],dates:new Set()});const group=topics.get(topic);group.items.push(item);group.dates.add(item.issue_date);});
  const issueCounts=new Map(); items.forEach(item=>{const key=`${item.issue_date}|||${item.topic_name||'未分类'}`;issueCounts.set(key,(issueCounts.get(key)||0)+1);});
  return {mode:'topic',issues,items,groups:[...topics.values()].sort((a,b)=>b.items.length-a.items.length),issueCounts};
}
function keywordModel() {
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const query=state.keyword||state.keywordSuggestions[0]?.[0]||'Agent'; const items=scopedItems().filter(item=>matchesKeyword(item,query)); const groups=new Map();
  items.forEach(item=>{const topic=item.topic_name||'未分类';if(!groups.has(topic))groups.set(topic,{name:topic,items:[],dates:new Set()});const group=groups.get(topic);group.items.push(item);group.dates.add(item.issue_date);});
  return {mode:'keyword',issues,items,groups:[...groups.values()].sort((a,b)=>b.items.length-a.items.length),keyword:query};
}

function renderGraph(reset=false) {
  const model=state.graphMode==='keyword'?keywordModel():topicModel();
  const layout=state.graphMode==='keyword'?layoutKeyword(model):layoutTopic(model);
  drawGraph(model,layout);renderGraphStats(model);renderInspector(null,model);if(reset)fitGraph(layout);
}
function layoutTopic(model){return {nodes:[],edges:[],W:1200,H:700};}
function layoutKeyword(model){return layoutTopic(model);}
function svgEl(tag,attrs={}){const element=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([key,value])=>element.setAttribute(key,value));return element;}
function textNode(group,value,x,y,size,className,anchor='start'){const node=svgEl('text',{x,y,'font-size':size,class:className,'text-anchor':anchor});node.textContent=value;group.appendChild(node);}
function drawGraph() {}
function countRoles(items){return items.reduce((counts,item)=>(counts[item.role]=(counts[item.role]||0)+1,counts),{core:0,supplement:0,radar:0});}
function renderGraphStats(model){const roles=countRoles(model.items);$('#graphStats').innerHTML=[['条目',model.items.length],['专题',new Set(model.items.map(item=>item.topic_name)).size],['深度',roles.core],['简要',roles.supplement],['雷达',roles.radar]].map(([label,value])=>`<span class="graph-stat"><b>${esc(value)}</b>${label}</span>`).join('');}
function renderInspector(node,model){
  const pane=$('#detailPane');
  if(!node){pane.innerHTML=`<div class="detail-placeholder"><span>EVIDENCE EXPLORER</span><h2>${model.mode==='keyword'?`关键词「${esc(model.keyword)}」`:'选择图谱节点'}</h2><p>图中关系仅来自归档结构或显式关键词，不推断 EXTENDS / USES 等语义边。</p></div>`;return;}
  if(node.type==='item'){renderItemDetail(node.data);return;}
  pane.innerHTML=`<div class="detail-placeholder"><span>${esc(node.type.toUpperCase())}</span><h2>${esc(node.label)}</h2><p>${node.type==='topic'?`${node.data.items.length} 条公开记录，涉及 ${node.data.dates.size} 期日报。`:'点击节点查看公开证据。'}</p></div>`;
}
function showTip(event,node){const tip=$('#graphTooltip');tip.innerHTML=`<b>${esc(node.label)}</b>`;tip.style.display='block';tip.style.left=`${Math.min(window.innerWidth-300,event.clientX+14)}px`;tip.style.top=`${Math.min(window.innerHeight-100,event.clientY+14)}px`;}
function fitGraph(layout=state.lastLayout){if(!layout)return;state.view={x:0,y:0,w:layout.W,h:layout.H};applyView();}
function resetGraphView(){fitGraph();}
function applyView(){if(state.view)$('#knowledgeGraph').setAttribute('viewBox',`${state.view.x} ${state.view.y} ${state.view.w} ${state.view.h}`);}
function zoomGraph(factor,cx=.5,cy=.5){if(!state.view)return;const view=state.view,nw=view.w*factor,nh=view.h*factor;view.x+=view.w*cx-nw*cx;view.y+=view.h*cy-nh*cy;view.w=nw;view.h=nh;applyView();}
function initPanZoom() {}

function canonicalIdentity(item) { return BriefingData.canonicalIdentity(item, location.href); }

function feedbackButtons(targetType,targetId,positive,negative) {
  const current=state.feedback.current(targetType,targetId);
  return `<div class="feedback-buttons" data-feedback-target="${esc(targetId)}" data-feedback-type="${esc(targetType)}"><button data-reaction="${esc(positive[0])}" class="${current===positive[0]?'active':''}">${esc(positive[1])}</button><button data-reaction="${esc(negative[0])}" class="${current===negative[0]?'active':''}">${esc(negative[1])}</button></div>`;
}
function updateFeedbackCount(){if(state.feedback)$('#feedbackCount').textContent=`${state.feedback.listEvents().length} 条本地事件`;}
function bindFeedbackEvents(container=document) {
  container.querySelectorAll?.('.feedback-buttons button').forEach(button=>button.addEventListener('click',event=>{
    event.stopPropagation();const wrap=button.closest('.feedback-buttons');state.feedback.toggle(wrap.dataset.feedbackType,wrap.dataset.feedbackTarget,button.dataset.reaction);
    wrap.querySelectorAll('button').forEach(row=>row.classList.toggle('active',state.feedback.current(wrap.dataset.feedbackType,wrap.dataset.feedbackTarget)===row.dataset.reaction));updateFeedbackCount();
  }));
}
function renderItemDetail(item) {
  const id=itemKey(item);const machine=item.detail||{};
  $('#detailPane').innerHTML=`<div class="detail-kicker">${esc(roleName(item.role))} · ${esc(item.issue_date||'')}</div><h2>${esc(item.title)}</h2><p class="detail-lead">${esc(item.summary||'暂无读者摘要。')}</p><dl class="detail-fields"><dt>专题 / 方向</dt><dd>${esc(item.topic_name||'未分类')} · ${esc(item.direction_name||'未标注')}</dd>${machine.boundary?`<dt>适用边界</dt><dd>${esc(machine.boundary)}</dd>`:''}${machine.project_relevance?`<dt>项目启发</dt><dd>${esc(machine.project_relevance)}</dd>`:''}</dl><div class="detail-actions"><a href="${esc(item.url||issueHref(item.issue_date))}" target="_blank" rel="noreferrer">原始来源 ↗</a><a href="${issueHref(item.issue_date)}" target="_blank" rel="noreferrer">当期公开阅读版 ↗</a></div>${feedbackButtons('brief_item',id,['interested','感兴趣'],['not_interested','不感兴趣'])}<p class="feedback-note">仅保存在当前浏览器，不参与真实筛选。</p>`;
  bindFeedbackEvents($('#detailPane'));
}

function downloadFeedback() {
  const blob=new Blob([JSON.stringify(state.feedback.exportData(),null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='technical-briefing-feedback.json';anchor.click();URL.revokeObjectURL(url);
}

async function bootWorkbench() {
  state.feedback=new BriefingFeedback.LocalFeedbackStore(window.localStorage);
  $('#exportFeedback').addEventListener('click',downloadFeedback);
  $('#clearFeedback').addEventListener('click',()=>{if(window.confirm('清空当前浏览器中的演示反馈？')){state.feedback.clear();updateFeedbackCount();renderRoute();}});
  updateFeedbackCount();
  bindGraphControls(); renderKeywordChips();
  window.addEventListener('hashchange',renderRoute);
  try { await loadData(); }
  catch(error){ $('#loadBanner').hidden=false;$('#loadBanner').textContent=`站点数据加载失败：${error.message}`;return; }
  renderKeywordChips();
  if(state.knowledgeError){$('#loadBanner').hidden=false;$('#loadBanner').textContent='Roadmap / Idea 物化数据尚不可用；日报与证据图谱仍可查看。';}
  renderRoute();
}

function renderRoute() {
  state.route=BriefingData.parseRoute(location.hash);
  $$('.primary-nav a').forEach(link=>link.classList.toggle('active',link.dataset.route===state.route.name));
  $$('.view').forEach(view=>view.hidden=view.dataset.view!==state.route.name);
  $('#mainPane').scrollTop=0;$('#detailPane').scrollTop=0;
  if(typeof renderWorkbenchView==='function')renderWorkbenchView(state.route);
  if(state.route.name==='atlas')requestAnimationFrame(()=>renderGraph(true));
}
