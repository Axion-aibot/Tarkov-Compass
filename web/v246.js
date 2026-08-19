// v24.6 — local account / quest progression planner.
// Uses the live quest catalog, prerequisite graph and raid-kit requirements.

var v246RecommendedRaid=null;
var v246OldLoadQuestCatalog=loadQuestCatalog;
var v246OldSaveQuestProgress=saveQuestProgress;
var v246OldRenderQuestCard=renderQuestCard;

function v246CompletedSet(){
  try{return new Set(JSON.parse(localStorage.getItem('eft-v246-completed-quests')||'[]'))}catch{return new Set()}
}
function v246SaveCompletedSet(set){localStorage.setItem('eft-v246-completed-quests',JSON.stringify([...set]))}
function v246IsCompleted(id){return v246CompletedSet().has(String(id))}
function v246PlayerLevel(){
  const el=$('progressionLevel');
  const raw=el?+el.value:+(localStorage.getItem('eft-v246-player-level')||1);
  return clamp(Math.round(Number.isFinite(raw)?raw:1),1,79);
}
function v246SetPlayerLevel(v){
  v=clamp(Math.round(+v||1),1,79);localStorage.setItem('eft-v246-player-level',String(v));
  if($('progressionLevel'))$('progressionLevel').value=String(v);v246RenderProgression();
}
function v246QuestById(id){return questCatalog.find(q=>String(q.id)===String(id))||null}
function v246Faction(){return String($('progressionFaction')?.value||localStorage.getItem('eft-v246-faction')||'').toUpperCase()}
function v246FactionMatches(q){const selected=v246Faction(),f=String(q?.faction||'').toUpperCase();return !selected||!f||f==='ANY'||f===selected}
function v246RelevantQuests(){return questCatalog.filter(v246FactionMatches)}
function v246QuestProgressCount(q){return q?questProgress(q.id).size:0}
function v246PrereqRows(q){return (q?.prerequisites||[]).filter(r=>r&&(r.id||r.name))}
function v246NeedsSpecialState(r){
  const s=(Array.isArray(r?.status)?r.status:[r?.status]).filter(Boolean).map(x=>String(x).toLowerCase());
  return s.length&&!s.some(x=>x.includes('complete')||x.includes('success'));
}
function v246Context(){
  const completed=v246CompletedSet(),level=v246PlayerLevel(),byId=new Map(),reverse=new Map();
  for(const q of questCatalog){byId.set(String(q.id),q);reverse.set(String(q.id),[])}
  for(const q of questCatalog){for(const r of v246PrereqRows(q)){if(!r.id)continue;const k=String(r.id);if(!reverse.has(k))reverse.set(k,[]);reverse.get(k).push(q)}}
  return{completed,level,byId,reverse};
}
function v246QuestState(q,ctx=v246Context(),completedOverride=null){
  const completed=completedOverride||ctx.completed,id=String(q?.id||'');
  if(completed.has(id))return{key:'completed',label:'Voltooid',missing:[],levelGap:0,reason:'Quest gemarkeerd als voltooid'};
  const missing=[],special=[];
  for(const r of v246PrereqRows(q)){
    if(v246NeedsSpecialState(r))special.push(r);
    if(!r.id||!completed.has(String(r.id)))missing.push(r);
  }
  const levelGap=Math.max(0,(+q.minPlayerLevel||0)-ctx.level);
  if(!missing.length&&!levelGap)return{key:'ready',label:'Nu beschikbaar',missing,special,levelGap,reason:'Level en prerequisites zijn klaar'};
  if((missing.length<=1&&levelGap<=3)||(missing.length===0&&levelGap<=5)){
    const bits=[];if(missing.length)bits.push(`${missing.length} prerequisite`);if(levelGap)bits.push(`nog ${levelGap} level${levelGap===1?'':'s'}`);
    return{key:'near',label:'Bijna unlocked',missing,special,levelGap,reason:bits.join(' · ')};
  }
  const bits=[];if(missing.length)bits.push(`${missing.length} prerequisites`);if(levelGap)bits.push(`level ${q.minPlayerLevel||0} nodig`);
  return{key:'blocked',label:'Geblokkeerd',missing,special,levelGap,reason:bits.join(' · ')||'Voorwaarden nog niet voldaan'};
}
function v246FutureChain(q,ctx=v246Context(),maxDepth=4){
  const start=String(q?.id||q||'');if(!start)return[];const seen=new Set([start]),out=[],queue=[{id:start,depth:0}];
  while(queue.length){const cur=queue.shift();if(cur.depth>=maxDepth)continue;for(const dep of ctx.reverse.get(cur.id)||[]){const id=String(dep.id);if(seen.has(id))continue;seen.add(id);out.push({q:dep,depth:cur.depth+1});queue.push({id,depth:cur.depth+1})}}
  return out;
}
function v246UnlockImpact(q,ctx=v246Context(),completedOverride=null){
  const completed=new Set(completedOverride||ctx.completed),id=String(q?.id||'');if(!id)return[];
  const before=new Map();for(const dep of ctx.reverse.get(id)||[])before.set(String(dep.id),v246QuestState(dep,ctx,completed).key);
  completed.add(id);const out=[];
  for(const dep of ctx.reverse.get(id)||[]){if(completed.has(String(dep.id)))continue;const after=v246QuestState(dep,ctx,completed);if(after.key==='ready'&&before.get(String(dep.id))!=='ready')out.push(dep)}
  return out;
}
function v246SimulatedUnlocks(ids,ctx=v246Context()){
  const completed=new Set(ctx.completed);for(const id of ids)completed.add(String(id));
  const beforeReady=new Set(v246RelevantQuests().filter(q=>v246QuestState(q,ctx,ctx.completed).key==='ready').map(q=>String(q.id)));
  return v246RelevantQuests().filter(q=>!completed.has(String(q.id))&&v246QuestState(q,ctx,completed).key==='ready'&&!beforeReady.has(String(q.id)));
}
function v246QuestScore(q,ctx){
  const impact=v246UnlockImpact(q,ctx).filter(v246FactionMatches).length;
  const chain=v246FutureChain(q,ctx).filter(x=>v246FactionMatches(x.q)).length;return 10+(q.hasLocations?5:0)+Math.min(5,+q.objectiveCount||0)+impact*5+Math.min(10,chain)*1.25+(q.kappa?1:0)+(q.lightkeeper?1:0);
}
function v246SupportedQuestMaps(q){return [...new Set((q.maps||[]).filter(k=>k&&maps[k]&&maps[k].group!=='detail'))]}
function v246Recommendation(forceMap=null){
  const ctx=v246Context(),groups=new Map();
  for(const q of v246RelevantQuests()){if(v246QuestState(q,ctx).key!=='ready')continue;for(const mk of v246SupportedQuestMaps(q)){if(forceMap&&mk!==forceMap)continue;if(!groups.has(mk))groups.set(mk,[]);groups.get(mk).push(q)}}
  let best=null;
  for(const [mk,rows] of groups){
    const ranked=rows.slice().sort((a,b)=>v246QuestScore(b,ctx)-v246QuestScore(a,ctx)||(a.name||'').localeCompare(b.name||''));
    const selected=ranked.slice(0,6),score=selected.reduce((n,q)=>n+v246QuestScore(q,ctx),0)+(mk===mapKey()?2:0);
    const rec={map:mk,quests:selected,allCount:rows.length,score};if(!best||rec.score>best.score)best=rec;
  }
  if(!best)return null;
  best.unlocks=v246SimulatedUnlocks(best.quests.map(q=>q.id),ctx);
  best.kit=v246AggregateKit(best.quests);
  best.pinQuests=best.quests.filter(q=>q.hasLocations).length;
  best.unlockImpact=best.unlocks.length;
  return best;
}
function v246AggregateKit(quests){
  const rows=new Map();
  for(const q of quests){for(const r of q.requirements||[]){
    const key=`${r.kind||'item'}|${r.id||r.name||''}|${r.note||''}|${!!r.foundInRaid}`;
    if(!rows.has(key))rows.set(key,{...r,count:0});const hit=rows.get(key),c=Number(r.count||1)||1;
    if(String(r.kind||'').toLowerCase().includes('key'))hit.count=Math.max(+hit.count||0,c);else hit.count=(+hit.count||0)+c;
  }}
  return [...rows.values()].sort((a,b)=>String(a.kind||'').localeCompare(String(b.kind||''))||String(a.name||'').localeCompare(String(b.name||'')));
}
function v246KitLabel(r){
  try{return requirementLabel(r)}catch{return `${r.count&&+r.count!==1?r.count+'x ':''}${r.name||'Item'}`}
}
function v246SetQuestCompleted(qid,done=true){
  qid=String(qid||'');if(!qid)return;const set=v246CompletedSet();done?set.add(qid):set.delete(qid);v246SaveCompletedSet(set);
  if(done&&activeQuest&&String(activeQuest.id)===qid){const prog=questProgress(qid);for(const o of activeQuest.objectives||[])prog.add(String(o.id));v246OldSaveQuestProgress(qid,prog)}
  v246RenderProgression();renderQuestCard();renderRaidPlan();buildActiveQuestPois();draw();
}
function v246StatusCounts(ctx){const c={ready:0,near:0,blocked:0,completed:0};for(const q of v246RelevantQuests())c[v246QuestState(q,ctx).key]++;return c}
function v246RenderStats(ctx){
  const b=$('progressionStats');if(!b)return;const c=v246StatusCounts(ctx);
  b.innerHTML=`<div class="progressStat completed"><b>${c.completed}</b><small>voltooid</small></div><div class="progressStat ready"><b>${c.ready}</b><small>beschikbaar</small></div><div class="progressStat near"><b>${c.near}</b><small>bijna</small></div><div class="progressStat blocked"><b>${c.blocked}</b><small>geblokkeerd</small></div>`;
  if($('progressionStateBadge'))$('progressionStateBadge').textContent=`LVL ${ctx.level}`;
}
function v246RenderRecommendation(forceMap=null){
  const box=$('bestRaidRecommendation'),btn=$('progressionLoadRaidBtn');if(!box||!btn)return;
  const rec=v246Recommendation(forceMap);v246RecommendedRaid=rec;
  if(!questCatalog.length){box.innerHTML='<div class="statusLine">Questdata nog niet beschikbaar. Gebruik “Data update” in Quest Navigator.</div>';btn.disabled=true;return}
  if(!rec){box.innerHTML=`<div class="statusLine">Geen direct beschikbare questraid gevonden${forceMap?' op '+escapeHtml(questMapName(forceMap)):''}. Controleer je PMC-level en gemarkeerde questprogressie.</div>`;btn.disabled=true;return}
  const ctx=v246Context(),kit=rec.kit.slice(0,8),more=Math.max(0,rec.kit.length-kit.length),unlocks=rec.unlocks.slice(0,4),future=[...new Set(rec.quests.flatMap(q=>v246FutureChain(q,ctx).filter(x=>v246FactionMatches(x.q)).map(x=>x.q.name)).filter(Boolean))];
  box.innerHTML=`<div class="bestRaidHero"><div><b>Beste volgende raid: ${escapeHtml(questMapName(rec.map))}</b><span>${rec.quests.length} geselecteerde quests · ${rec.pinQuests} met kaartspots</span></div><span>score ${Math.round(rec.score)}</span></div><div class="bestRaidReason">Combineert quests die nu unlocked zijn met hun directe progression-impact. ${rec.unlockImpact?`Als deze set klaar is kunnen <b>${rec.unlockImpact}</b> nieuwe quests direct beschikbaar worden.`:'Deze set heeft geen directe nieuwe unlock volgens de huidige dependency-data.'} ${future.length?`De vervolglijnen achter deze quests bevatten samen <b>${future.length}</b> toekomstige quests.`:''}</div>${rec.quests.map(q=>{const impact=v246UnlockImpact(q,ctx).filter(v246FactionMatches).length;return`<div class="bestRaidQuest"><span><b>${escapeHtml(q.name)}</b><small>${escapeHtml(q.trader||'Unknown')} · lvl ${q.minPlayerLevel||0}${q.hasLocations?' · kaartpins':''}</small></span><span class="unlockImpact">${impact?`+${impact} unlock${impact===1?'':'s'}`:'open'}</span></div>`}).join('')}${kit.length?`<div class="bestRaidKit"><b>Voor deze raid meenemen</b><br>${kit.map(v246KitLabel).map(escapeHtml).join(' · ')}${more?` · +${more} meer`:''}</div>`:''}${unlocks.length?`<div class="bestRaidUnlocks"><b>Kan hierna unlocken:</b> ${unlocks.map(q=>escapeHtml(q.name)).join(' · ')}${rec.unlocks.length>unlocks.length?` · +${rec.unlocks.length-unlocks.length}`:''}</div>`:''}`;
  btn.disabled=false;btn.textContent=`Laad ${questMapName(rec.map)} raid plan`;
}
function v246RenderQuestList(ctx){
  const box=$('progressionQuestList');if(!box)return;const filter=$('progressionFilter')?.value||'ready',search=($('progressionSearch')?.value||'').trim().toLowerCase();
  let rows=v246RelevantQuests().map(q=>({q,state:v246QuestState(q,ctx),impact:v246UnlockImpact(q,ctx).filter(v246FactionMatches).length}));
  if(filter!=='all')rows=rows.filter(x=>x.state.key===filter);
  if(search)rows=rows.filter(x=>`${x.q.name||''} ${x.q.trader||''} ${(x.q.maps||[]).map(questMapName).join(' ')}`.toLowerCase().includes(search));
  rows.sort((a,b)=>b.impact-a.impact-(0)||(a.q.minPlayerLevel||0)-(b.q.minPlayerLevel||0)||(a.q.name||'').localeCompare(b.q.name||''));
  box.innerHTML='';
  for(const {q,state,impact} of rows.slice(0,80)){
    const missing=state.missing.slice(0,2).map(r=>r.name||v246QuestById(r.id)?.name||r.id).filter(Boolean),progress=v246QuestProgressCount(q),future=v246FutureChain(q,ctx).filter(x=>v246FactionMatches(x.q)).length,d=document.createElement('div');d.className=`progressionQuestRow ${state.key}`;
    d.innerHTML=`<div><b>${escapeHtml(q.name)}</b><small>${escapeHtml(q.trader||'Unknown')} · lvl ${q.minPlayerLevel||0}${(q.maps||[]).length?' · '+escapeHtml((q.maps||[]).map(questMapName).join(', ')):''}${progress?` · ${progress}/${q.objectiveCount||'?'} objectives`:''}</small><small>${escapeHtml(state.reason)}${missing.length?` · mist: <span class="prereqMissing">${missing.map(escapeHtml).join(', ')}</span>`:''}${impact?` · <span class="unlockImpact">opent ${impact}</span>`:''}${future?` · keten ${future}`:''}</small></div><div class="progressionQuestActions"><span class="progressStatus ${state.key}">${escapeHtml(state.label)}</span><button type="button" class="progressCompleteBtn">${state.key==='completed'?'Terugzetten':'✓ Voltooid'}</button></div>`;
    d.onclick=async()=>{$('questSelect').value=q.id;await selectQuest(q.id)};
    d.querySelector('.progressCompleteBtn').onclick=e=>{e.stopPropagation();v246SetQuestCompleted(q.id,state.key!=='completed')};box.append(d);
  }
  if(!rows.length)box.innerHTML='<div class="statusLine">Geen quests in deze selectie.</div>';
}
function v246RenderProgression(forceMap=null){
  if(!$('progressionStats'))return;const ctx=v246Context();v246RenderStats(ctx);v246RenderRecommendation(forceMap);v246RenderQuestList(ctx);v246InjectActiveQuestCompletion();
  const ab=$('progressionMarkActiveBtn');if(ab){ab.disabled=!activeQuest;ab.textContent=!activeQuest?'Geen actieve quest':(v246IsCompleted(activeQuest.id)?'Actieve quest terugzetten':'Actieve quest voltooid')}
}
function v246InjectActiveQuestCompletion(){
  const box=$('questCard');if(!box||!activeQuest)return;let old=box.querySelector('.activeQuestCompletion');if(old)old.remove();
  const done=v246IsCompleted(activeQuest.id),prog=questProgress(activeQuest.id),total=(activeQuest.objectives||[]).length,allObjectives=total>0&&prog.size>=total,wrap=document.createElement('div');wrap.className='activeQuestCompletion';
  wrap.innerHTML=`<span>${done?'Deze quest telt als voltooid in je accountprogressie.':allObjectives?'Alle objectives zijn afgevinkt — zet hem nu als account-complete.':'Gebruik account-complete wanneer Tarkov de quest daadwerkelijk als voltooid toont.'}</span><button type="button">${done?'↶ Niet voltooid':'✓ Quest voltooid'}</button>`;
  wrap.querySelector('button').onclick=()=>v246SetQuestCompleted(activeQuest.id,!done);const head=box.querySelector('.questHead');if(head)head.insertAdjacentElement('afterend',wrap);else box.prepend(wrap);
}
async function v246LoadRecommendedRaid(){
  const rec=v246RecommendedRaid;if(!rec)return;const ids=rec.quests.map(q=>q.id).slice(0,8);saveRaidPlanIds(ids);await loadRaidPlanDetails();
  if(rec.map&&maps[rec.map]&&mapKey()!==rec.map){questPlanLocked=true;visualMapKey=rec.map;$('map').value=rec.map;loadMap(rec.map)}
  raidPlanOrder=[];renderRaidPlan();renderRaidPlanRoute();setTimeout(()=>optimizeRaidPlan(),250);
}
function v246ResetProgression(){
  if(!confirm('Accountprogressie resetten? Dit wist ook lokaal afgevinkte quest-objectives en raid-kit vinkjes.'))return;
  localStorage.removeItem('eft-v246-completed-quests');
  for(let i=localStorage.length-1;i>=0;i--){const k=localStorage.key(i)||'';if(k.startsWith('eft-mvp-quest-progress-')||k.startsWith('eft-mvp-quest-kit-'))localStorage.removeItem(k)}
  v246RenderProgression();renderQuestCard();buildActiveQuestPois();renderRaidPlan();draw();
}

loadQuestCatalog=async function(force=false){const r=await v246OldLoadQuestCatalog(force);v246RenderProgression();return r};
saveQuestProgress=function(id,set){v246OldSaveQuestProgress(id,set);v246RenderProgression()};
renderQuestCard=function(){v246OldRenderQuestCard();v246InjectActiveQuestCompletion()};

function v246WireProgression(){
  const lvl=clamp(+(localStorage.getItem('eft-v246-player-level')||1),1,79);if($('progressionLevel')){$('progressionLevel').value=String(lvl);$('progressionLevel').onchange=e=>v246SetPlayerLevel(e.target.value);$('progressionLevel').oninput=e=>{localStorage.setItem('eft-v246-player-level',String(clamp(+e.target.value||1,1,79)));v246RenderProgression()}}
  if($('progressionFaction')){const f=localStorage.getItem('eft-v246-faction')||'';$('progressionFaction').value=f;$('progressionFaction').onchange=e=>{localStorage.setItem('eft-v246-faction',e.target.value);v246RenderProgression()}}
  if($('progressionFilter'))$('progressionFilter').onchange=()=>v246RenderProgression();if($('progressionSearch'))$('progressionSearch').oninput=()=>v246RenderProgression();
  if($('progressionLoadRaidBtn'))$('progressionLoadRaidBtn').onclick=v246LoadRecommendedRaid;
  if($('progressionCurrentMapBtn'))$('progressionCurrentMapBtn').onclick=()=>v246RenderProgression(mapKey());
  if($('progressionMarkActiveBtn'))$('progressionMarkActiveBtn').onclick=()=>{if(activeQuest)v246SetQuestCompleted(activeQuest.id,!v246IsCompleted(activeQuest.id))};
  if($('progressionResetBtn'))$('progressionResetBtn').onclick=v246ResetProgression;
  setTimeout(()=>v246RenderProgression(),700);
}
v246WireProgression();
