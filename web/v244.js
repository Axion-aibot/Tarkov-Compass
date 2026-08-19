// v24.4 — Media previews, confidence/floor guidance, local pin feedback,
// alias search and smarter raid planning. Loaded after app.js on purpose.

var v244PinMedia={version:'24.4',exact:{},questKeywords:[],aliases:{}};
var v244PendingReport=null;
var v244CorrectionMode=null;
var v244RaidExtract=null;
var v244OldPoiMapNormalized=poiMapNormalized;
var v244OldDraw=draw;
var v244OldNavigateQuestLocation=navigateQuestLocation;
var v244OldRenderDomPins=renderDomPins;

function v244Style(){return $('mapStyle')?.value||'reemr'}
function v244CorrectionStore(){try{return JSON.parse(localStorage.getItem('eft-v244-pin-corrections')||'{}')}catch{return{}}}
function v244SaveCorrectionStore(v){localStorage.setItem('eft-v244-pin-corrections',JSON.stringify(v||{}))}
function v244StableKey(p,k=mapKey()){
  if(!p)return'';
  const mk=p.map||k;
  if(p.questActive||p.category==='quest'||p.questId)return `${mk}|quest|${p.questId||''}|${p.objectiveId||p.id||''}|${p.locationIndex??0}`;
  return `${mk}|${p.category||'poi'}|${canonicalPoiName(p.name||p.id||'poi')}`;
}
function v244CorrectionFor(p,k=mapKey()){
  const c=v244CorrectionStore()[v244StableKey(p,k)];
  if(!c||c.map!==(p?.map||k)||c.style!==v244Style())return null;
  return Number.isFinite(+c.nx)&&Number.isFinite(+c.ny)?c:null;
}
function v244CorrectedPoi(p,k=mapKey()){
  if(!p)return p;
  const c=v244CorrectionFor(p,k);if(!c)return p;
  const out={...p,nx:+c.nx,ny:+c.ny,_localCorrection:true};
  if(Number.isFinite(+c.x)&&Number.isFinite(+c.z)){out.x=+c.x;out.z=+c.z}
  return out;
}
poiMapNormalized=function(p,k=mapKey()){
  const c=v244CorrectionFor(p,k);if(c)return{x:+c.nx,y:+c.ny};
  return v244OldPoiMapNormalized(p,k);
};

async function v244LoadMedia(){
  try{const r=await fetch('/data/pin_media.json',{cache:'no-store'});if(r.ok)v244PinMedia=await r.json()}catch(e){console.warn('v24.4 media manifest niet geladen',e)}
  const s=$('pinReportStatus');if(s)s.textContent=`Media: ${Object.keys(v244PinMedia.exact||{}).length} extract-herkenningsbeelden · ${(v244PinMedia.questKeywords||[]).length} quest-referenties · kaartpreview voor elke pin.`;
  renderDomPins();
}
v244LoadMedia();

function v244ExactMediaKey(p,k=p?.map||mapKey()){return `${k}|${p?.category||'poi'}|${canonicalPoiName(p?.name||'')}`}
function v244Aliases(p,k=p?.map||mapKey()){
  const key=v244ExactMediaKey(p,k),e=v244PinMedia.exact?.[key];
  return [...(e?.aliases||[]),...(v244PinMedia.aliases?.[key]||[]),...(Array.isArray(p?.aliases)?p.aliases:[])];
}
function v244MediaEntryImages(p,o=null,q=null){
  const k=p?.map||mapKey(),out=[],seen=new Set(),exact=v244PinMedia.exact?.[v244ExactMediaKey(p,k)];
  for(const im of exact?.images||[]){if(im?.src&&!seen.has(im.src)){seen.add(im.src);out.push({...im,kind:'image'})}}
  if(p?.questActive||p?.category==='quest'||o||q){
    const hay=`${p?.name||''} ${p?.objectiveDescription||''} ${o?.description||''} ${q?.name||p?.questName||''}`.toLowerCase();
    for(const e of v244PinMedia.questKeywords||[]){
      if(e.map!==k)continue;
      if(!(e.keywords||[]).some(x=>hay.includes(String(x).toLowerCase())))continue;
      if(e.image&&!seen.has(e.image)){seen.add(e.image);out.push({kind:'image',src:e.image,label:e.label||'Herkenningsbeeld',source:e.source||'Lokale referentie'})}
      if(out.length>=3)break;
    }
  }
  return out;
}
function v244MapPreviewItem(p){
  const k=p?.map||mapKey(),n=poiMapNormalized(p,k),m=maps[k],src=m?.styles?.reemr||m?.styles?.[v244Style()]||m?.image;
  if(!n||!src||!Number.isFinite(n.x)||!Number.isFinite(n.y))return null;
  return{kind:'map',src,label:'Exacte kaartspot',source:'Lokale RE3MR kaart',nx:clamp(n.x,0,1),ny:clamp(n.y,0,1),map:k};
}
function v244MediaItems(p,o=null,q=null){const a=v244MediaEntryImages(p,o,q),mp=v244MapPreviewItem(p);if(mp)a.push(mp);return a}
function v244MapCropHtml(item,large=false){
  const z=large?290:420,x=(item.nx*100).toFixed(2),y=(item.ny*100).toFixed(2);
  return `<div class="mapSpotPreview ${large?'large':''}" style="background-image:url('${escapeHtml(item.src)}');background-size:${z}% auto;background-position:${x}% ${y}%"><span class="mapSpotCross"><i></i></span><span class="mapSpotLabel">${escapeHtml(questMapName(item.map))}</span></div>`;
}
function v244MediaStageHtml(item,p,large=false){
  if(!item)return'<div class="mediaEmpty">Geen preview beschikbaar.</div>';
  if(item.kind==='map')return v244MapCropHtml(item,large);
  return `<img class="pinMediaImg ${large?'large':''}" src="${escapeHtml(item.src)}" alt="${escapeHtml((item.label||'Locatie')+' · '+(p?.name||p?.objectiveDescription||''))}">`;
}
function v244PinMediaShell(p,o=null,q=null){
  const items=v244MediaItems(p,o,q);if(!items.length)return'';
  return `<div class="pinMedia244"><div class="pinMediaStage">${v244MediaStageHtml(items[0],p)}</div><div class="pinMediaBar"><button class="pinMediaPrev" type="button" aria-label="Vorige afbeelding">‹</button><span class="pinMediaCaption"><b>${escapeHtml(items[0].label||'Preview')}</b><small>${escapeHtml(items[0].source||'')}</small></span><span class="pinMediaCount">1/${items.length}</span><button class="pinMediaNext" type="button" aria-label="Volgende afbeelding">›</button></div></div>`;
}
function v244OpenLightbox(p,item){
  const modal=$('mediaLightbox'),body=$('mediaLightboxBody');if(!modal||!body)return;
  $('mediaLightboxTitle').textContent=p?.name||p?.objectiveDescription||'Locatievoorbeeld';
  body.innerHTML=v244MediaStageHtml(item,p,true);
  $('mediaLightboxCaption').textContent=[item?.label,item?.source].filter(Boolean).join(' · ');
  modal.classList.remove('hidden');
}
function v244WireMedia(root,p,o=null,q=null){
  const box=root?.querySelector?.('.pinMedia244');if(!box)return;
  const items=v244MediaItems(p,o,q);let i=0,stage=box.querySelector('.pinMediaStage'),cap=box.querySelector('.pinMediaCaption'),count=box.querySelector('.pinMediaCount');
  const paint=()=>{const it=items[i];stage.innerHTML=v244MediaStageHtml(it,p);cap.innerHTML=`<b>${escapeHtml(it.label||'Preview')}</b><small>${escapeHtml(it.source||'')}</small>`;count.textContent=`${i+1}/${items.length}`;box.querySelector('.pinMediaPrev').disabled=items.length<2;box.querySelector('.pinMediaNext').disabled=items.length<2;stage.onclick=()=>v244OpenLightbox(p,it)};
  box.querySelector('.pinMediaPrev').onclick=e=>{e.stopPropagation();i=(i-1+items.length)%items.length;paint()};
  box.querySelector('.pinMediaNext').onclick=e=>{e.stopPropagation();i=(i+1)%items.length;paint()};paint();
}

function v244Confidence(p){
  const c=v244CorrectionFor(p,p?.map||mapKey());if(c)return{score:98,label:'Lokale correctie',note:'Door jou exact op deze kaart geplaatst'};
  if(displayAnchorFor(p,p?.map||mapKey()))return{score:100,label:'Visuele kaart-anchor',note:'Pinpunt rechtstreeks op de RE3MR kaart verankerd'};
  if(Array.isArray(p?.outline)&&p.outline.length>=3)return{score:93,label:'Questzone',note:'Gestructureerde zone + middenpunt'};
  if(p?.worldApproximate)return{score:58,label:'Benaderde wereldpositie',note:'Kaartpunt is bruikbaar; wereldafstand kan afwijken'};
  if(Number.isFinite(+p?.x)&&Number.isFinite(+p?.z))return{score:86,label:'Wereldcoördinaat',note:'Gestructureerde Tarkov XYZ/map-coördinaat'};
  if(Number.isFinite(+p?.nx)&&Number.isFinite(+p?.ny))return{score:78,label:'Kaartcoördinaat',note:'Exact op kaartbeeld, zonder betrouwbare wereldafstand'};
  return{score:40,label:'Te verifiëren',note:'Geen volledige positionele bron beschikbaar'};
}
function v244ConfidenceHtml(p){const c=v244Confidence(p);return `<div class="confidenceBlock"><div><b>${escapeHtml(c.label)}</b><span>${c.score}%</span></div><div class="confidenceTrack"><i style="width:${c.score}%"></i></div><small>${escapeHtml(c.note)}</small></div>`}
function v244FloorGuidance(p,o=null){
  const bits=[],lv=p?.level??p?.floor;
  if(lv!==null&&lv!==undefined&&String(lv)!=='')bits.push(`Laag: ${String(lv).replaceAll('_',' ')}`);
  const pos=activePosition();if(pos&&Number.isFinite(+pos.y)&&Number.isFinite(+p?.y)){const dy=+p.y-(+pos.y);if(Math.abs(dy)>=1.8)bits.push(`Doel ligt op basis van Y ongeveer ${Math.round(Math.abs(dy))} m ${dy>0?'hoger':'lager'} dan jij`)}
  const text=String(o?.description||p?.objectiveDescription||p?.name||'');const indoor=/room|floor|verdieping|basement|kelder|office|hotel|apartment|building|warehouse|clinic|resort|dorm/i.test(text);
  if(indoor&&!bits.length)bits.push('Indoor objective: controleer herkenningsbeeld en kaartspot; verdieping is niet als apart veld bekend');
  if(!bits.length)bits.push('Geen aparte verdiepingseis in de gestructureerde locatie-data');
  return bits;
}
function v244FloorHtml(p,o=null){return `<div class="floorGuide"><b>Verdieping / indoor</b>${v244FloorGuidance(p,o).map(x=>`<span>${escapeHtml(x)}</span>`).join('')}</div>`}
function v244RewardSummary(q){
  const out=[];if(q?.experience)out.push(`${q.experience} XP`);const fr=q?.finishRewards||{};
  const items=Array.isArray(fr.items)?fr.items:[];for(const r of items.slice(0,5)){const name=r?.item?.name||r?.item?.shortName||r?.name||r?.id;if(name)out.push(`${r.count&&+r.count>1?r.count+'x ':''}${name}`)}
  const stand=Array.isArray(fr.traderStanding)?fr.traderStanding:[];for(const r of stand.slice(0,2)){const n=r?.trader?.name||r?.name||'trader';const v=r?.standing??r?.amount;if(v!==undefined)out.push(`${n} standing ${Number(v)>=0?'+':''}${v}`)}
  return [...new Set(out)].slice(0,7);
}
function v244QuestContextHtml(q,o=null){
  const prereq=(q?.prerequisites||[]).map(x=>x.name||x.id).filter(Boolean).slice(0,4),rewards=v244RewardSummary(q),req=[...(o?.requirements||[]),...(q?.requirements||[])],keys=[...new Set(req.map(x=>x?.name).filter(x=>/key|keycard/i.test(String(x))))].slice(0,3);
  const rows=[];if(prereq.length)rows.push(['Quest-chain',prereq.join(' → ')]);if(rewards.length)rows.push(['Reward',rewards.join(' · ')]);if(keys.length)rows.push(['Key / toegang',keys.join(' · ')]);if(q?.kappa)rows.push(['Progressie','Kappa-relevant']);if(q?.lightkeeper)rows.push(['Progressie','Lightkeeper-relevant']);
  return rows.length?`<div class="questContext">${rows.map(([a,b])=>`<div><small>${escapeHtml(a)}</small><span>${escapeHtml(b)}</span></div>`).join('')}</div>`:'';
}

function v244PoiConditionHtml(p){
  const rows=[];
  if(p?.faction)rows.push(['Type',p.faction]);
  const req=p?.requirement||p?.requirements||p?.condition;if(req){const t=Array.isArray(req)?req.map(x=>x.name||x.note||String(x)).join(' · '):String(req);if(t)rows.push(['Voorwaarde',t])}
  if(p?.note&&!/Offline fallback aligned/i.test(p.note))rows.push(['Info',p.note]);
  const aliases=v244Aliases(p);if(aliases.length)rows.push(['Ook te vinden als',aliases.slice(0,5).join(' · ')]);
  return rows.length?`<div class="pinFacts">${rows.map(([a,b])=>`<div><small>${escapeHtml(a)}</small><span>${escapeHtml(b)}</span></div>`).join('')}</div>`:'';
}

showPoiTip=function(ev,p){
  const t=$('poiTooltip');if(!t||!p)return;const cp=v244CorrectedPoi(p,p.map||mapKey()),pos=activePosition(),d=pos&&Number.isFinite(+cp.x)&&Number.isFinite(+cp.z)?Math.round(Math.hypot(cp.x-pos.x,cp.z-pos.z))+' m · ':'';const media=v244MediaEntryImages(p),mp=v244MapPreviewItem(p),thumb=media[0];
  t.innerHTML=`${thumb?`<img class="tipThumb" src="${escapeHtml(thumb.src)}" alt="">`:mp?`<div class="tipMapThumb" style="background-image:url('${escapeHtml(mp.src)}');background-size:430% auto;background-position:${(mp.nx*100).toFixed(1)}% ${(mp.ny*100).toFixed(1)}%"></div>`:''}<b>${escapeHtml(p.name||'POI')}</b><span>${d}${escapeHtml(categories[p.category]||p.category||'POI')}</span><small>${escapeHtml(v244Confidence(p).label)}</small>`;
  t.style.left=(ev.clientX+14)+'px';t.style.top=(ev.clientY+14)+'px';t.classList.remove('hidden');
};

showPoiDetail=function(p){
  if(!p)return;generalSelectedPoi=p;const d=$('poiDetail'),b=$('poiDetailBody');if(!d||!b)return;const cp=v244CorrectedPoi(p,p.map||mapKey()),canNav=Number.isFinite(+cp.x)&&Number.isFinite(+cp.z),distance=canNav&&activePosition()?Math.round(Math.hypot(cp.x-activePosition().x,cp.z-activePosition().z)):null;
  b.innerHTML=`<div class="detailEyebrow">${escapeHtml(categories[p.category]||p.category||'POI')}</div><h3>${escapeHtml(p.name||'POI')}</h3>${v244PinMediaShell(p)}${v244PoiConditionHtml(p)}${v244ConfidenceHtml(p)}${v244FloorHtml(p)}${distance!=null?`<div class="distanceCallout"><b>${distance} m</b><span>rechtstreeks vanaf huidige XYZ</span></div>`:''}<div class="poiActions">${canNav?'<button id="poiNavigateBtn" class="primaryPinAction">▶ Navigeer</button>':''}<button id="poiFocusBtn">Focus</button><button id="poiReportBtn">Pin klopt niet?</button></div>${p.worldApproximate?'<div class="pinSourceNote">Wereldafstand is een fallback; het zichtbare kaartpunt zelf kan via een vaste kaart-anchor of lokale correctie preciezer zijn.</div>':''}`;
  d.classList.remove('hidden');v244WireMedia(b,p);
  if(canNav)$('poiNavigateBtn').onclick=()=>{target={...cp,name:p.name||'POI',_type:p.category||'poi'};routeDirty=true;updateNav();draw()};
  $('poiFocusBtn').onclick=()=>focusGeneralPoi(p);$('poiReportBtn').onclick=()=>v244OpenPinReport(p);renderDomPins();draw();
};

showObjectiveDrawer=function(p,o,q){
  const d=$('objectiveDrawer'),c=$('objectiveDrawerContent'),st=objectiveStyle(p),done=questProgress(q.id).has(o.id),objectiveReq=[...(o.requirements||[])],fallbackReq=objectiveReq.length?[]:[...(q.requirements||[])].slice(0,4),req=objectiveReq.length?objectiveReq:fallbackReq;
  c.innerHTML=`<div class="drawerType" style="color:${st.color}">${escapeHtml(st.glyph)} ${escapeHtml(st.kind.toUpperCase())} · PIN ${p.markerNumber}</div><div class="drawerTitle"><span style="color:${st.color}">${escapeHtml(o.description)}</span></div><div class="drawerQuest">${escapeHtml(q.name)} · ${escapeHtml(q.trader||'Unknown')} · lvl ${q.minPlayerLevel||0}</div>${v244PinMediaShell(p,o,q)}<div class="drawerDo"><b>Wat moet je doen?</b><br>${escapeHtml(objectiveHint(o))}</div>${v244QuestContextHtml(q,o)}${req.length?`<div class="qpopReq"><b>${objectiveReq.length?'Voor dit doel nodig':'Raid-kit / mogelijk nodig'}:</b><br>${req.map(requirementLabel).map(escapeHtml).join('<br>')}</div>`:''}${v244FloorHtml(p,o)}${v244ConfidenceHtml(p)}<div class="drawerMeta"><span>${escapeHtml(questMapName(p.map))}</span>${p.level!==null&&p.level!==undefined?`<span>${escapeHtml(String(p.level).replaceAll('_',' '))}</span>`:''}<span>${v244MediaEntryImages(p,o,q).length?'Herkenningsbeeld + kaartspot':'Exacte kaartspot'}</span></div><div class="drawerActions"><button id="drawerNavigate" class="primaryPinAction">▶ Navigeer</button><button id="drawerDone">${done?'✓ Voltooid':'Afvinken'}</button><button id="drawerReport">Pin klopt niet?</button></div>`;
  d.classList.remove('hidden');v244WireMedia(c,p,o,q);
  $('drawerNavigate').onclick=()=>navigateQuestLocation(o.id,p.locationIndex);
  $('drawerDone').onclick=()=>{const set=questProgress(q.id);set.has(o.id)?set.delete(o.id):set.add(o.id);saveQuestProgress(q.id,set);buildActiveQuestPois();renderQuestCard();renderRaidPlan();d.classList.add('hidden');questSelectedPoi=null;draw()};
  $('drawerReport').onclick=()=>v244OpenPinReport(p);
};

function v244ReportPayload(p,reason,note,suggested=null){
  const k=p?.map||mapKey(),orig=v244OldPoiMapNormalized(p,k),pos=activePosition();
  return{map:k,pinKey:v244StableKey(p,k),name:p?.name||p?.objectiveDescription||'',category:p?.category||'poi',reason,note:note||'',original:orig?{nx:+orig.x,ny:+orig.y,x:Number.isFinite(+p?.x)?+p.x:null,z:Number.isFinite(+p?.z)?+p.z:null}:null,suggested,player:pos?{x:+pos.x,y:+pos.y,z:+pos.z}:null};
}
async function v244SendReport(p,reason,note,suggested=null){
  try{const r=await fetch('/api/pin-report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(v244ReportPayload(p,reason,note,suggested))});const d=await r.json();const s=$('pinReportStatus');if(s)s.textContent=d.ok?'Pinfeedback lokaal opgeslagen.':'Pinfeedback kon niet worden opgeslagen.';return!!d.ok}catch(e){const s=$('pinReportStatus');if(s)s.textContent='Pinfeedback kon niet naar de lokale backend worden geschreven.';return false}
}
function v244OpenPinReport(p){
  if(!p)return;v244PendingReport=p;$('pinReportName').textContent=`${p.name||p.objectiveDescription||'Pin'} · ${questMapName(p.map||mapKey())}`;$('pinReportNote').value='';$('pinReportModal').classList.remove('hidden');
}
function v244ClosePinReport(){v244PendingReport=null;$('pinReportModal')?.classList.add('hidden')}
function v244StartCorrection(p,note=''){
  if(!p)return;v244CorrectionMode={p,note};$('pinReportModal')?.classList.add('hidden');$('pinCorrectionBanner')?.classList.remove('hidden');const h=$('hudTarget');if(h)h.textContent=`Pin-correctie: klik de exacte plek voor ${p.name||p.objectiveDescription}`;
}
function v244StopCorrection(){v244CorrectionMode=null;$('pinCorrectionBanner')?.classList.add('hidden');updateNav()}
function v244CaptureCorrection(ev){
  if(!v244CorrectionMode)return false;const n=eventN(ev);if(n.x<0||n.x>1||n.y<0||n.y>1)return true;const p=v244CorrectionMode.p,k=p.map||mapKey(),w=inverseNormalized(n,k),store=v244CorrectionStore(),key=v244StableKey(p,k);store[key]={map:k,style:v244Style(),nx:n.x,ny:n.y,x:w?.x,z:w?.z,name:p.name||p.objectiveDescription||'',ts:Date.now(),note:v244CorrectionMode.note||''};v244SaveCorrectionStore(store);const suggested={nx:n.x,ny:n.y,x:w?.x,z:w?.z};v244SendReport(p,'manual-map-correction',v244CorrectionMode.note||'',suggested);v244StopCorrection();routeDirty=true;renderNearby();renderTargetSelect();renderDomPins();draw();if(p.questActive&&activeQuest){const o=(activeQuest.objectives||[]).find(x=>String(x.id)===String(p.objectiveId));if(o)showObjectiveDrawer(p,o,activeQuest)}else showPoiDetail(p);return true;
}
viewport.addEventListener('click',ev=>{if(v244CorrectionMode){ev.preventDefault();ev.stopImmediatePropagation();v244CaptureCorrection(ev)}},true);
window.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&v244CorrectionMode){ev.preventDefault();v244StopCorrection()}});

navigateQuestLocation=async function(objId,idx){
  await v244OldNavigateQuestLocation(objId,idx);
  if(questSelectedPoi){const cp=v244CorrectedPoi(questSelectedPoi,questSelectedPoi.map||mapKey());if(cp._localCorrection&&target){target={...target,x:cp.x,z:cp.z,nx:cp.nx,ny:cp.ny};routeDirty=true;updateNav();draw()}}
};

function v244SearchText(p){
  const k=p?.map||mapKey(),media=v244MediaEntryImages(p),kw=(v244PinMedia.questKeywords||[]).filter(x=>x.map===k&&x.image&&media.some(m=>m.src===x.image)).flatMap(x=>x.keywords||[]);
  return [p?.name,p?.note,p?.category,categories[p?.category],p?.faction,p?.objectiveDescription,p?.questName,...v244Aliases(p,k),...kw].filter(Boolean).join(' ').toLowerCase();
}
globalSearchRows=function(query){
  const q=String(query||'').trim().toLowerCase();if(!q)return[];const rows=[],seen=new Set();
  const addPoi=(p,sub)=>{const k=`${p.map||mapKey()}|${p.category||''}|${p.name||''}|${Math.round((+p.x||0)*10)}|${Math.round((+p.z||0)*10)}`;if(seen.has(k))return;seen.add(k);rows.push({type:'poi',label:p.name||p.objectiveDescription||'POI',sub,p})};
  for(const p of globalPoiIndex){if(v244SearchText(p).includes(q))addPoi(p,`${categories[p.category]||p.category||'POI'} · ${questMapName(p.map)}`)}
  for(const p of allPois()){if(v244SearchText(p).includes(q))addPoi({...p,map:p.map||mapKey()},`${p.questActive?(p.questName||'Quest'):(categories[p.category]||p.category)} · ${questMapName(p.map||mapKey())}`)}
  for(const w of waypoints())if([w.name,...v244Aliases(w)].join(' ').toLowerCase().includes(q))addPoi({...w,map:w.map||mapKey()},`Waypoint · ${questMapName(w.map||mapKey())}`);
  for(const qs of questCatalog){const hay=[qs.searchText,qs.name,qs.trader,(qs.maps||[]).join(' ')].join(' ').toLowerCase();if(hay.includes(q))rows.push({type:'quest',label:qs.name,sub:`${qs.trader} · ${(qs.maps||[]).map(questMapName).join(', ')}`,q:qs})}
  return rows.slice(0,30);
};

function v244SmartCandidates(){
  const src=[...activeQuestPois,...planQuestPois],seen=new Set(),out=[];
  for(const p of src){if(questObjectiveDone(p))continue;const cp=v244CorrectedPoi(p,p.map||mapKey());if(cp.map!==mapKey()||!Number.isFinite(+cp.x)||!Number.isFinite(+cp.z))continue;const key=v244StableKey(cp);if(seen.has(key))continue;seen.add(key);out.push(cp)}return out;
}
function v244SmartScore(p,pos){
  let s=Math.hypot(p.x-pos.x,p.z-pos.z),why=[];const lv=p.level??p.floor;if(lv&&currentFloor&&String(lv).toLowerCase()!==String(currentFloor).toLowerCase()){s+=75;why.push('andere verdieping')}
  const conf=v244Confidence(p);s+=(100-conf.score)*.35;if(conf.score<70)why.push('lagere locatiezekerheid');return{score:s,distance:Math.hypot(p.x-pos.x,p.z-pos.z),why};
}
function v244SmartNext(){const pos=activePosition();if(!pos)return null;return v244SmartCandidates().map(p=>({p,...v244SmartScore(p,pos)})).sort((a,b)=>a.score-b.score)[0]||null}
async function v244GoQuestPin(p){
  if(!p?.questId)return;if(activeQuest?.id!==p.questId){$('questSelect').value=p.questId;await selectQuest(p.questId)}await navigateQuestLocation(p.objectiveId,p.locationIndex||0);
}
renderNearby=function(){
  const box=$('nearby'),smart=$('smartNext');if(box)box.innerHTML='';if(smart)smart.innerHTML='';const pos=activePosition();if(!pos)return;
  const sn=v244SmartNext();if(smart&&sn){const p=sn.p,conf=v244Confidence(p);smart.innerHTML=`<button class="smartNextCard" type="button"><span class="smartKicker">SLIM VOLGENDE DOEL</span><b>${escapeHtml(p.questName||'Quest')} · ${escapeHtml(String(p.objectiveDescription||p.name).slice(0,70))}</b><small>${Math.round(sn.distance)} m rechtstreeks · ${escapeHtml(conf.label)}${sn.why.length?' · '+escapeHtml(sn.why.join(', ')):''}</small></button>`;smart.querySelector('button').onclick=()=>v244GoQuestPin(p)}
  if(!box)return;const arr=allPois().filter(poiVisible).map(q=>v244CorrectedPoi(q,q.map||mapKey())).filter(q=>Number.isFinite(+q.x)&&Number.isFinite(+q.z)).map(q=>({...q,d:dist(pos,q)})).sort((a,b)=>a.d-b.d).slice(0,20);for(const q of arr){const r=document.createElement('div');r.className='nearRow';r.innerHTML=`<span><i class="poiDot" style="background:${catColor[q.category]||catColor.user}"></i>${escapeHtml(q.name||q.objectiveDescription||'POI')}</span><span>${Math.round(q.d)}m</span>`;r.onclick=()=>{target={...q,_type:q.category};$('targetSelect').value='';routeDirty=true;updateNav();draw()};box.append(r)}
};

function v244PlanDistance(order,start){let t=0,cur=start?{x:start.x,z:start.z}:null;for(const r of order){const p=v244CorrectedPoi({...r.l,map:r.l.map,category:'quest',questActive:true,questId:r.qid,objectiveId:r.o.id,locationIndex:r.li},r.l.map);if(cur)t+=Math.hypot(p.x-cur.x,p.z-cur.z);cur={x:p.x,z:p.z}}return t}
function v244Optimize2Opt(order,start){if(order.length<4||order.length>55)return order;let best=order.slice(),bd=v244PlanDistance(best,start),improved=true,passes=0;while(improved&&passes++<5){improved=false;for(let i=0;i<best.length-2;i++){for(let j=i+1;j<best.length-1;j++){const cand=[...best.slice(0,i),...best.slice(i,j+1).reverse(),...best.slice(j+1)],d=v244PlanDistance(cand,start);if(d+1<bd){best=cand;bd=d;improved=true}}}}return best}
function v244RecommendExtract(order){
  const last=order.length?order[order.length-1]:null,pos=last?v244CorrectedPoi({...last.l,map:last.l.map,category:'quest',questActive:true,questId:last.qid,objectiveId:last.o.id,locationIndex:last.li},last.l.map):activePosition();if(!pos)return null;let ex=currentExtracts().map(p=>v244CorrectedPoi(p,p.map||mapKey())).filter(p=>Number.isFinite(+p.x)&&Number.isFinite(+p.z));const exact=ex.filter(p=>!p.worldApproximate);if(exact.length)ex=exact;return ex.map(p=>({p,d:Math.hypot(p.x-pos.x,p.z-pos.z)})).sort((a,b)=>a.d-b.d)[0]||null;
}
optimizeRaidPlan=function(){
  let rows=buildPlanCandidates(),cur=activePosition()?{x:activePosition().x,z:activePosition().z}:null;if(!rows.length){raidPlanOrder=[];v244RaidExtract=null;renderRaidPlanRoute();return}const order=[];while(rows.length){let idx=0;if(cur){let bd=Infinity;rows.forEach((r,i)=>{const p=v244CorrectedPoi({...r.l,map:r.l.map,category:'quest',questActive:true,questId:r.qid,objectiveId:r.o.id,locationIndex:r.li},r.l.map),d=Math.hypot(p.x-cur.x,p.z-cur.z);if(d<bd){bd=d;idx=i}})}const r=rows.splice(idx,1)[0];order.push(r);const pp=v244CorrectedPoi({...r.l,map:r.l.map,category:'quest',questActive:true,questId:r.qid,objectiveId:r.o.id,locationIndex:r.li},r.l.map);cur={x:pp.x,z:pp.z}}raidPlanOrder=v244Optimize2Opt(order,activePosition());planStepIndex=0;v244RaidExtract=$('planEndExtract')?.checked?v244RecommendExtract(raidPlanOrder):null;renderRaidPlanRoute();if(raidPlanOrder[0])navigatePlanStep(0)
};
renderRaidPlanRoute=function(){
  const b=$('raidPlanRoute');if(!b)return;b.innerHTML='';const rows=raidPlanOrder.length?raidPlanOrder:buildPlanCandidates();if(!rows.length){b.innerHTML='<div class="statusLine">Geen open questpins op deze map.</div>';return}let cur=activePosition()?{x:activePosition().x,z:activePosition().z}:null,total=0;rows.forEach((r,i)=>{const cp=v244CorrectedPoi({...r.l,map:r.l.map,category:'quest',questActive:true,questId:r.qid,objectiveId:r.o.id,locationIndex:r.li},r.l.map),leg=cur?Math.hypot(cp.x-cur.x,cp.z-cur.z):0;total+=leg;cur={x:cp.x,z:cp.z};const d=document.createElement('div');d.className='planStep';d.innerHTML=`<b>${i+1}</b><span>${escapeHtml(r.q.name)}<br><small>${escapeHtml(r.o.description)}</small></span><span>${cur?Math.round(leg)+'m':''}</span>`;d.onclick=()=>navigatePlanStep(i);b.append(d)});v244RaidExtract=$('planEndExtract')?.checked?v244RecommendExtract(rows):null;if(v244RaidExtract){total+=v244RaidExtract.d;const ex=document.createElement('button');ex.type='button';ex.className='planExtractStep';ex.innerHTML=`<b>⇥</b><span>Aanbevolen extract<br><small>${escapeHtml(v244RaidExtract.p.name)} · controleer extractvoorwaarden</small></span><span>${Math.round(v244RaidExtract.d)}m</span>`;ex.onclick=()=>{const p=v244RaidExtract.p;target={...p,_type:'extract'};routeDirty=true;focusGeneralPoi(p);updateNav();draw()};b.append(ex)}const sum=document.createElement('div');sum.className='planSummary';sum.innerHTML=`<b>≈ ${Math.round(total)} m</b><span>directe segmenten · ${rows.length} questspot${rows.length===1?'':'s'}${v244RaidExtract?' + extract':''}</span>`;b.prepend(sum)
};

function v244DrawSelectedHighlight(){
  const p=questSelectedPoi||generalSelectedPoi;if(!p)return;ctx.save();const t=performance.now()/550,a=.36+.16*Math.sin(t),col=p.questActive?objectiveStyle(p).color:(catColor[p.category]||'#fff');if(Array.isArray(p.outline)&&p.outline.length>=3){const pts=p.outline.map(q=>Number.isFinite(+q.x)&&Number.isFinite(+q.z)?toP(worldNormalizedRaw(+q.x,+q.z)):null).filter(Boolean);if(pts.length>=3){ctx.beginPath();pts.forEach((q,i)=>i?ctx.lineTo(q.x,q.y):ctx.moveTo(q.x,q.y));ctx.closePath();ctx.fillStyle=col+'22';ctx.strokeStyle=col;ctx.lineWidth=4/zoom;ctx.setLineDash([10/zoom,5/zoom]);ctx.fill();ctx.stroke()}}else{const n=poiMapNormalized(p,p.map||mapKey());if(n){const q=toP(n),r=(22+7*Math.sin(t))/zoom;ctx.strokeStyle=col;ctx.globalAlpha=a+.35;ctx.lineWidth=3/zoom;ctx.beginPath();ctx.arc(q.x,q.y,r,0,Math.PI*2);ctx.stroke();ctx.globalAlpha=.8;ctx.beginPath();ctx.moveTo(q.x-r*1.35,q.y);ctx.lineTo(q.x+r*1.35,q.y);ctx.moveTo(q.x,q.y-r*1.35);ctx.lineTo(q.x,q.y+r*1.35);ctx.stroke()}}ctx.restore();
}
draw=function(){v244OldDraw();v244DrawSelectedHighlight()};

renderDomPins=function(){v244OldRenderDomPins();const buttons=$('domPins')?.querySelectorAll?.('.domMapPin:not(.cluster)')||[];for(const b of buttons){const title=b.title||'',p=allPois().find(x=>(x.name||x.objectiveDescription||'')===title);if(p&&v244MediaEntryImages(p).length)b.classList.add('hasMedia')}};

setTargetValue=function(v){
  if(!v){target=null;routeDirty=true;updateNav();draw();return}
  if(v.startsWith('q:')){const p=activeQuestPois[+v.slice(2)],q=p?v244CorrectedPoi(p,p.map||mapKey()):null;target=q?{...q,_type:'quest',_id:v}:null}
  else if(v.startsWith('ex:')){const p=currentExtracts()[+v.slice(3)],q=p?v244CorrectedPoi(p,p.map||mapKey()):null;target=q?{...q,_type:'extract',_id:v}:null}
  else if(v.startsWith('wp:')){const w=waypoints().find(x=>String(x.id)===v.slice(3));target=w?{...w,_type:'waypoint',_id:v}:null}
  routeDirty=true;updateNav();draw();
};
renderGlobalSearch=function(){
  const b=$('searchResults'),query=$('globalSearch').value,rows=globalSearchRows(query);b.innerHTML='';if(!query||!rows.length){b.classList.add('hidden');return}
  rows.forEach(r=>{const d=document.createElement('div');d.className='searchRow';d.innerHTML=`<b>${escapeHtml(r.label)}</b><span>${escapeHtml(r.sub)}</span>`;d.onclick=async()=>{b.classList.add('hidden');$('globalSearch').value='';if(r.type==='quest'){$('questSelect').value=r.q.id;await selectQuest(r.q.id);return}let p=r.p;if(p.map&&p.map!==mapKey()&&maps[p.map]){visualMapKey=p.map;$('map').value=p.map;loadMap(p.map)}p=v244CorrectedPoi(p,p.map||mapKey());target={...p,name:p.name||'Zoekresultaat',_type:p.category||'search'};routeDirty=true;follow=false;const n=poiMapNormalized(p,p.map||mapKey());if(!n)return;const q2=toP(n);zoom=Math.max(zoom,2.7);const sc=fitScale*zoom;panX=-(q2.x-baseW/2)*sc;panY=-(q2.y-baseH/2)*sc;updateTransform();updateNav();draw()};b.append(d)});b.classList.remove('hidden')
};

function v244WireUi(){
  if($('mediaLightboxClose'))$('mediaLightboxClose').onclick=()=>$('mediaLightbox').classList.add('hidden');
  if($('mediaLightbox'))$('mediaLightbox').addEventListener('click',e=>{if(e.target===$('mediaLightbox'))$('mediaLightbox').classList.add('hidden')});
  const close=()=>v244ClosePinReport();if($('pinReportClose'))$('pinReportClose').onclick=close;if($('pinReportCancel'))$('pinReportCancel').onclick=close;
  if($('pinReportSend'))$('pinReportSend').onclick=async()=>{if(!v244PendingReport)return;const p=v244PendingReport,n=$('pinReportNote').value;await v244SendReport(p,'user-report',n);v244ClosePinReport()};
  if($('pinReportPick'))$('pinReportPick').onclick=()=>{if(!v244PendingReport)return;const p=v244PendingReport,n=$('pinReportNote').value;v244PendingReport=null;v244StartCorrection(p,n)};
  if($('clearPinCorrectionsBtn'))$('clearPinCorrectionsBtn').onclick=()=>{if(confirm('Alle lokale pin-correcties wissen?')){v244SaveCorrectionStore({});routeDirty=true;renderDomPins();draw();renderNearby();$('pinReportStatus').textContent='Lokale pin-correcties gewist.'}};
  if($('planEndExtract'))$('planEndExtract').onchange=()=>{v244RaidExtract=null;renderRaidPlanRoute()};
  setTimeout(()=>{renderNearby();renderRaidPlanRoute();renderDomPins()},900);
}
v244WireUi();


// v24.5 — dedicated extraction image popup on pin click.
var v245ActiveExtractPoi=null;
function v245PreferredExtractItems(p){
  const raw=v244MediaItems(p),images=raw.filter(x=>x&&x.kind==='image'),maps=raw.filter(x=>x&&x.kind==='map');
  return images.length?[...images,...maps]:raw;
}
function v245OpenExtractPreview(p){
  if(!p)return;v245ActiveExtractPoi=p;generalSelectedPoi=p;
  const modal=$('extractPreviewModal'),body=$('extractPreviewBody');if(!modal||!body)return;
  const cp=v244CorrectedPoi(p,p.map||mapKey()),canNav=Number.isFinite(+cp.x)&&Number.isFinite(+cp.z),distance=canNav&&activePosition()?Math.round(Math.hypot(cp.x-activePosition().x,cp.z-activePosition().z)):null,conf=v244Confidence(p),items=v245PreferredExtractItems(p),hasReal=items.some(x=>x.kind==='image');
  body.innerHTML=`<div class="extractPreviewMain">${v244PinMediaShell({...p,__v245Items:items})}</div><aside class="extractPreviewAside"><div class="detailEyebrow">EXTRACT VERGELIJKEN</div><div class="extractCompareNote">Vergelijk dit herkenningsbeeld met wat je in raid ziet. Klik op de afbeelding voor een grotere versie. ${hasReal?'De echte extractfoto staat vooraan; de exacte kaartspot is als extra slide beschikbaar.':'Voor deze extract is nog geen aparte foto gevonden; de popup toont daarom direct de exacte kaartspot.'}</div>${distance!=null?`<div class="distanceCallout"><b>${distance} m</b><span>rechtstreeks vanaf je huidige positie</span></div>`:''}${v244PoiConditionHtml(p)}${v244FloorHtml(p)}${v244ConfidenceHtml(p)}<div class="pinFacts"><div><small>Map</small><span>${escapeHtml(questMapName(p.map||mapKey()))}</span></div><div><small>Type</small><span>Extraction</span></div>${items.length?`<div><small>Preview</small><span>${escapeHtml(items[0].label||'Locatiebeeld')}${hasReal?' · foto + kaartspot':' · kaartspot'}</span></div>`:''}</div></aside>`;
  $('extractPreviewTitle').textContent=p.name||'Extract voorbeeld';
  $('extractPreviewSub').textContent='Aparte extract-popup · vergelijk het beeld met je huidige omgeving.';
  $('extractPreviewMeta').textContent=[distance!=null?`${distance} m vanaf huidige positie`:null,conf.label,hasReal?'Eerste slide = herkenningsbeeld':'Alleen kaartpreview beschikbaar'].filter(Boolean).join(' · ');
  modal.classList.remove('hidden');
  v244WireMedia(body.querySelector('.extractPreviewMain'),{...p,__v245Items:items});
  $('extractPreviewNavigate').onclick=()=>{if(canNav){target={...cp,name:p.name||'Extract',_type:'extract'};routeDirty=true;updateNav();draw();}};
  $('extractPreviewFocus').onclick=()=>focusGeneralPoi(p);
  $('extractPreviewInfo').onclick=()=>{modal.classList.add('hidden');showPoiDetail(p)};
  renderDomPins();draw();
}
function v245CloseExtractPreview(){v245ActiveExtractPoi=null;$('extractPreviewModal')?.classList.add('hidden')}
(function(){
  const oldMediaItems=v244MediaItems;
  v244MediaItems=function(p,o=null,q=null){if(p&&Array.isArray(p.__v245Items))return p.__v245Items;return oldMediaItems(p,o,q)};
})();
function v245FindExtractFromButton(btn){
  const name=btn?.title||'';if(!name)return null;
  const pois=allPois().filter(p=>!p.questActive&&p.category==='extract'&&(p.name||p.objectiveDescription||'')===name);
  return pois[0]||null;
}
function v245BindExtractClicks(){
  const layer=$('domPins');if(!layer||layer._v245ExtractBound)return;layer._v245ExtractBound=true;
  layer.addEventListener('click',ev=>{
    const btn=ev.target?.closest?.('.domMapPin.pin-extract:not(.cluster)');if(!btn)return;const p=v245FindExtractFromButton(btn);if(!p)return;
    ev.preventDefault();ev.stopImmediatePropagation();hidePoiTip();$('poiDetail')?.classList.add('hidden');hideQuestPopup?.();
    v245OpenExtractPreview(p);
  },true);
}
function v245WireExtractUi(){
  if($('extractPreviewClose'))$('extractPreviewClose').onclick=v245CloseExtractPreview;
  if($('extractPreviewModal'))$('extractPreviewModal').addEventListener('click',e=>{if(e.target===$('extractPreviewModal'))v245CloseExtractPreview()});
  window.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('extractPreviewModal')?.classList.contains('hidden'))v245CloseExtractPreview()});
  v245BindExtractClicks();
}
v245WireExtractUi();
