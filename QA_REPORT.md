# Tarkov Compass · v24.6 progression planner QA report

Build date: 2026-08-19

## v24.6 resultaat

Naast alle bestaande v24.1-v24.4 regressies zijn de accountprogressie, dependency graph, factionfilter, unlock-impact, raid recommendation en raid-kit aggregatie toegevoegd en getest.

### Nieuwe regressies

- `/api/quests` summary bevat compacte `prerequisites` en `requirements`;
- PMC-level en faction worden lokaal bewaard;
- account-complete queststatus is apart van tijdelijke objective-progress;
- ready / near / blocked / completed statusengine;
- reverse dependency graph en downstream questketen;
- directe unlock-impact na gesimuleerde quest completion;
- beste-map recommendation;
- automatische raid-kit aggregatie;
- aanbevolen questset kan direct naar het bestaande Raid Plan;
- tegenovergestelde faction wordt uit progression stats/recommendations gefilterd;
- actieve quest kan vanuit Quest Navigator account-complete worden gezet.

### Runtime browser-DOM test

Een echte headless Chromium DOM-test met een synthetische USEC questketen valideerde dat:
- `Customs` als beste volgende map werd gerenderd;
- de raid-kit `2x MS2000 Marker` bevatte;
- een BEAR-only quest niet in de USEC progression-lijst/recommendation verscheen;
- `Debut` als beschikbare quest verscheen;
- voltooiing van de eerste quest de volgende dependency correct unlockt.

### Bestaande functionaliteit

Alle eerdere extraction image popup, media, pin-alignment, questspots, raw-position tracking, calibration, Smart Next en Smart Route regressies blijven onderdeel van `self_test.py` en de JavaScript syntaxchecks.

---

Build date: 2026-08-19

## Resultaat

De volledige Python/self-test en JavaScript syntaxchecks zijn groen in de werkbuild. De lokale HTTP-handler is daarnaast als echte server gestart en heeft de nieuwe media-assets, JSON-manifest en pin-report endpoints succesvol geserveerd.

## Baseline / regressies uit v24.1-v24.3

Opnieuw gevalideerd:
- Python backend compileert;
- `web/app.js` en `web/v244.js` slagen voor `node --check`;
- alle lokale RE3MR-mapassets bestaan;
- DOM pin-engine, bottom-center anchors en pin stacking blijven aanwezig;
- Streets heeft 17 vaste RE3MR extraction display-anchors;
- Ventilation Shaft blijft regression-locked op `nx=0.758381`, `ny=0.896132`;
- live raw XYZ, 72 px spelerpijl, opt-in walkable snap, prediction max. 0,35 s en raw-position calibratie blijven intact;
- quest overlay patches op bestaande objectives blijven werken;
- `possibleLocations.positions` behoudt meerdere questspots;
- current/legacy position merge verliest geen alternatieve spots;
- floor `0` blijft behouden;
- hand-checked move/floor/hide corrections blijven actief;
- story pins en `kind: area` polygons blijven interactieve questlocaties;
- storyline `needs` blijft quest requirement;
- volledige deterministic refresh -> merge -> corrections -> story -> cache pipeline blijft groen.

## v24.4 media regressies

Gecontroleerd:
- `web/data/pin_media.json` heeft versie `24.4`;
- exact 17 Streets extract-media entries;
- minimaal 30 quest/location media keyword entries;
- alle in het manifest genoemde bestanden bestaan in de ZIP;
- 17 Streets extraction recognition WebP's;
- 20 Streets quest/location recognition WebP's;
- 12 Ground Zero quest/location recognition WebP's;
- iedere navigeerbare pin heeft in de UI een lokale **Exacte kaartspot** fallback gebaseerd op dezelfde `poiMapNormalized()` projectie als de pin zelf;
- recognition image + map crop vormen samen een carousel wanneer recognition media bestaat;
- grote media-lightbox bestaat en is gekoppeld aan de preview;
- hover-preview gebruikt recognition media of de mapspot fallback;
- image-backed DOM pins krijgen een media-indicator.

## v24.4 context / guidance

Gecontroleerd:
- extraction/POI detail ondersteunt condition/faction/note/aliases;
- quest drawer toont trader, minimumlevel, objective-uitleg en requirements;
- quest context kan prerequisites, XP/finish-reward items en Kappa/Lightkeeper metadata tonen;
- floor guidance gebruikt alleen gestructureerde `level/floor`, target-Y of expliciete indoor-context; er worden geen fictieve trappen/ingangen gegenereerd;
- location confidence onderscheidt visuele anchor, lokale correctie, zone, wereldcoördinaat, kaartcoördinaat en approximate fallback;
- geselecteerde questzones gebruiken hun echte polygon als highlight; andere geselecteerde pins krijgen een crosshair/halo.

## Pinfeedback / lokale correctie

Gecontroleerd:
- `POST /api/pin-report` slaat feedback lokaal op in `pin_reports.json`;
- `GET /api/pin-reports` kan de lokale reviewrecords teruglezen;
- payloadlengtes worden begrensd en het reportbestand blijft begrensd op de laatste 2000 records;
- `webp` en `json` hebben correcte HTTP content types;
- local correction key bevat map/pin/mapstijl;
- de override-laag wordt vóór de normale anchor/world-projectie gecontroleerd;
- een mapklik bewaart normalized `nx/ny` én inverse `x/z` voor afstand/navigatie;
- alle lokale correcties kunnen via de UI worden gewist.

De echte HTTP-smoketest heeft succesvol uitgevoerd:
- `GET /`
- `GET /v244.js`
- `GET /data/pin_media.json`
- `GET /assets/thumbs/extracts/streets/ventilation_shaft.webp` met `image/webp`
- `GET /api/state`
- `POST /api/pin-report`
- `GET /api/pin-reports`

Het QA-reportbestand is na deze test weer teruggezet naar de oorspronkelijke lege `pin_reports.json`, zodat de distributie geen testfeedback bevat.

## Search / Smart Navigation

Gecontroleerd:
- globale search gebruikt aliases, category/note/faction, objective/questtekst en media keywords;
- `vent shaft` kan `Ventilation Shaft` vinden;
- Smart Next gebruikt afstand + floor penalty + confidence penalty;
- Smart Route gebruikt nearest-neighbour gevolgd door maximaal vijf 2-opt verbeterpasses;
- routeoverzicht toont segmentafstanden en totale directe afstand;
- optionele eindextract-aanbeveling wordt bepaald vanaf het laatste geplande doel;
- eindextract wordt expliciet als geografische aanbeveling behandeld: raid-specifieke availability/requirements moeten nog steeds in de extractdata worden gecontroleerd;
- handmatig gecorrigeerde pins worden door target dropdown, popup navigation, search focus en Smart Route als gecorrigeerde target gebruikt.

## Browser runtime check

Chromium mag in deze buildomgeving door een organisatiebeleid niet naar `127.0.0.1` navigeren (`Your organization doesn't allow you to view this site`). Daarom kan de echte loopback-UI hier niet als normale browserpagina worden geopend.

Als aanvullende runtimecontrole is dezelfde `index.html + app.js + v244.js` via Chrome DevTools `Page.setDocumentContent` in `about:blank` uitgevoerd. Daarbij zijn daadwerkelijk gevalideerd:
- document title `v24.4`;
- v24.4 JavaScriptfuncties zijn geladen;
- report- en Smart UI bestaan in de DOM;
- geïnjecteerde productie-map/media data vindt Ventilation Shaft;
- Ventilation Shaft detail opent met 2 media-items (recognition image + exact mapspot);
- confidence toont `Visuele kaart-anchor`;
- alias search `vent shaft` retourneert Ventilation Shaft.

Een localStorage-correctie kan in die aanvullende opaque `about:blank` runtime niet worden getest omdat Chromium localStorage daar bewust blokkeert. De correction code wordt daarom statisch/regression-tested en de echte backend reportflow wordt via HTTP getest.

## Internet/source check tijdens de build

Tijdens deze build zijn actuele webpagina's gecontroleerd voor:
- Official Escape from Tarkov Wiki: quest image-guide structuur en Streets extractioninformatie;
- Wand / Team Wand: Ground Zero Quest Items checklist, Streets Quest Items checklist en Streets Extraction Points.

De herkenningsscreenshots zijn lokaal gebundeld zodat runtime geen externe netwerkverbinding nodig heeft. Zie `MEDIA_AND_SMART_NAV.md` en `web/data/pin_media.json` voor bronpagina's/credits.
