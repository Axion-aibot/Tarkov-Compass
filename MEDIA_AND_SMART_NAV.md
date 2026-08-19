# Tarkov Compass · v24.4 Media & Smart Navigation

## 1. Universele thumbnailstrategie

De app gebruikt twee mediabronnen naast elkaar:

1. **Herkenningsbeeld** — een gebundelde lokale WebP-screenshot wanneer er een geschikte, actuele bronfoto is gekoppeld.
2. **Exacte kaartspot** — altijd beschikbaar voor een navigeerbare pin. Dit is geen vooraf gerenderd bestand; de UI cropt de lokale RE3MR-kaart rond exact dezelfde genormaliseerde pincoördinaat als de kaartrenderer gebruikt en tekent een crosshair in het midden.

Hierdoor kan een ontbrekende externe foto nooit betekenen dat de popup geen visuele locatiehulp heeft.

### Gebundelde recognition assets in deze build

- Streets of Tarkov: 17/17 extraction recognition images.
- Streets of Tarkov: 20 quest/location recognition images.
- Ground Zero: 12 quest/location recognition images.

De rest gebruikt minimaal de exacte RE3MR-kaartspot. Nieuwe recognition screenshots kunnen later uitsluitend via `web/data/pin_media.json` worden gekoppeld zonder de pinengine te wijzigen.

## 2. Media manifest

Bestand: `web/data/pin_media.json`.

Belangrijke secties:
- `exact`: vaste media per `map|category|canonical-name`;
- `questKeywords`: mapgebonden objective-keywords die een recognition screenshot koppelen;
- `aliases`: communitynamen/afkortingen voor search en matching;
- `credits`: bronpagina's en gebruik.

Media staat onder:
- `web/assets/thumbs/extracts/...`
- `web/assets/thumbs/quests/...`

## 3. Bronpagina's

Cross-check/reference:
- Official Escape from Tarkov Wiki — Quests / Image Guides
  `https://escapefromtarkov.fandom.com/wiki/Quests`
- Official Escape from Tarkov Wiki — Streets of Tarkov extraction table
  `https://escapefromtarkov.fandom.com/wiki/Streets_of_Tarkov`

Gebundelde recognition screenshots:
- Wand / Team Wand — Streets extraction points
  `https://wand.com/maps/escape-from-tarkov/streets-of-tarkov/checklist/place-of-interests/extraction-point`
- Wand / Team Wand — Streets quest items/locations
  `https://wand.com/maps/escape-from-tarkov/streets-of-tarkov/checklist/quests-and-activities/quest-items`
- Wand / Team Wand — Ground Zero quest items/locations
  `https://wand.com/maps/escape-from-tarkov/ground-zero/checklist/quest-and-activities/quest-items`

Runtime hoeft deze sites niet te bereiken; screenshots zijn lokaal gebundeld.

## 4. Position confidence

De detailpopup toont een praktische positionele score. Dit is geen statistische kans dat de wiki 'waar' is; het is een indicatie van de gebruikte positioneringslaag:

- 100% — visuele RE3MR display-anchor;
- 98% — lokaal door de gebruiker gecorrigeerd kaartpunt;
- 93% — gestructureerde questzone/polygon;
- 86% — gestructureerde wereldcoördinaat;
- 78% — alleen een kaartcoördinaat;
- 58% — bekende `worldApproximate` fallback.

Zo is meteen zichtbaar of een afstand exact uit XYZ komt of vooral bedoeld is als visuele kaartreferentie.

## 5. Floor / indoor guidance

Wanneer `level/floor` of een betrouwbare target-Y bekend is, toont de popup die informatie. Als de objective duidelijk indoor-context bevat maar de bron geen aparte verdieping heeft, zegt de UI expliciet dat de verdieping niet gestructureerd bekend is en verwijst hij naar het herkenningsbeeld + de kaartspot. Er worden geen trappen/ingangen verzonnen zonder brondata.

## 6. Pinfeedback en lokale correctie

Backendendpoint:
- `POST /api/pin-report`
- `GET /api/pin-reports` (lokale review/diagnose)

Bestand:
- `pin_reports.json`

Een gekozen nieuwe plek wordt per pin/map/mapstijl opgeslagen in browser-localStorage (`eft-v244-pin-corrections`). De displayprojectie controleert deze laag vóór fixed anchors/world projection. De inverse kaarttransformatie wordt ook opgeslagen als gecorrigeerde x/z zodat afstand/navigatie de correctie waar mogelijk kunnen gebruiken.

## 7. Smart Route

De planner gebruikt een lichte offline optimalisatie zonder cloudservice:

1. open raid-plan objectives op de huidige map verzamelen;
2. greedily vanaf huidige positie het dichtstbijzijnde volgende doel kiezen;
3. maximaal vijf 2-opt verbeterpasses;
4. totale directe segmentafstand tonen;
5. optioneel het geografisch dichtstbijzijnde bekende extract na het laatste doel voorstellen.

Het extractadvies houdt niet automatisch rekening met alle raid-specifieke beschikbaarheidsvoorwaarden. De popup/live extractdata blijft daarvoor leidend.
