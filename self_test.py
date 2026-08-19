from pathlib import Path
import json, re, py_compile, sys
import tracker_mvp as tm
ROOT=Path(__file__).resolve().parent
errors=[]
try: py_compile.compile(str(ROOT/'tracker_mvp.py'),doraise=True)
except Exception as e: errors.append(f'Python: {e}')
try:
    maps=json.loads((ROOT/'maps.json').read_text(encoding='utf-8'))
    if len(maps)<10: errors.append('Minder dan 10 lokale maps')
    for k,m in maps.items():
        for style,path in (m.get('styles') or {}).items():
            f=ROOT/'web'/path.lstrip('/')
            if not f.exists(): errors.append(f'Mapasset ontbreekt {k}/{style}')
        mask=m.get('mask')
        if mask and not (ROOT/'web'/mask.lstrip('/')).exists(): errors.append(f'Mask ontbreekt {k}')
except Exception as e: errors.append(f'Maps: {e}')
app_js=(ROOT/'web'/'app.js').read_text(encoding='utf-8'); v244_js=(ROOT/'web'/'v244.js').read_text(encoding='utf-8'); v246_js=(ROOT/'web'/'v246.js').read_text(encoding='utf-8'); js=app_js+'\n'+v244_js+'\n'+v246_js; html=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
ids=set(re.findall(r"\\$\\('([^']+)'\\)",js))
hids=set(re.findall(r'id="([^"]+)"',html))
# dynamic ids are created by JS itself
missing=sorted(x for x in ids-hids if x not in {'missionNextBtn','missionOverviewBtn','missionListBtn','drawerNavigate','drawerDone'})
if missing: errors.append('HTML IDs ontbreken: '+', '.join(missing))
print('Tarkov Compass v24.6 self-test')
if errors:
    print('FOUT:'); [print(' -',x) for x in errors]; sys.exit(1)
print('OK - Python, mapassets en DOM-contract gecontroleerd.')

code=(ROOT/'tracker_mvp.py').read_text(encoding='utf-8')
assert 'enabled=bool(state.get("capture_enabled", True))' in code, 'capture state ontbreekt in input loop'

# Productregressies
assert "function setInterval(" not in js, "browser setInterval wordt overschreven"
assert "saveCaptureInterval" in js, "capture-interval save-functie ontbreekt"
assert 'path_only=="/api/poi-index"' in code, "globale POI index endpoint ontbreekt"
assert (ROOT/'START_TRACKER.bat').exists(), 'START_TRACKER.bat ontbreekt'
assert (ROOT/'START_TARKOV_COMPASS.bat').exists() and (ROOT/'STOP_TARKOV_COMPASS.bat').exists(), 'Tarkov Compass launchers ontbreken'
assert not any(ROOT.glob('*.vbs')), 'VBS launcher hoort niet in productbuild'

assert 'domPins' in html, 'DOM pinlaag ontbreekt'
assert 'function renderDomPins' in js, 'DOM pin engine ontbreekt'
assert len(maps)>=13, 'Niet alle RE3MR hoofdkaarten aanwezig'
assert all((m.get('source')=='RE3MR' or k=='lab') for k,m in maps.items()), 'Onverwachte mapbron'


required={'customs','factory','groundzero','icebreaker','interchange','labyrinth','lighthouse','reserve','shoreline','streetsoftarkov','terminal','woods','transit'}
assert required.issubset(maps), 'RE3MR mapset incompleet: '+', '.join(sorted(required-set(maps)))
for k in required:
    m=maps[k]
    assert m.get('styles',{}).get('reemr'), f'{k}: RE3MR style ontbreekt'
    assert (ROOT/'web'/m['styles']['reemr'].lstrip('/')).exists(), f'{k}: RE3MR bestand ontbreekt'
    assert m.get('starterPins'), f'{k}: lokale startpins ontbreken'
assert "eft-v24-2-reemr-prefs-" in js, 'v24.2 voorkeuren zijn niet geisoleerd'
# Live-position regressions: raw XYZ must remain authoritative; visual aids may not
# silently move the player several metres.
assert 'playerMarkerSize' in html and "playerPx=+$('playerMarkerSize').value||72" in js, 'aparte grotere spelerpijl ontbreekt'
assert 'screenScale=Math.max(.05,fitScale*zoom)' in js, 'spelerpijl is niet schermpixel-stabiel'
assert 'Math.min(.35' in js, 'prediction horizon is niet begrensd op 0,35 s'
assert 'function calibrationWorldPosition(){return state?.position' in js, 'kalibratie gebruikt niet de ruwe serverpositie'
assert 'migrated?false:(v.playerSnap??false)' in js, 'walkable snap staat niet veilig standaard uit'
assert "worldNormalized(pos.x,pos.z,$('snapWalkable').checked)" in js, 'spelerpositie respecteert opt-in snap niet'
assert 'undoCalBtn' in html and "$('undoCalBtn').onclick" in js, 'kalibratiepunt terugdraaien ontbreekt'
assert "age>1.25" in js and "speedMps>1.2" in js, 'kalibratie weigert geen oude/bewegende metingen'
assert "visualMapKey=chosen" in js and "parentMap||chosen" in js, 'handmatige mapwissel/detailmap routing ontbreekt'
assert 'container:' in js and 'loot:' in js, 'loot/container filters ontbreken'
assert 'renderDomPins()' in js, 'DOM pins worden niet gerenderd'

# v24.3 extraction/pin alignment regressions. RE3MR visual anchors are measured
# directly against the bundled map image and intentionally separate from live
# game-world coordinates. This keeps the marker tip on the printed map symbol.
anchor_path=ROOT/'web'/'data'/'map_pin_anchors.json'
assert anchor_path.exists(), 'vaste RE3MR pin-anchors ontbreken'
anchor_doc=json.loads(anchor_path.read_text(encoding='utf-8'))
extract_anchors=anchor_doc.get('maps',{}).get('streetsoftarkov',{}).get('reemr',{}).get('extract',{})
assert len(extract_anchors)>=17, 'Streets heeft niet alle 17 extract display-anchors'
def _qa_canon(name):
    import unicodedata
    v=''.join(c for c in unicodedata.normalize('NFKD',str(name or '')) if not unicodedata.combining(c)).lower().replace('’','').replace("'",'')
    v=re.sub(r'\([^)]*\)',' ',v); v=re.sub(r'[^a-z0-9]+',' ',v); return re.sub(r'\s+',' ',v).strip()
_current_streets_extracts=['Courtyard','Primorsky Ave Taxi V-Ex','Stylobate Building Elevator','Crash Site','Sewer River','Damaged House','Collapsed Crane','Klimov Street (Flare)','Pinewood Basement (Co-Op)','Expo Checkpoint',"Smugglers' Basement",'Entrance to Catacombs','Ventilation Shaft','Sewer Manhole','Near Kamchatskaya Arch','Cardinal Apartment Complex Parking','Klimov Shopping Mall Exfil']
assert {_qa_canon(x) for x in _current_streets_extracts}==set(extract_anchors), 'current Streets extractnaamvarianten matchen de anchor keys niet'
vent=extract_anchors.get('ventilation shaft')
assert vent and abs(vent['nx']-0.758381)<1e-6 and abs(vent['ny']-0.896132)<1e-6, 'Ventilation Shaft display-anchor is verschoven'
assert all(0<=float(a['nx'])<=1 and 0<=float(a['ny'])<=1 for a in extract_anchors.values()), 'display-anchor buiten kaartgrenzen'
curated=json.loads((ROOT/'web'/'data'/'streets_curated.json').read_text(encoding='utf-8'))
curated_extracts=[r for r in curated if r.get('category')=='extract']
assert len(curated_extracts)==17 and any(r.get('name')=='Sewer River' for r in curated_extracts), 'Streets offline extract fallback is niet compleet'
assert 'function displayAnchorFor' in js and 'function poiMapNormalized' in js and 'function currentExtracts' in js, 'anchor-aware pin/target functies ontbreken'
assert "await Promise.all([loadStreetsCurated(),loadMapPinAnchors()])" in js, 'pin-anchor dataset wordt niet bij init geladen'
assert "const merged=[...base,...cur,...starter" in js, 'live API heeft niet de hoogste extractbron-prioriteit'
assert "(cat==='extract'||cat==='transit')" in js and 'canonicalPoiName(p.name)' in js, 'extract/transit dedupe op naam ontbreekt'
assert 'function pinNormalized(p){return poiMapNormalized(p)}' in js, 'DOM pins gebruiken niet dezelfde anchor-aware projectie'
assert "p.category==='extract'||p.category==='transit'" in js and 'const critical=pins.filter' in js, 'extract/transit pins mogen niet in automatische clusters verdwijnen'
css=(ROOT/'web'/'style.css').read_text(encoding='utf-8')
assert '.domMapPin.pin-extract,.domMapPin.pin-transit{z-index:6}' in css, 'extract/transit pinlaag ontbreekt'
assert '.domMapPin:not(.cluster)::after' in css and 'bottom:0' in css, 'exacte pin-tip anchor-dot ontbreekt'
assert 'width:28px;height:28px;transform:translate(-50%,-100%)' in css, 'pincontainer is niet op zijn bottom-center geankerd'
cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
assert cfg.get('app_name')=='Tarkov Compass', 'config app_name is niet Tarkov Compass'
assert 'TarkovCompassSingleInstance' in code and 'TarkovCompass/24.6' in code, 'backend interne app-identiteit is niet Tarkov Compass'
assert str(cfg.get('app_version','')).startswith('24.6-'), 'app_version is niet v24.6'
assert 'str(cfg.get("app_version", "24.6-progression-planner"))' in code, 'backend publiceert config app_version niet'
assert 'Tarkov Compass v24.6' in html and 'TARKOV COMPASS' in html and 'account progression planner' in html, 'frontend Tarkov Compass buildlabel is niet v24.6'
assert 'function drawQuestZones' in js and "drawQuestZones([...activeQuestPois" in js, 'quest-zone polygonen worden niet door de actieve DOM-pin renderer getekend'
# v24.4 media + smart navigation regressions. Every pin must have an exact local
# RE3MR map-preview fallback; bundled recognition images enrich the most useful spots.
media_path=ROOT/'web'/'data'/'pin_media.json'
assert media_path.exists(), 'pin media manifest ontbreekt'
media=json.loads(media_path.read_text(encoding='utf-8'))
assert media.get('version')=='24.4', 'pin media manifest heeft verkeerde versie'
assert len(media.get('exact',{}))==17, 'niet alle 17 Streets extracts hebben een herkenningsbeeld-entry'
assert len(media.get('questKeywords',[]))>=30, 'te weinig gebundelde quest-herkenningsbeelden'
for entry in media.get('exact',{}).values():
    for im in entry.get('images',[]):
        assert (ROOT/'web'/im['src'].lstrip('/')).exists(), 'media asset ontbreekt: '+str(im.get('src'))
for entry in media.get('questKeywords',[]):
    assert (ROOT/'web'/entry['image'].lstrip('/')).exists(), 'quest media asset ontbreekt: '+str(entry.get('image'))
assert 'v244PinMediaShell' in v244_js and 'Exacte kaartspot' in v244_js and 'mapSpotPreview' in css, 'universele pin-thumbnail fallback ontbreekt'
assert 'v244OpenPinReport' in v244_js and '/api/pin-report' in code and 'pin_reports.json' in code, 'pin feedback/correctie ontbreekt'
assert 'eft-v244-pin-corrections' in v244_js and 'v244CaptureCorrection' in v244_js, 'lokale kaartcorrecties ontbreken'
assert 'v244Optimize2Opt' in v244_js and 'v244RecommendExtract' in v244_js and 'planEndExtract' in html, 'Smart Route + extractadvies ontbreekt'
assert 'v244SmartNext' in v244_js and 'smartNext' in html, 'slim volgende questdoel ontbreekt'
assert 'v244Aliases' in v244_js and 'globalSearchRows=function' in v244_js, 'alias search ontbreekt'
assert 'v244FloorGuidance' in v244_js and 'v244Confidence' in v244_js, 'floor guidance/confidence ontbreekt'
assert 'v244DrawSelectedHighlight' in v244_js, 'selected zone/pin highlight ontbreekt'
assert '.domMapPin.hasMedia::before' in css, 'media-indicator op pins ontbreekt'
assert 'mediaLightbox' in html and 'pinReportModal' in html and 'pinCorrectionBanner' in html, 'media/report UI ontbreekt'
assert "p.level!==null&&p.level!==undefined" in js and "next&&next.level!==null&&next.level!==undefined" in js, 'floor 0 wordt niet overal in de quest UI weergegeven'

# v24.6 account progression planner regressions.
assert (ROOT/'web'/'v246.js').exists(), 'v24.6 progression script ontbreekt'
assert 'progressionPlanner' in html and 'progressionLevel' in html and 'bestRaidRecommendation' in html, 'progression planner UI ontbreekt'
assert 'v246QuestState' in v246_js and 'v246Recommendation' in v246_js and 'v246SimulatedUnlocks' in v246_js, 'quest dependency/recommendation engine ontbreekt'
assert 'v246AggregateKit' in v246_js and 'v246LoadRecommendedRaid' in v246_js, 'raid-kit of raid-plan koppeling ontbreekt'
assert 'eft-v246-completed-quests' in v246_js and 'eft-v246-player-level' in v246_js, 'accountprogressie wordt niet lokaal bewaard'
assert 'progressionFaction' in html and 'eft-v246-faction' in v246_js and 'v246FactionMatches' in v246_js, 'USEC/BEAR progressionfilter ontbreekt'
assert '.progressionStats' in css and '.bestRaidRecommendation' in css, 'progression planner styling ontbreekt'
# Catalog summaries must carry enough dependency + kit data without sending full objectives.
_sample_q={"id":"qa","name":"A","trader":"T","maps":["customs"],"minPlayerLevel":7,"objectives":[{"id":"o"}],"requirements":[{"kind":"key","id":"k","name":"Test key","count":1}],"prerequisites":[{"id":"qb","name":"B","status":["complete"]}],"hasLocations":True}
_summary=tm._quest_summary(_sample_q)
assert _summary.get('prerequisites',[{}])[0].get('id')=='qb', 'quest summary mist prerequisite dependency'
assert _summary.get('requirements',[{}])[0].get('name')=='Test key', 'quest summary mist raid-kit requirement'

for k in {'customs_dorms','reserve_tunnels','shoreline_resort','streets_caches','streets_lexos','woods_train_depot'}:
    assert k in maps and maps[k].get('group')=='detail', f'{k}: detailkaart ontbreekt'

# Quest-data regressies: every source that can add/correct a physical quest
# location must reach the same interactive objective.locations array.
base_tasks={"data":{"tasks":[{
    "id":"quest-a","name":"Overlay Spot Test","map":"map-interchange",
    "objectives":[{"id":"objective-a","type":"visit","description":"Visit the test spot on Interchange"}]
}]}}
map_rows={"data":{"maps":[{"id":"map-interchange","name":"Interchange","normalizedName":"interchange"}]}}
overlay={
    "tasks":{"quest-a":{"objectives":{"objective-a":{"zones":[{
        "zoneId":"test_zone","map":{"id":"map-interchange","name":"Interchange"},
        "position":{"x":428.755,"y":28.55,"z":125.8475}
    }]}}}},
    "tasksAdd":{"quest-b":{"id":"quest-b","name":"Added Quest","map":{"id":"map-interchange","name":"Interchange"},"objectives":[{"id":"objective-b","description":"Added objective"}]}},
    "locales":{"en":{"tasks":{"quest-b":{"name":"Added Quest EN"}}}}
}
normalized=tm._normalize_tasks_current(base_tasks,{}, {},{}, map_rows,{}, {},{}, overlay)
qa=next(q for q in normalized if q['id']=='quest-a')
assert qa['hasLocations'], 'overlay zones bereiken de quest-normalizer niet'
loc=qa['objectives'][0]['locations'][0]
assert loc['map']=='interchange' and abs(loc['x']-428.755)<1e-6 and abs(loc['z']-125.8475)<1e-6, 'overlay questspot is gewijzigd/verloren'
qb=next(q for q in normalized if q['id']=='quest-b')
assert qb['name']=='Added Quest EN', 'tasksAdd/locale overlay-volgorde werkt niet'

# Current API slice uses possibleLocations.positions; this was previously silently
# skipped and is the exact shape used by quests with multiple possible spawn spots.
snapshot={"quests":[{"id":"quest-woods","objectiveMaps":["Woods"],"objectives":[{
    "id":"objective-package","type":"findQuestItem","description":"Locate package on Woods","maps":["Woods"],
    "possibleLocations":[{"map":"Woods","positions":[
        {"x":-619.19604,"y":8.457,"z":127.90881},
        {"x":-612.7649,"y":9.221001,"z":136.13657}
    ]}]
}]}]}
positional=tm._normalize_objective_snapshot(snapshot)
plocs=positional[0]['objectives'][0]['locations']
assert len(plocs)==2, 'possibleLocations.positions levert niet alle alternatieve quest-spots'
assert {round(x['x'],3) for x in plocs}=={-619.196,-612.765}, 'possible-location coordinaten gewijzigd'

primary=[{"id":"quest-woods","gameId":"quest-woods","name":"Q","normalizedName":"q","maps":["woods"],"objectives":[{"id":"objective-package","description":"Spot","maps":["woods"],"locations":[{"map":"woods","x":-619.19604,"y":8.457,"z":127.90881,"level":None,"supported":True}]}]}]
merged=tm._merge_positional_quests(primary,positional,only_when_empty=False)
assert len(merged[0]['objectives'][0]['locations'])==2, 'current positional supplement wordt niet als union samengevoegd'

# Same coordinate + missing floor metadata must enrich, not duplicate, the spot.
same_spot=tm._merge_location_lists(
    [{'map':'lab','x':1.0,'y':0.0,'z':2.0,'level':None,'supported':True}],
    [{'map':'lab','x':1.0,'y':0.0,'z':2.0,'level':0,'supported':True}]
)
assert len(same_spot)==1 and same_spot[0]['level']==0, 'vloermetadata veroorzaakt een dubbele fysieke questspot'

# Archived fallback may only fill empty objectives; it must never resurrect an old
# alternative coordinate alongside a current, already mapped objective.
legacy=[{"id":"quest-woods","gameId":"quest-woods","name":"Q","normalizedName":"q","maps":["woods"],"objectives":[{"id":"objective-package","description":"Spot","maps":["woods"],"locations":[{"map":"woods","x":999.0,"y":0.0,"z":999.0,"level":None,"supported":True}]}]}]
legacy_merged=tm._merge_tarkovlab(merged,legacy)
assert len(legacy_merged[0]['objectives'][0]['locations'])==2, 'oude fallback overschrijft/vergroot actuele quest-spots'

# Hand-checked corrections: move a published pin, keep floor 0, and hide a known
# false API marker for the same objective.
correction_quest=[{"id":"qc","gameId":"qc","name":"Correction","normalizedName":"correction","maps":["lab"],"objectives":[{
    "id":"objective-c","description":"Correct me","maps":["lab"],"locations":[
        {"map":"lab","x":-169.0,"y":0.0,"z":-342.0,"level":None,"supported":True},
        {"map":"lab","x":-168.0,"y":0.0,"z":-344.0,"level":None,"supported":True}
    ]
}]}]
map_side={"corrections":{
    "objectives":{"The Lab|objective-c|-169|-342":{"x":-161.2,"z":-347.3}},
    "objectiveFloors":{"The Lab|objective-c|-169|-342":0},
    "hidden":{"api|The Lab|objective-c|-168|-344":True}
}}
counts=tm._apply_map_objective_corrections(correction_quest,map_side)
clocs=correction_quest[0]['objectives'][0]['locations']
assert len(clocs)==1 and abs(clocs[0]['x']+161.2)<1e-6 and abs(clocs[0]['z']+347.3)<1e-6, 'pin-correctie/hide-regel werkt niet'
assert clocs[0]['level']==0, 'floor 0 gaat verloren'
assert counts=={'moved':1,'floors':1,'hidden':1}, 'correctie-statistiek klopt niet'

# Story chapters remain ordinary interactive quest records, with local progress ids
# namespaced away from trader task ids.
story_raw={"story":{"chapters":[{
    "id":"tour","questId":"story-game-id","name":"Tour","order":1,"wikiLink":"https://escapefromtarkov.fandom.com/wiki/Tour","requires":[],"wip":False,
    "objectives":[
        {"id":"story-o","type":"main","description":"Inspect the location","maps":["The Lab"],"points":[{"map":"The Lab","floor":0,"kind":"pin","pts":[{"x":-131.08,"z":-273.23},{"x":-130.0,"z":-272.0}]}]},
        {"id":"story-area","type":"main","description":"Search the area","maps":["Interchange"],"needs":"Secure Flash drive","points":[{"map":"Interchange","floor":0,"kind":"area","pts":[{"x":92.12,"z":-304.63},{"x":46.63,"z":-304.63},{"x":47.22,"z":-284.19},{"x":92.71,"z":-283.60},{"x":92.12,"z":-304.63}]}]}
    ]
}]}}
story=tm._normalize_story_chapters(story_raw)
assert len(story)==1 and story[0]['id']=='story:story-game-id' and story[0]['trader']=='Story', 'story chapter normalisatie faalt'
assert len(story[0]['objectives'][0]['locations'])==2 and all(x['level']==0 for x in story[0]['objectives'][0]['locations']), 'story pins/floor ontbreken'
area=story[0]['objectives'][1]['locations']
assert len(area)==1 and len(area[0]['outline'])==5 and area[0]['level']==0, 'story-area wordt niet als een zone met centroid genormaliseerd'
assert story[0]['objectives'][1]['requirements'][0]['name']=='Secure Flash drive', 'storyline itemvereiste ontbreekt'
assert any(r['name']=='Secure Flash drive' for r in story[0]['requirements']), 'storyline itemvereiste bereikt de quest-tracker niet'

stats=tm._quest_spot_stats(merged+story)
assert stats['spots']==5 and stats['mappedObjectives']==3 and stats['mappedQuests']==2, 'questspot-statistiek is onjuist'

print('OK - overlay, multi-position questspots, current/legacy merge, pin-correcties en story pins/zones gecontroleerd.')

# End-to-end refresh regression with the real refresh pipeline, but deterministic
# in-memory network documents. This verifies cache writing, source composition and
# the final catalog consumed by /api/quests without needing internet in CI.
orig_http=tm._http_json
orig_cache=tm.QUEST_CACHE
orig_catalog=tm.quest_catalog
orig_index=tm.quest_index
qa_cache=ROOT/'_qa_quests_cache.json'
try:
    tm.QUEST_CACHE=qa_cache
    tasks=[]; objective_rows=[]
    for i in range(100):
        tid=f'e2e-q-{i}'; oid=f'e2e-o-{i}'
        tasks.append({'id':tid,'name':f'E2E Quest {i}','map':'map-woods','objectives':[{'id':oid,'type':'visit','description':f'Visit E2E spot {i} on Woods'}]})
        positions=[{'x':float(i),'y':0.0,'z':float(i+10)}]
        if i==0: positions.append({'x':0.5,'y':0.0,'z':10.5})
        objective_rows.append({'id':tid,'objectiveMaps':['Woods'],'objectives':[{'id':oid,'type':'visit','description':f'Visit E2E spot {i} on Woods','maps':['Woods'],'possibleLocations':[{'map':'Woods','positions':positions}]}]})
    docs_by_marker={
        '/regular/tasks_en':{}, '/regular/items_en':{}, '/regular/maps_en':{}, '/regular/traders_en':{},
        '/regular/tasks':{'data':{'tasks':tasks}}, '/regular/items':{'data':{'items':[]}},
        '/regular/maps':{'data':{'maps':[{'id':'map-woods','name':'Woods','normalizedName':'woods'}]}},
        '/regular/traders':{'data':{'traders':[]}},
        'overlay.json':{},
        '/api/quests/objectives.json':{'quests':objective_rows},
        '/api/maps.json':{'corrections':{'objectives':{'Woods|e2e-o-1|1|11':{'x':1.25,'z':11.25}},'objectiveFloors':{},'hidden':{}},'story':{'chapters':[{
            'id':'e2e-story','questId':'e2e-story-game','name':'E2E Story','order':1,'wikiLink':'https://escapefromtarkov.fandom.com/wiki/Tour','requires':[],'wip':False,
            'objectives':[{'id':'e2e-story-o','type':'main','description':'Story point','maps':['Woods'],'points':[{'map':'Woods','floor':0,'pts':[{'x':50.0,'z':50.0}]}]}]
        }]}}
    }
    def fake_http(url, timeout=12.0):
        # Most-specific markers first because *_en paths contain the base name.
        for marker in ('/regular/tasks_en','/regular/items_en','/regular/maps_en','/regular/traders_en','/api/quests/objectives.json','/api/maps.json','overlay.json','/regular/tasks','/regular/items','/regular/maps','/regular/traders'):
            if marker in url: return docs_by_marker[marker]
        raise RuntimeError('unexpected QA URL '+url)
    tm._http_json=fake_http
    tm.quest_catalog=[]; tm.quest_index={}
    tm.refresh_quest_data()
    assert len(tm.quest_catalog)==101, 'end-to-end refresh levert niet 100 trader quests + 1 story chapter'
    e2e0=next(q for q in tm.quest_catalog if q['id']=='e2e-q-0')
    assert len(e2e0['objectives'][0]['locations'])==2, 'end-to-end refresh verliest possibleLocations alternatieven'
    e2e1=next(q for q in tm.quest_catalog if q['id']=='e2e-q-1')
    assert abs(e2e1['objectives'][0]['locations'][0]['x']-1.25)<1e-6, 'end-to-end mapcorrectie niet toegepast'
    storyq=next(q for q in tm.quest_catalog if q['id']=='story:e2e-story-game')
    assert storyq['objectives'][0]['locations'][0]['level']==0, 'end-to-end story floor 0 verloren'
    payload=json.loads(qa_cache.read_text(encoding='utf-8'))
    assert payload['stats']['spots']==102 and payload['storyCount']==1, 'end-to-end cache-statistiek klopt niet'
    assert payload['positionCorrections']['moved']==1, 'end-to-end correctieteller ontbreekt'
    assert 'current objective positions' in payload['source'] and 'story campaign pins' in payload['source'], 'end-to-end bronmetadata incompleet'
finally:
    tm._http_json=orig_http
    tm.QUEST_CACHE=orig_cache
    tm.quest_catalog=orig_catalog
    tm.quest_index=orig_index
    try: qa_cache.unlink()
    except FileNotFoundError: pass

print('OK - volledige quest refresh -> merge -> correctie -> story -> cache pipeline gecontroleerd.')
