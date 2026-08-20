/* Workbench views. Roadmap and Idea views only consume materialized knowledge objects. */
const STATUS_LABELS={seed:'Seed',observing:'观察中',ready_for_validation:'待验证',promising:'有希望',rejected:'已淘汰',proposal_candidate:'立项候选'};
const IDEA_TYPE_LABELS={research_hypothesis:'研究假设',solution_concept:'技术方案'};
let viewRenderToken=0;

function missingKnowledge(message='knowledge/index.json 尚不存在或不符合合同。'){
  const template=$('#missingKnowledgeTemplate').content.cloneNode(true);template.querySelector('p').textContent=`${message} 系统不会用日期列表或 next_action 临时拼装替代品。`;return template;
}
function emptyBlock(message){return `<div class="empty-state">${esc(message)}</div>`;}
function setDetail(html){$('#detailPane').innerHTML=html;}
function setLeft(html=''){$('#leftContext').innerHTML=html;}
function go(route,params={}){const query=new URLSearchParams(params).toString();location.hash=`${route}${query?`?${query}`:''}`;}

function renderHome(){
  setLeft(`<div class="context-title">首页</div><p class="context-copy">只看最新一期、Roadmap 实质变化、Idea 状态和来源构成。</p>`);
  const latest=state.latest;
  if(!latest){$('#homeLatest').innerHTML=emptyBlock('暂无已发布日报');return;}
  $('#homeUpdated').textContent=`更新至 ${latest.date}`;
  $('#homeLatest').classList.remove('skeleton-card');
  $('#homeLatest').innerHTML=`<div><span class="status-pill">最新一期 · ${esc(latest.date)}</span><h2>${esc(latest.headline)}</h2><p>${latest.papers.filter(item=>item.role!=='radar').length} 条正式记录 · ${latest.radar.length} 条 Radar</p></div><div class="feature-actions"><a class="primary-action" href="${latest.public_href}" target="_blank">阅读公开版 ↗</a><button data-open-issue="${latest.date}">在工作台查看</button></div>`;
  $('#homeLatest [data-open-issue]').addEventListener('click',()=>go('archive',{date:latest.date}));

  if(!state.knowledge){
    $('#homeRoadmaps').replaceChildren(missingKnowledge('Roadmap 物化索引缺失。'));
    $('#homeIdeas').replaceChildren(missingKnowledge('Idea 物化索引缺失。'));
  }else{
    const roadmaps=[...state.knowledge.roadmaps].sort((a,b)=>String(b.updated_by_issue||'').localeCompare(String(a.updated_by_issue||''))).filter(row=>row.change_type!=='no_material_change').slice(0,4);
    $('#homeRoadmaps').innerHTML=roadmaps.length?roadmaps.map(row=>`<button class="compact-row" data-topic="${esc(row.topic_id)}"><span><b>${esc(row.topic_name)}</b><small>${esc(row.summary||'暂无变化摘要')}</small></span><em>${esc(row.change_type||'更新')}</em></button>`).join(''):emptyBlock('还没有 Roadmap 实质变化');
    $$('#homeRoadmaps [data-topic]').forEach(button=>button.addEventListener('click',()=>go('roadmaps',{topic:button.dataset.topic})));
    const ideas=[...state.knowledge.ideas].sort((a,b)=>String(b.last_updated_issue||'').localeCompare(String(a.last_updated_issue||''))).slice(0,4);
    $('#homeIdeas').innerHTML=ideas.length?ideas.map(row=>`<button class="compact-row" data-idea="${esc(row.idea_id)}"><span><b>${esc(row.title)}</b><small>${esc(IDEA_TYPE_LABELS[row.idea_type]||row.idea_type||'Idea')} · ${esc(row.last_updated_issue||'')}</small></span><em class="status-${esc(row.status)}">${esc(STATUS_LABELS[row.status]||row.status)}</em></button>`).join(''):emptyBlock('还没有物化 Idea');
    $$('#homeIdeas [data-idea]').forEach(button=>button.addEventListener('click',()=>go('ideas',{idea:button.dataset.idea})));
  }
  renderSourceDistribution(latest);
  setDetail(`<div class="detail-kicker">LATEST ISSUE</div><h2>${esc(latest.date)}</h2><p class="detail-lead">${esc(latest.headline)}</p><div class="detail-actions"><a href="${latest.public_href}" target="_blank">当前公开阅读版 ↗</a>${latest.original_href?`<a class="secondary-link" href="${esc(latest.original_href)}" target="_blank">查看实际发送版 ↗</a>`:''}</div><p class="detail-note">Roadmap 与 Idea 使用 Machine IDs 建立关联；Reader 文案只负责展示。</p>`);
}

function renderSourceDistribution(issue){
  const counts=new Map();
  issue.papers.forEach(item=>{let label='其他公开来源';try{const host=new URL(item.url).hostname.replace(/^www\./,'');label=host.includes('arxiv.org')?'arXiv':host.includes('github.com')?'GitHub':host||label;}catch(_){}counts.set(label,(counts.get(label)||0)+1);});
  const rows=[...counts.entries()].sort((a,b)=>b[1]-a[1]);const max=Math.max(1,...rows.map(([,count])=>count));
  $('#sourceDistribution').innerHTML=rows.length?rows.map(([label,count],index)=>`<div class="source-row"><span>${esc(label)}</span><i><b style="width:${count/max*100}%;--source-color:${COLORS[index%COLORS.length]}"></b></i><strong>${count}</strong></div>`).join(''):emptyBlock('本期没有可统计来源');
}

async function renderRoadmaps(route){
  const token=++viewRenderToken;
  if(!state.knowledge){setLeft('<div class="context-title">Roadmap</div>');$('#roadmapMain').replaceChildren(missingKnowledge(state.knowledgeError?.message));setDetail('<div class="detail-placeholder"><span>ROADMAP</span><h2>等待物化数据</h2><p>日报归档仍可独立查看。</p></div>');return;}
  const entries=state.knowledge.roadmaps;
  $('#roadmapMeta').textContent=`${entries.length} 个外部技术专题`;
  if(!entries.length){$('#roadmapMain').innerHTML=emptyBlock('尚无 Roadmap 对象');setLeft('');return;}
  const selected=entries.find(row=>row.topic_id===route.params.topic)||entries[0];
  setLeft(`<div class="context-title">选择专题</div><div class="context-list">${entries.map(row=>`<button data-topic="${esc(row.topic_id)}" class="${row.topic_id===selected.topic_id?'active':''}"><b>${esc(row.topic_name)}</b><small>v${esc(row.version)} · ${esc(row.updated_by_issue||'')}</small></button>`).join('')}</div><p class="context-copy">仅表达外部技术演进；证据范围为已发布日报。</p>`);
  $$('#leftContext [data-topic]').forEach(button=>button.addEventListener('click',()=>go('roadmaps',{topic:button.dataset.topic})));
  $('#roadmapMain').innerHTML='<div class="loading-state">正在加载 Roadmap 对象…</div>';
  try{
    const roadmap=await loadKnowledgeObject(selected.path);if(token!==viewRenderToken)return;
    const branches=Array.isArray(roadmap.branches)?roadmap.branches:[];
    const selectedBranch=branches.find(row=>row.branch_id===route.params.branch)||branches[0];
    $('#leftContext').insertAdjacentHTML('beforeend',`<div class="context-title secondary">技术分支</div><div class="context-list branch-list">${branches.map(row=>`<button data-branch="${esc(row.branch_id)}" class="${row===selectedBranch?'active':''}"><b>${esc(row.name)}</b><small>${esc(row.status||'')}</small></button>`).join('')||'<span class="quiet">尚未形成稳定分支</span>'}</div>`);
    $$('#leftContext [data-branch]').forEach(button=>button.addEventListener('click',()=>go('roadmaps',{topic:selected.topic_id,branch:button.dataset.branch})));
    renderRoadmapObject(roadmap,selectedBranch,selected);
  }catch(error){if(token===viewRenderToken){$('#roadmapMain').innerHTML=emptyBlock(`Roadmap 加载失败：${error.message}`);}}
}

function renderRoadmapObject(roadmap,branch,indexRow){
  const stages=branch?.stages||[];const timeline=branch?.evidence_timeline||roadmap.evidence_timeline||[];
  $('#roadmapMain').innerHTML=`<article class="object-hero"><div><span class="status-pill">${esc(roadmap.change_type||indexRow.change_type)} · v${esc(roadmap.version||indexRow.version)}</span><h2>${esc(indexRow.topic_name)}</h2><p>${esc(roadmap.summary||indexRow.summary||'暂无演进摘要')}</p></div><small>证据范围：${esc(roadmap.evidence_scope||'published_archive_only')}<br/>更新：${esc(roadmap.updated_by_issue||indexRow.updated_by_issue||'')}</small></article>${branch?`<div class="branch-heading"><h3>${esc(branch.name)}</h3><span>${esc(branch.status||'')}</span></div>`:''}<div class="stage-list">${stages.length?stages.map((stage,index)=>stageCard(stage,index)).join(''):timeline.length?`<div class="timeline-disclaimer">当前证据不足以识别可靠阶段，以下仅展示证据时间线。</div>${timeline.map((row,index)=>timelineCard(row,index)).join('')}`:emptyBlock('该分支尚无阶段或证据时间线')}</div>`;
  $$('#roadmapMain [data-stage]').forEach(button=>button.addEventListener('click',()=>renderRoadmapDetail(branch,stages[+button.dataset.stage])));
  $$('#roadmapMain [data-timeline]').forEach(button=>button.addEventListener('click',()=>renderRoadmapDetail(branch,timeline[+button.dataset.timeline],true)));
  if(stages[0])renderRoadmapDetail(branch,stages[0]);else if(timeline[0])renderRoadmapDetail(branch,timeline[0],true);else renderRoadmapDetail(branch,null);
}
function stageCard(stage,index){return `<button class="stage-card" data-stage="${index}"><span class="stage-index">${String(index+1).padStart(2,'0')}</span><div><div class="stage-top"><h3>${esc(stage.name||stage.title||`阶段 ${index+1}`)}</h3><em>${esc(stage.evidence_status||stage.status||'')}</em></div><p>${esc(stage.problem||stage.summary||stage.mechanism||'')}</p><small>${esc(stage.first_seen_issue||stage.started_at||'')} · ${(stage.evidence_item_ids||stage.evidence_for||[]).length} 条证据</small></div></button>`;}
function timelineCard(row,index){const item=evidenceItem(row);return `<button class="stage-card evidence-only" data-timeline="${index}"><span class="stage-index">${esc(row.issue_date||row.date||String(index+1).padStart(2,'0'))}</span><div><h3>${esc(row.title||item?.title||'证据记录')}</h3><p>${esc(row.reason||row.summary||row.change||'')}</p></div></button>`;}
function evidenceLinks(references){
  const rows=(references||[]).map(reference=>({reference,item:evidenceItem(reference)}));
  return rows.length?rows.map(({reference,item})=>{const id=typeof reference==='string'?reference:reference.item_id||reference.brief_item_id||'';return item?`<a href="${esc(item.url||issueHref(item.issue_date))}" target="_blank"><b>${esc(item.title)}</b><small>${esc(item.issue_date)} · ${esc(item.topic_name)}</small></a>`:`<span><b>证据 ${esc(id)}</b><small>当前归档索引未解析到该 Machine ID</small></span>`;}).join(''):'<span class="quiet">暂无引用证据</span>';
}
function renderRoadmapDetail(branch,row,isTimeline=false){
  if(!row){setDetail('<div class="detail-placeholder"><span>ROADMAP DETAIL</span><h2>暂无阶段</h2><p>材料不足时保持空白，不强造技术阶段。</p></div>');return;}
  const refs=row.item_id?[row]:row.evidence_item_ids||row.evidence_for||row.supporting_evidence||[];
  const linkedItem=isTimeline?evidenceItem(row):null;
  const mechanisms=Array.isArray(row.mechanisms)?row.mechanisms.join('；'):row.mechanism;
  setDetail(`<div class="detail-kicker">${isTimeline?'EVIDENCE TIMELINE':'ROADMAP STAGE'} · ${esc(row.evidence_status||row.status||'')}</div><h2>${esc(row.name||row.title||linkedItem?.title||'证据记录')}</h2><dl class="detail-fields">${row.reason?`<dt>为何记录</dt><dd>${esc(row.reason)}</dd>`:''}${row.problem?`<dt>解决的问题</dt><dd>${esc(row.problem)}</dd>`:''}${mechanisms?`<dt>代表机制</dt><dd>${esc(mechanisms)}</dd>`:''}${row.transition_reason?`<dt>变化原因</dt><dd>${esc(row.transition_reason)}</dd>`:''}<dt>开放问题</dt><dd>${esc((row.open_questions||branch?.open_questions||[]).join('；')||'尚未记录')}</dd></dl><h3 class="detail-section-title">已发布证据</h3><div class="evidence-links">${evidenceLinks(refs)}</div>${(row.evidence_against||[]).length?`<h3 class="detail-section-title">反对 / 冲突证据</h3><div class="evidence-links">${evidenceLinks(row.evidence_against)}</div>`:''}`);
}

async function renderIdeas(route){
  const token=++viewRenderToken;
  if(!state.knowledge){setLeft('<div class="context-title">Idea Bank</div>');$('#ideaMain').replaceChildren(missingKnowledge(state.knowledgeError?.message));setDetail('<div class="detail-placeholder"><span>IDEA BANK</span><h2>等待物化数据</h2><p>不会把项目 next_action 当作 Idea。</p></div>');return;}
  const all=state.knowledge.ideas;$('#ideaMeta').textContent=`${all.length} 个稳定 Idea 对象`;
  const topics=[...new Set(all.flatMap(row=>row.topic_ids||[]))].sort();
  const filters={topic:route.params.topic||'',type:route.params.type||'',status:route.params.status||''};
  setLeft(`<div class="context-title">筛选 Idea</div>${filterSelect('ideaTopicFilter','专题',topics,filters.topic)}${filterSelect('ideaTypeFilter','类型',Object.keys(IDEA_TYPE_LABELS),filters.type,IDEA_TYPE_LABELS)}${filterSelect('ideaStatusFilter','状态',Object.keys(STATUS_LABELS),filters.status,STATUS_LABELS)}<p class="context-copy">研究假设与技术方案是一等对象；验证动作只挂在 Idea 下。</p>`);
  ['ideaTopicFilter','ideaTypeFilter','ideaStatusFilter'].forEach(id=>$('#'+id).addEventListener('change',()=>go('ideas',{topic:$('#ideaTopicFilter').value,type:$('#ideaTypeFilter').value,status:$('#ideaStatusFilter').value})));
  const rows=all.filter(row=>(!filters.topic||(row.topic_ids||[]).includes(filters.topic))&&(!filters.type||row.idea_type===filters.type)&&(!filters.status||row.status===filters.status));
  $('#ideaMain').innerHTML=rows.length?rows.map(row=>`<button class="idea-list-card ${row.idea_id===route.params.idea?'selected':''}" data-idea="${esc(row.idea_id)}"><div><span class="status-pill status-${esc(row.status)}">${esc(STATUS_LABELS[row.status]||row.status)}</span><span class="type-label">${esc(IDEA_TYPE_LABELS[row.idea_type]||row.idea_type)}</span></div><h2>${esc(row.title)}</h2><p>${esc((row.topic_ids||[]).join(' · '))}</p><small>更新于 ${esc(row.last_updated_issue||'')}</small></button>`).join(''):emptyBlock('当前筛选条件下没有 Idea');
  $$('#ideaMain [data-idea]').forEach(button=>button.addEventListener('click',()=>go('ideas',{...filters,idea:button.dataset.idea})));
  const selected=rows.find(row=>row.idea_id===route.params.idea)||rows[0];if(!selected){setDetail('<div class="detail-placeholder"><span>IDEA</span><h2>没有匹配记录</h2></div>');return;}
  try{const idea=await loadKnowledgeObject(selected.path);if(token!==viewRenderToken)return;renderIdeaDetail(idea,selected);}catch(error){if(token===viewRenderToken)setDetail(`<div class="missing-data"><b>Idea 加载失败</b><p>${esc(error.message)}</p></div>`);}
}
function filterSelect(id,label,values,current,labels={}){return `<label class="context-filter">${esc(label)}<select id="${id}"><option value="">全部</option>${values.map(value=>`<option value="${esc(value)}" ${value===current?'selected':''}>${esc(labels[value]||value)}</option>`).join('')}</select></label>`;}
function listField(title,rows){return `<dt>${esc(title)}</dt><dd>${Array.isArray(rows)?esc(rows.join('；')||'尚未记录'):esc(rows||'尚未记录')}</dd>`;}
function validationPlan(plan={}){
  return `<section class="validation-plan"><div class="warning-label">验证建议 · 尚未执行</div><p>以下内容是建议怎样验证，不是仿真或实验结果。</p><dl class="detail-fields">${listField('方式',plan.mode)}${listField('最小模型',plan.minimal_model)}${listField('输入与扫描范围',plan.inputs)}${listField('对照基线',plan.baselines)}${listField('观察指标',plan.metrics)}${listField('支持判据',plan.support_criteria)}${listField('否定判据',plan.reject_criteria)}${listField('无法覆盖的边界',plan.limitations)}</dl></section>`;
}
function renderIdeaDetail(idea,indexRow){
  const id=idea.idea_id||indexRow.idea_id;
  setDetail(`<div class="detail-kicker">${esc(IDEA_TYPE_LABELS[idea.idea_type]||idea.idea_type)} · ${esc(STATUS_LABELS[idea.status]||idea.status)}</div><h2>${esc(idea.title||indexRow.title)}</h2><dl class="detail-fields">${listField('问题',idea.problem)}${listField('可证伪假设',idea.hypothesis)}${listField('核心机制',idea.mechanism)}${listField('预期效果',idea.expected_effect)}${listField('关键未知量',idea.unknowns)}</dl><h3 class="detail-section-title">支持证据</h3><div class="evidence-links">${evidenceLinks(idea.evidence_for)}</div><h3 class="detail-section-title">反对证据</h3><div class="evidence-links">${evidenceLinks(idea.evidence_against)}</div>${validationPlan(idea.validation_plan)}<h3 class="detail-section-title">判断记录</h3><div class="decision-log">${(idea.decision_log||[]).map(row=>`<div><b>${esc(row.date||row.issue_date||row.created_at||'')}</b><p>${esc(row.reason||row.summary||row.decision||JSON.stringify(row))}</p></div>`).join('')||'<span class="quiet">暂无判断记录</span>'}</div>${feedbackButtons('idea',id,['continue','值得继续'],['not_now','暂不值得'])}<p class="feedback-note">仅保存在当前浏览器，不会自动改变 Idea 状态。</p>`);
  bindFeedbackEvents($('#detailPane'));
}

function renderArchive(route){
  const selected=state.issues.find(row=>row.date===route.params.date)||state.latest;
  $('#archiveMeta').textContent=`${state.issues.length} 期已发布记录`;
  setLeft(`<div class="context-title">已发布期次</div><div class="context-list issue-list">${[...state.issues].reverse().map(issue=>`<button data-date="${issue.date}" class="${issue.date===selected?.date?'active':''}"><b>${issue.date}</b><small>${issue.papers.length} 条记录</small></button>`).join('')}</div><p class="context-copy">根链接始终指向最新版公开 Reader；原始发送版仅在 manifest 声明存在时显示。</p>`);
  $$('#leftContext [data-date]').forEach(button=>button.addEventListener('click',()=>go('archive',{date:button.dataset.date})));
  $('#archiveMain').innerHTML=[...state.issues].reverse().map(issue=>`<button class="issue-list-card ${issue===selected?'selected':''}" data-date="${issue.date}"><span>${issue.date}</span><h2>${esc(issue.headline)}</h2><p>${issue.papers.filter(item=>item.role==='core').length} 深度 · ${issue.papers.filter(item=>item.role==='supplement').length} 简要 · ${issue.radar.length} Radar</p></button>`).join('');
  $$('#archiveMain [data-date]').forEach(button=>button.addEventListener('click',()=>go('archive',{date:button.dataset.date})));
  if(selected)renderIssueDetail(selected);
}
function renderIssueDetail(issue){
  setDetail(`<div class="detail-kicker">PUBLISHED ISSUE · ${esc(issue.date)}</div><h2>${esc(issue.headline)}</h2><div class="detail-actions"><a href="${issue.public_href}" target="_blank">打开当前公开版 ↗</a>${issue.original_href?`<a class="secondary-link" href="${esc(issue.original_href)}" target="_blank">查看实际发送版 ↗</a>`:''}</div><div class="issue-items">${issue.papers.map(item=>`<button data-item="${esc(itemKey(item))}"><span class="role-tag role-${esc(item.role)}">${esc(roleName(item.role))}</span><b>${esc(item.title)}</b><small>${esc(item.topic_name||'未分类')}</small></button>`).join('')}</div>`);
  $$('#detailPane [data-item]').forEach(button=>button.addEventListener('click',()=>renderItemDetail(state.itemById.get(button.dataset.item))));
}

function renderAtlasContext(){setLeft(`<div class="context-title">证据图谱</div><p class="context-copy">图谱是辅助浏览工具。它只使用 Machine IDs、归档结构与显式关键词，不替代 Roadmap，也不根据 Reader 文案制造关联。</p>`);}

function renderWorkbenchView(route){
  if(route.name==='home')renderHome();
  else if(route.name==='roadmaps')renderRoadmaps(route);
  else if(route.name==='ideas')renderIdeas(route);
  else if(route.name==='archive')renderArchive(route);
  else if(route.name==='atlas')renderAtlasContext();
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bootWorkbench);else bootWorkbench();
