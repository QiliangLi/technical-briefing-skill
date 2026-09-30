/* Atlas readability layer: collision-free lanes, semantic zoom, progressive disclosure. */
state.expandedClusters = state.expandedClusters || new Set();
state.focusTopic = state.focusTopic || '';

function clusterKey(group, role) { return `${state.graphMode}:${state.graphScope}:${group.name}:${role}`; }
function splitRoles(items) {
  return {
    core: items.filter(i => i.role === 'core'),
    supplement: items.filter(i => i.role === 'supplement'),
    radar: items.filter(i => i.role === 'radar')
  };
}
function rolePreview(group, role, previewCount) {
  const items = splitRoles(group.items)[role] || [];
  if (!items.length) return [];
  const key = clusterKey(group, role);
  const expanded = state.expandedClusters.has(key);
  if (items.length <= previewCount + 1) return items.map(item => ({kind:'item', item}));
  if (expanded) {
    return [
      ...items.map(item => ({kind:'item', item})),
      {kind:'aggregate', action:'collapse', role, key, group, count:items.length, items}
    ];
  }
  return [
    ...items.slice(0, previewCount).map(item => ({kind:'item', item})),
    {kind:'aggregate', action:'expand', role, key, group, count:items.length-previewCount, total:items.length, items:items.slice(previewCount)}
  ];
}
function visibleEntries(group) {
  return [
    ...splitRoles(group.items).core.map(item => ({kind:'item', item})),
    ...rolePreview(group, 'supplement', 2),
    ...rolePreview(group, 'radar', 1)
  ];
}

function renderGraph(reset=false){
  const model=state.graphMode==='keyword'?keywordModel():topicModel();
  if (state.focusTopic && !model.groups.some(g=>g.name===state.focusTopic)) state.focusTopic='';
  const layout=state.graphMode==='keyword'?layoutKeyword(model):layoutTopic(model);
  drawGraph(model,layout);
  renderGraphStats(model);
  renderInspector(null,model);
  if(reset) fitGraph(layout); else applyView();
}

function layoutTopic(model){
  const W=1540, issueX=105, topicX=445, itemXs=[785,1060,1335];
  const itemW=238, itemH=38, rowH=48, groupGap=64, top=86;
  const nodes=[], edges=[], topicBlocks=[];
  let y=top;
  model.groups.forEach(group=>{
    const entries=visibleEntries(group);
    const rows=Math.max(1,Math.ceil(entries.length/itemXs.length));
    const blockH=Math.max(92,rows*rowH+22);
    const mid=y+blockH/2;
    const topic={id:`topic:${group.name}`,type:'topic',label:group.name,x:topicX,y:mid,w:210,h:50,data:group,topic:group.name};
    nodes.push(topic); topicBlocks.push({group,topic,y,blockH});
    entries.forEach((entry,j)=>{
      const row=Math.floor(j/itemXs.length), col=j%itemXs.length;
      if(entry.kind==='item'){
        const item=entry.item;
        const node={id:`item:${item.issue_date}:${item.id}`,type:'item',label:item.title,x:itemXs[col],y:y+28+row*rowH,w:itemW,h:itemH,data:item,topic:group.name};
        nodes.push(node); edges.push({a:topic,b:node,kind:'item',weight:1,topic:group.name});
      }else{
        const role=entry.role;
        const node={id:`aggregate:${entry.key}`,type:'aggregate',label:entry.action==='expand'?`+${entry.count} ${roleName(role)}`:`收起 ${roleName(role)}`,x:itemXs[col],y:y+28+row*rowH,w:itemW,h:itemH,data:entry,topic:group.name};
        nodes.push(node); edges.push({a:topic,b:node,kind:'aggregate',weight:entry.count||1,topic:group.name});
      }
    });
    y+=blockH+groupGap;
  });
  const H=Math.max(780,y+40);
  const issueNodes=new Map();
  const issueCount=model.issues.length;
  model.issues.forEach((issue,idx)=>{
    const iy=issueCount===1?H/2:100+idx*((H-200)/(issueCount-1));
    const node={id:`issue:${issue.date}`,type:'issue',label:issue.date,x:issueX,y:iy,data:issue};
    issueNodes.set(issue.date,node); nodes.push(node);
  });
  topicBlocks.forEach(({group,topic})=>{
    model.issues.forEach(issue=>{
      const weight=model.issueCounts.get(`${issue.date}|||${group.name}`)||0;
      if(weight) edges.push({a:issueNodes.get(issue.date),b:topic,kind:'issue',weight,topic:group.name});
    });
  });
  return {nodes,edges,W,H};
}

function layoutKeyword(model){
  const entriesByGroup=model.groups.map(group=>({group,entries:visibleEntries(group)}));
  const weights=entriesByGroup.map(x=>Math.max(2,x.entries.length));
  const total=Math.max(1,weights.reduce((a,b)=>a+b,0));
  const maxEntries=Math.max(1,...entriesByGroup.map(x=>x.entries.length));
  const maxR=610+Math.ceil(maxEntries/4)*115;
  const size=Math.max(1500,maxR*2+360), W=size,H=size,cx=W/2,cy=H/2;
  const nodes=[],edges=[];
  const center={id:`keyword:${model.keyword}`,type:'keyword',label:model.keyword,x:cx,y:cy,w:240,h:62,data:{count:model.items.length}};
  nodes.push(center);
  let cursor=-Math.PI/2;
  entriesByGroup.forEach(({group,entries},idx)=>{
    const span=(Math.PI*2)*(weights[idx]/total);
    const margin=Math.min(.12,span*.16);
    const start=cursor+margin, end=cursor+span-margin, mid=cursor+span/2;
    const topicR=270;
    const topic={id:`topic:${group.name}`,type:'topic',label:group.name,x:cx+Math.cos(mid)*topicR,y:cy+Math.sin(mid)*topicR,w:190,h:48,data:group,topic:group.name};
    nodes.push(topic); edges.push({a:center,b:topic,kind:'keyword',weight:group.items.length,topic:group.name});
    const usable=Math.max(.08,end-start);
    let placed=0, ring=0;
    while(placed<entries.length){
      const radius=510+ring*125;
      const capacity=Math.max(1,Math.floor(usable*radius/255));
      const take=Math.min(capacity,entries.length-placed);
      for(let j=0;j<take;j++){
        const frac=take===1?.5:(j+.5)/take;
        const ang=start+usable*frac;
        const entry=entries[placed+j];
        if(entry.kind==='item'){
          const item=entry.item;
          const node={id:`item:${item.issue_date}:${item.id}`,type:'item',label:item.title,x:cx+Math.cos(ang)*radius,y:cy+Math.sin(ang)*radius,w:224,h:38,data:item,topic:group.name};
          nodes.push(node); edges.push({a:topic,b:node,kind:'item',weight:1,topic:group.name});
        }else{
          const node={id:`aggregate:${entry.key}`,type:'aggregate',label:entry.action==='expand'?`+${entry.count} ${roleName(entry.role)}`:`收起 ${roleName(entry.role)}`,x:cx+Math.cos(ang)*radius,y:cy+Math.sin(ang)*radius,w:224,h:38,data:entry,topic:group.name};
          nodes.push(node); edges.push({a:topic,b:node,kind:'aggregate',weight:entry.count||1,topic:group.name});
        }
      }
      placed+=take; ring++;
    }
    cursor+=span;
  });
  return {nodes,edges,W,H};
}

function drawGraph(model,layout){
  const svg=$('#knowledgeGraph'); svg.innerHTML='';
  const edgesG=svgEl('g',{class:'atlas-edges'}),nodesG=svgEl('g',{class:'atlas-nodes'}); svg.append(edgesG,nodesG);
  layout.edges.forEach(e=>{
    const a=e.a,b=e.b;
    const curve=state.graphMode==='keyword'
      ? `M ${a.x} ${a.y} Q ${(a.x+b.x)/2} ${(a.y+b.y)/2} ${b.x} ${b.y}`
      : `M ${a.x} ${a.y} C ${a.x+(b.x-a.x)*.46} ${a.y}, ${b.x-(b.x-a.x)*.38} ${b.y}, ${b.x} ${b.y}`;
    const path=svgEl('path',{d:curve,class:`edge ${e.kind==='keyword'?'keyword-edge':e.kind==='item'?'item-edge':'aggregate-edge'}`,'stroke-width':e.kind==='item'?1:e.kind==='aggregate'?1.2:1.2+Math.min(7,e.weight)*.42,'data-topic':e.topic||''});
    if(state.focusTopic&&e.topic!==state.focusTopic)path.classList.add('is-dimmed');
    edgesG.appendChild(path);
  });
  layout.nodes.forEach(n=>{
    const g=svgEl('g',{class:`node node-${n.type}`,'data-topic':n.topic||''});
    if(state.focusTopic&&n.type!=='issue'&&n.type!=='keyword'&&n.topic!==state.focusTopic)g.classList.add('is-dimmed');
    drawNode(g,n);
    g.addEventListener('mouseenter',ev=>showTip(ev,n));
    g.addEventListener('mouseleave',()=>$('#graphTooltip').style.display='none');
    g.addEventListener('click',ev=>{
      ev.stopPropagation();
      if(n.type==='aggregate'){
        n.data.action==='expand'?state.expandedClusters.add(n.data.key):state.expandedClusters.delete(n.data.key);
        renderGraph(true); return;
      }
      if(n.type==='topic'){
        state.focusTopic=state.focusTopic===n.data.name?'':n.data.name;
        renderGraph(false); renderInspector(n,model); return;
      }
      renderInspector(n,model);
      if(n.type==='item'&&n.data.url)window.open(n.data.url,'_blank');
      if(n.type==='issue')window.open(`${ROOT}/issues/${n.data.date}/email.html`,'_blank');
    });
    nodesG.appendChild(g);
  });
  svg.onclick=()=>{if(state.focusTopic){state.focusTopic='';renderGraph(false)}};
  state.lastLayout=layout;
  updateSemanticZoom();
}

function drawNode(g,n){
  if(n.type==='issue'){
    g.appendChild(svgEl('circle',{cx:n.x,cy:n.y,r:14,class:'node-shape issue-node'}));
    textNode(g,n.label.slice(5),n.x+23,n.y+4,11,'node-title');
    textNode(g,`${n.data.papers?.length||0} items`,n.x+23,n.y+18,8,'node-sub'); return;
  }
  if(n.type==='keyword'){
    g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:20,class:'node-shape keyword-node'}));
    textNode(g,`⌕  ${truncate(n.label,22)}`,n.x-n.w/2+16,n.y-2,15,'node-title');
    textNode(g,`${n.data.count} matching items`,n.x-n.w/2+16,n.y+18,9,'node-sub'); return;
  }
  if(n.type==='topic'){
    g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:13,class:'node-shape topic-node'}));
    textNode(g,truncate(n.label,19),n.x-n.w/2+12,n.y-3,11,'node-title');
    textNode(g,`${n.data.items.length} 条 · ${n.data.dates.size} 期`,n.x-n.w/2+12,n.y+14,8,'node-sub'); return;
  }
  if(n.type==='aggregate'){
    const role=n.data.role;
    g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:10,class:`node-shape aggregate-node aggregate-${role}`}));
    textNode(g,n.label,n.x-n.w/2+15,n.y+4,9.5,'aggregate-label');
    textNode(g,n.data.action==='expand'?`点击展开，共 ${n.data.total} 条`:'点击折叠',n.x+n.w/2-10,n.y+4,7.5,'aggregate-hint','end'); return;
  }
  const role=n.data.role||'supplement';
  g.appendChild(svgEl('rect',{x:n.x-n.w/2,y:n.y-n.h/2,width:n.w,height:n.h,rx:8,class:`node-shape item-${role}`}));
  g.appendChild(svgEl('circle',{cx:n.x-n.w/2+11,cy:n.y-3,r:4,class:`role-badge-${role}`}));
  textNode(g,truncate(n.label,27),n.x-n.w/2+21,n.y-2,8.7,'node-title item-label');
  textNode(g,`${roleName(role)} · ${n.data.issue_date?.slice(5)||''}`,n.x-n.w/2+21,n.y+12,7.2,'node-sub item-meta');
}

function textNode(g,s,x,y,size,cls,anchor='start'){
  const t=svgEl('text',{x,y,'font-size':size,class:cls,'text-anchor':anchor});t.textContent=s;g.appendChild(t);
}

function showTip(ev,n){
  const tip=$('#graphTooltip'); let html=`<b>${esc(n.label)}</b>`;
  if(n.type==='item')html+=`<br><small>${roleName(n.data.role)} · ${esc(n.data.topic_name||'')}</small>${n.data.score?`<br>score ${n.data.score}`:''}`;
  if(n.type==='topic')html+=`<br><small>${n.data.items.length} 条 · ${n.data.dates.size} 期 · 点击聚焦</small>`;
  if(n.type==='aggregate')html+=`<br><small>${n.data.action==='expand'?'点击展开隐藏条目':'点击折叠该类条目'}</small>`;
  tip.innerHTML=html;tip.style.display='block';tip.style.left=`${Math.min(window.innerWidth-330,ev.clientX+14)}px`;tip.style.top=`${Math.min(window.innerHeight-120,ev.clientY+14)}px`;
}

const _baseRenderInspector=renderInspector;
renderInspector=function(n,model){
  if(n?.type==='aggregate'){
    const box=$('#detailPane');
    box.innerHTML=`<span class="inspector-kicker">PROGRESSIVE DISCLOSURE</span><h3>${esc(n.data.group.name)}</h3><p>${n.data.action==='expand'?`还有 ${n.data.count} 条${roleName(n.data.role)}被折叠，以避免密集节点互相遮挡。`:`当前已展开 ${n.data.count} 条${roleName(n.data.role)}。`}</p><div class="inspector-tip">点击聚合节点即可${n.data.action==='expand'?'展开':'收起'}；数据始终保留在图谱模型中。</div>`;
    return;
  }
  _baseRenderInspector(n,model);
}

function fitGraph(layout=state.lastLayout){
  if(!layout)return;
  const padX=40,padY=36;
  state.view={x:-padX,y:-padY,w:layout.W+padX*2,h:layout.H+padY*2};
  applyView();
}
function applyView(){
  if(!state.view)return;
  $('#knowledgeGraph').setAttribute('viewBox',`${state.view.x} ${state.view.y} ${state.view.w} ${state.view.h}`);
  updateSemanticZoom();
}
function zoomGraph(factor,cx=.5,cy=.5){
  if(!state.view)return;
  const v=state.view,layout=state.lastLayout||{W:v.w,H:v.h};
  const minW=Math.max(300,layout.W*.2),maxW=layout.W*1.8;
  const nw=clamp(v.w*factor,minW,maxW), ratio=nw/v.w, nh=v.h*ratio;
  v.x+=v.w*cx-nw*cx;v.y+=v.h*cy-nh*cy;v.w=nw;v.h=nh;applyView();
}
function updateSemanticZoom(){
  const svg=$('#knowledgeGraph'); if(!svg||!state.view||!state.lastLayout)return;
  const z=state.lastLayout.W/state.view.w;
  svg.classList.remove('zoom-far','zoom-mid','zoom-near');
  svg.classList.add(z<1.15?'zoom-far':z<2.15?'zoom-mid':'zoom-near');
}
