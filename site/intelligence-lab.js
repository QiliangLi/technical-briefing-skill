(() => {
  const EFFECT_LABELS = {supports:'支持', challenges:'挑战', narrows:'收敛', opens:'打开新方向'};

  function issueHref(date){ return `${ROOT}/issues/${date}/email.html`; }
  function itemKey(item){ return String(item.item_id || item.brief_item_id || item.detail?.brief_item_id || item.id || ''); }

  function allStructuredItems(){
    return state.items.filter(item => item.role !== 'radar' && item.topic_name && item.issue_date);
  }

  function topicCounts(){
    const counts = new Map();
    allStructuredItems().forEach(item => counts.set(item.topic_name, (counts.get(item.topic_name) || 0) + 1));
    return [...counts.entries()].sort((a,b)=>b[1]-a[1] || a[0].localeCompare(b[0], 'zh-CN'));
  }

  function roadmapFor(topic){
    const items = allStructuredItems()
      .filter(item => item.topic_name === topic)
      .sort((a,b)=>a.issue_date.localeCompare(b.issue_date) || String(a.direction_name||'').localeCompare(String(b.direction_name||''), 'zh-CN'));
    const firstSeen = new Map();
    items.forEach(item => {
      const direction = item.direction_name || item.direction_id || '未标注方向';
      if (!firstSeen.has(direction)) firstSeen.set(direction, item.issue_date);
    });
    const byDate = new Map();
    items.forEach(item => {
      if (!byDate.has(item.issue_date)) byDate.set(item.issue_date, []);
      byDate.get(item.issue_date).push(item);
    });
    return [...byDate.entries()].map(([date, rows]) => {
      const directions = new Map();
      rows.forEach(item => {
        const name = item.direction_name || item.direction_id || '未标注方向';
        if (!directions.has(name)) directions.set(name, []);
        directions.get(name).push(item);
      });
      return {date, directions:[...directions.entries()].map(([name, directionItems])=>({name, items:directionItems, first:firstSeen.get(name)===date}))};
    });
  }

  function renderRoadmap(selectedTopic){
    const topics = topicCounts();
    if (!topics.length) return;
    const topic = selectedTopic && topics.some(([name])=>name===selectedTopic) ? selectedTopic : topics[0][0];
    const chips = document.querySelector('#roadmapTopics');
    chips.innerHTML = topics.map(([name,count]) => `<button class="lab-chip${name===topic?' active':''}" data-roadmap-topic="${esc(name)}">${esc(name)} <b>${count}</b></button>`).join('');
    chips.querySelectorAll('button').forEach(button => button.addEventListener('click', () => renderRoadmap(button.dataset.roadmapTopic)));

    const snapshots = roadmapFor(topic);
    const directionSet = new Set(snapshots.flatMap(snapshot => snapshot.directions.map(direction => direction.name)));
    document.querySelector('#roadmapSummary').textContent = `${snapshots.length} 个归档时间点 · ${directionSet.size} 个显式技术方向`;
    document.querySelector('#roadmapTimeline').innerHTML = snapshots.map((snapshot,index) => `
      <article class="roadmap-stop">
        <div class="roadmap-rail"><span class="roadmap-dot"></span>${index < snapshots.length-1 ? '<span class="roadmap-line"></span>' : ''}</div>
        <div class="roadmap-card">
          <div class="roadmap-date"><span>${esc(snapshot.date)}</span><a href="${issueHref(snapshot.date)}" target="_blank" rel="noreferrer">日报溯源 ↗</a></div>
          <div class="roadmap-directions">
            ${snapshot.directions.map(direction => `
              <div class="roadmap-direction">
                <div class="direction-head"><strong>${esc(direction.name)}</strong>${direction.first?'<span class="first-seen">首次进入归档</span>':''}</div>
                <div class="direction-items">
                  ${direction.items.map(item => `<a href="${esc(item.url || issueHref(snapshot.date))}" target="_blank" rel="noreferrer"><span class="role-mini ${esc(item.role)}">${item.role==='core'?'深度':'简要'}</span>${esc(item.title)}</a>`).join('')}
                </div>
              </div>`).join('')}
          </div>
        </div>
      </article>`).join('');
  }

  function collectIdeaThreads(){
    const itemMap = new Map();
    allStructuredItems().forEach(item => {
      const keys = [itemKey(item), item.detail?.brief_item_id, item.item_id].filter(Boolean).map(String);
      keys.forEach(key => itemMap.set(key, item));
    });
    const threads = new Map();
    state.issues.forEach(issue => {
      const insights = issue.issueDoc?.synthesis?.project_insights || [];
      insights.forEach((insight,index) => {
        if (!insight?.next_action || !insight?.insight) return;
        const key = `${insight.topic_id || insight.topic_name || 'topic'}|||${insight.project_question || insight.next_action}`;
        if (!threads.has(key)) threads.set(key, {key, topic_id:insight.topic_id, topic_name:insight.topic_name || '未分类', project_question:insight.project_question || '', entries:[]});
        const evidence = (insight.evidence_item_ids || []).map(id => itemMap.get(String(id))).filter(Boolean);
        threads.get(key).entries.push({
          date: issue.date,
          effect: insight.effect,
          confidence: insight.confidence,
          insight: insight.insight,
          next_action: insight.next_action,
          evidence,
          evidence_ids: insight.evidence_item_ids || [],
          issue_href: issueHref(issue.date),
          order:index
        });
      });
    });
    return [...threads.values()].map(thread => {
      thread.entries.sort((a,b)=>a.date.localeCompare(b.date));
      const latest = thread.entries.at(-1);
      const evidence = [];
      const seen = new Set();
      thread.entries.flatMap(entry => entry.evidence).forEach(item => {
        const key = itemKey(item);
        if (!seen.has(key)) { seen.add(key); evidence.push(item); }
      });
      return {...thread, latest, evidence, dates:[...new Set(thread.entries.map(entry=>entry.date))]};
    }).sort((a,b)=>b.latest.date.localeCompare(a.latest.date) || b.entries.length-a.entries.length);
  }

  function renderIdeaBank(){
    const threads = collectIdeaThreads();
    document.querySelector('#ideaSummary').textContent = threads.length ? `${threads.length} 个可溯源 Idea Seed` : '暂无结构化 Idea Seed';
    const box = document.querySelector('#ideaBank');
    if (!threads.length) {
      box.innerHTML = '<div class="lab-empty">当前归档还没有结构化 project_insights。后续日报产生明确 insight + next_action 后，这里会自动形成 Idea Seed。</div>';
      return;
    }
    box.innerHTML = threads.slice(0,18).map(thread => {
      const latest = thread.latest;
      const effectHistory = thread.entries.map(entry => `<span>${esc(entry.date.slice(5))} · ${EFFECT_LABELS[entry.effect] || esc(entry.effect || '观察')}</span>`).join('');
      const evidenceLinks = thread.evidence.slice(0,5).map(item => `<a href="${esc(item.url || issueHref(item.issue_date))}" target="_blank" rel="noreferrer" title="${esc(item.title)}">${esc(truncate(item.title,22))} ↗</a>`).join('');
      return `<article class="idea-card">
        <div class="idea-top"><span class="idea-status">IDEA SEED · 待验证</span><span>${esc(thread.topic_name)}</span></div>
        <h3>${esc(latest.next_action)}</h3>
        <div class="idea-question">来自问题：${esc(thread.project_question || '归档中的技术判断')}</div>
        <p>${esc(latest.insight)}</p>
        <div class="idea-history">${effectHistory}</div>
        <div class="idea-evidence"><strong>证据链</strong>${evidenceLinks || '<span>证据仅保存在日报结构中</span>'}</div>
        <div class="idea-footer"><span>积累 ${thread.dates.length} 期 · ${thread.evidence.length || latest.evidence_ids.length} 条证据</span><a href="${latest.issue_href}" target="_blank" rel="noreferrer">回到 ${esc(latest.date)} 日报 ↗</a></div>
      </article>`;
    }).join('');
  }

  function renderLab(){
    if (!state?.issues?.length) return false;
    renderRoadmap();
    renderIdeaBank();
    return true;
  }

  function waitForArchive(attempt=0){
    if (renderLab()) return;
    if (attempt < 80) window.setTimeout(()=>waitForArchive(attempt+1), 100);
  }

  waitForArchive();
})();
