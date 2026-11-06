/* Atlas interaction + canonical-node fixes: click-safe pan/zoom and cross-issue deduplication. */

function canonicalIdentity(item) {
  const arxiv = String(item.arxiv_id || '').trim().replace(/v\d+$/i, '');
  if (arxiv) return `arxiv:${arxiv.toLowerCase()}`;
  const rawUrl = String(item.url || '').trim();
  if (rawUrl) {
    try {
      const u = new URL(rawUrl, window.location.href);
      u.hash = '';
      [...u.searchParams.keys()].forEach(key => {
        if (/^(?:utm_.+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|igshid)$/i.test(key)) {
          u.searchParams.delete(key);
        }
      });
      u.searchParams.sort();
      let path = u.pathname.replace(/\/$/, '');
      if (/arxiv\.org$/i.test(u.hostname)) path = path.replace(/v\d+$/i, '');
      return `url:${u.hostname.toLowerCase()}${path.toLowerCase()}${u.search}`;
    } catch (_) {
      return `url:${rawUrl.replace(/#.*$/, '').replace(/\/$/, '').toLowerCase()}`;
    }
  }
  if (item.paper_key) return `key:${String(item.paper_key).toLowerCase()}`;
  const title = norm(item.title || '');
  return `title:${title || String(item.id || item.item_id || '')}`;
}

function rolePriority(role) {
  return role === 'core' ? 3 : role === 'supplement' ? 2 : 1;
}

function canonicalizeItems(rawItems) {
  const byKey = new Map();
  rawItems.forEach((item, order) => {
    const key = canonicalIdentity(item);
    const occurrence = {
      issue_date: item.issue_date,
      role: item.role,
      topic_name: item.topic_name,
      title: item.title,
      url: item.url,
      item_id: item.item_id || item.id
    };
    if (!byKey.has(key)) {
      byKey.set(key, {
        ...item,
        id: `canonical:${key}`,
        canonical_key: key,
        occurrences: [occurrence],
        issue_dates: [item.issue_date].filter(Boolean),
        occurrence_count: 1,
        _first_order: order
      });
      return;
    }
    const current = byKey.get(key);
    current.occurrences.push(occurrence);
    current.issue_dates = [...new Set([...current.issue_dates, item.issue_date].filter(Boolean))].sort();
    current.occurrence_count = current.occurrences.length;
    current.keywords = [...new Set([...(current.keywords || []), ...(item.keywords || [])])];
    if (!current.url && item.url) current.url = item.url;
    if (Number.isFinite(+item.score) && (!Number.isFinite(+current.score) || +item.score > +current.score)) current.score = item.score;
    if (rolePriority(item.role) > rolePriority(current.role)) current.role = item.role;
    if ((item.issue_date || '') >= (current.issue_date || '')) {
      current.issue_date = item.issue_date || current.issue_date;
      current.title = item.title || current.title;
      current.summary = item.summary || current.summary;
      current.topic_name = item.topic_name || current.topic_name;
      current.topic_id = item.topic_id || current.topic_id;
      current.direction_name = item.direction_name || current.direction_name;
      current.direction_id = item.direction_id || current.direction_id;
    }
  });
  return [...byKey.values()].sort((a,b)=>a._first_order-b._first_order);
}

function buildIssueTopicCounts(rawItems) {
  const counts = new Map();
  const seen = new Set();
  rawItems.forEach(item => {
    const topic = item.topic_name || '未分类';
    const dedupeKey = `${item.issue_date}|||${topic}|||${canonicalIdentity(item)}`;
    if (seen.has(dedupeKey)) return;
    seen.add(dedupeKey);
    const edgeKey = `${item.issue_date}|||${topic}`;
    counts.set(edgeKey, (counts.get(edgeKey) || 0) + 1);
  });
  return counts;
}

function topicModel(){
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const rawItems=scopedItems();
  const items=canonicalizeItems(rawItems);
  const topics=new Map();
  items.forEach(item=>{
    const t=item.topic_name||'未分类';
    if(!topics.has(t))topics.set(t,{name:t,items:[],dates:new Set()});
    const x=topics.get(t);x.items.push(item);
    (item.issue_dates||[item.issue_date]).forEach(d=>d&&x.dates.add(d));
  });
  const groups=[...topics.values()].sort((a,b)=>b.items.length-a.items.length);
  return {mode:'topic',issues,items,rawItems,groups,issueCounts:buildIssueTopicCounts(rawItems),duplicateCount:rawItems.length-items.length};
}

function keywordModel(){
  const issues=state.graphScope==='latest'?[state.latest]:state.issues;
  const all=scopedItems();
  const q=state.keyword||state.keywordSuggestions[0]?.[0]||'Agent';
  const rawItems=all.filter(i=>matchesKeyword(i,q));
  const items=canonicalizeItems(rawItems);
  const map=new Map();
  items.forEach(item=>{
    const t=item.topic_name||'未分类';
    if(!map.has(t))map.set(t,{name:t,items:[],dates:new Set()});
    const g=map.get(t);g.items.push(item);
    (item.issue_dates||[item.issue_date]).forEach(d=>d&&g.dates.add(d));
  });
  return {mode:'keyword',issues,items,rawItems,groups:[...map.values()].sort((a,b)=>b.items.length-a.items.length),keyword:q,duplicateCount:rawItems.length-items.length};
}

function renderGraphStats(model){
  const roles=countRoles(model.items);
  const topics=new Set(model.items.map(i=>i.topic_name));
  const rawCount=model.rawItems?.length??model.items.length;
  const duplicateCount=Math.max(0,rawCount-model.items.length);
  $('#graphStats').innerHTML=[
    ['唯一节点',model.items.length],
    ['原始记录',rawCount],
    ['合并重复',duplicateCount],
    ['专题',topics.size],
    ['深度',roles.core],
    ['简要',roles.supplement],
    ['雷达',roles.radar],
    ...(model.mode==='keyword'?[['中心关键词',model.keyword]]:[])
  ].map(([k,v])=>`<span class="graph-stat"><b>${esc(v)}</b>${k}</span>`).join('');
}

function initPanZoom(){
  const svg=$('#knowledgeGraph');
  if(!svg || svg.dataset.panZoomV3==='1') return;
  svg.dataset.panZoomV3='1';
  svg.addEventListener('wheel',e=>{
    e.preventDefault();
    const r=svg.getBoundingClientRect();
    zoomGraph(e.deltaY<0?.82:1.22,clamp((e.clientX-r.left)/r.width,0,1),clamp((e.clientY-r.top)/r.height,0,1));
  },{passive:false});
  svg.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;
    if(e.target?.closest?.('.node'))return;
    state.drag={pointerId:e.pointerId,x:e.clientX,y:e.clientY,view:{...state.view},moved:false};
  });
  svg.addEventListener('pointermove',e=>{
    if(!state.drag||state.drag.pointerId!==e.pointerId)return;
    const total=Math.hypot(e.clientX-state.drag.x,e.clientY-state.drag.y);
    if(!state.drag.moved&&total<5)return;
    if(!state.drag.moved){
      state.drag.moved=true;
      svg.setPointerCapture(e.pointerId);
      svg.classList.add('dragging');
    }
    const r=svg.getBoundingClientRect();
    const dx=(e.clientX-state.drag.x)/r.width*state.drag.view.w;
    const dy=(e.clientY-state.drag.y)/r.height*state.drag.view.h;
    state.view={...state.drag.view,x:state.drag.view.x-dx,y:state.drag.view.y-dy};
    applyView();
  });
  const end=()=>{
    if(!state.drag)return;
    const moved=state.drag.moved;
    state.drag=null;
    svg.classList.remove('dragging');
    if(moved) state.suppressGraphClickUntil=performance.now()+120;
  };
  svg.addEventListener('pointerup',end);
  svg.addEventListener('pointercancel',end);
  svg.addEventListener('click',e=>{
    if((state.suppressGraphClickUntil||0)>performance.now()){
      e.preventDefault();e.stopImmediatePropagation();
    }
  },true);
}
