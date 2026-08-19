# Tarkov Compass v24.6

v24.6 bouwt verder op de quest-spot, live-position, extraction-pin en media/Smart Route functies uit v24.1-v24.4. Deze versie voegt een lokale **Account Progression Planner** toe: PMC-level en faction, voltooide quests, prerequisite-ketens, toekomstige unlocks, raid-kit aggregatie en een automatisch voorgestelde beste volgende raid.

## Start

1. Pak de volledige ZIP uit in een nieuwe map.
2. Bind in Tarkov `Settings -> Controls -> Screenshot` aan `F9`.
3. Start `START_TARKOV_COMPASS.bat` (de bestaande `START_TRACKER.bat` blijft als compatibiliteitslauncher aanwezig).
4. Gebruik Tarkov Compass alleen voor OFFLINE / Practice raids.

## Wat is nieuw in v24.6

### Account Progression Planner

Onder **Account Progressie** kun je je PMC-level en faction (USEC/BEAR) instellen. De planner bewaart lokaal welke quests je daadwerkelijk als voltooid markeert en classificeert de relevante catalogus als:
- **Nu beschikbaar** — level en bekende quest-prerequisites zijn voldaan;
- **Bijna unlocked** — nog maximaal een prerequisite of een kleine levelstap;
- **Geblokkeerd** — meerdere prerequisites en/of hoger level nodig;
- **Voltooid** — expliciet door jou als account-complete gemarkeerd.

De planner bouwt een dependency graph uit de actuele questcatalogus. Daardoor ziet hij niet alleen de directe prerequisite, maar ook de vervolgketen achter een quest. Per quest toont hij welke prerequisite nog mist, hoeveel directe unlocks voltooiing kan opleveren en hoe groot de bekende vervolglijn is.

### Beste volgende raid

De planner groepeert alle momenteel beschikbare quests per ondersteunde map en geeft een **Beste volgende raid**. De score gebruikt onder andere:
- hoeveel beschikbare quests op dezelfde map gecombineerd kunnen worden;
- of de quests exacte kaartspots hebben;
- aantal objectives;
- directe unlock-impact;
- bekende toekomstige questketen.

Voor de gekozen set wordt automatisch een raid-kit samengesteld uit de gestructureerde quest requirements. Keys worden niet onnodig opgeteld; verbruikbare questitems/markers uit verschillende quests worden wel bij elkaar opgeteld. De kaart toont ook welke quests na deze set direct beschikbaar kunnen worden.

Met **Laad … raid plan** wordt de aanbevolen questset direct naar het bestaande Raid Plan gestuurd en daarna door Smart Route geoptimaliseerd. **Beste op huidige map** beperkt de aanbeveling tot de map die je nu bekijkt.

### Account-complete koppeling

Een quest kan vanuit de progression-lijst of vanuit de actieve questkaart als voltooid worden gemarkeerd. Als de actieve quest account-complete wordt gezet, worden de lokale objective-vinkjes eveneens afgerond. De progression-status staat los van een live Tarkov-accountkoppeling: de gebruiker bepaalt zelf wanneer Tarkov de quest echt als voltooid heeft geregistreerd.

### Extraction image popup

De extraction-pin verbetering uit v24.4.1 blijft actief: klikken op een extraction opent een aparte grote vergelijk-popup met het herkenningsbeeld vooraan en de exacte RE3MR-kaartspot als extra slide.

## Media + Smart Navigation uit v24.4

### Media bij extraction- en questpins

Iedere navigeerbare pin heeft in zijn detailvenster een **Exacte kaartspot**: een lokale uitsnede van de meegeleverde RE3MR-kaart met een crosshair exact op dezelfde pinprojectie als de kaart zelf. Daardoor heeft ook een pin waarvoor geen externe screenshot beschikbaar is altijd een bruikbare thumbnail.

Daarnaast bevat de ZIP lokale WebP-herkenningsbeelden voor:
- alle 17 huidige Streets of Tarkov extractionnamen;
- 20 herkenbare Streets quest-/objective-locaties;
- 12 Ground Zero quest-/objective-locaties.

Wanneer een herkenningsbeeld beschikbaar is, wordt het samen met de exacte kaartspot als carousel getoond. Klik op de preview voor een grote referentieweergave. Hover op een pin toont eveneens een compacte preview.

De afbeeldingen worden tijdens runtime **niet van internet geladen**. De gebundelde screenshots staan onder `web/assets/thumbs/`; de koppelingen, zoektermen en bronverwijzingen staan in `web/data/pin_media.json`.

### Rijkere pin- en questinformatie

Pin-details tonen waar beschikbaar:
- extraction/POI-type, voorwaarden en opmerkingen uit de live/lokale data;
- afstand vanaf de huidige XYZ;
- herkenningsbeeld + exacte kaartspot;
- location-confidence met score en bronsoort;
- floor/indoor guidance en Y-hoogteverschil wanneer dat betrouwbaar uit de data kan worden afgeleid;
- aliases/alternatieve namen;
- bij questpins: trader, minimumlevel, objective-uitleg, requirements, quest-chain prerequisites, XP/belangrijke reward-items en Kappa/Lightkeeper-relevantie.

### Pin klopt niet?

Elke extraction- en questpin heeft **Pin klopt niet?**.

- `Alleen melden`: schrijft de feedback lokaal naar `pin_reports.json`.
- `Nieuwe plek kiezen`: klik daarna exact op de juiste kaartpositie. De correctie wordt direct lokaal toegepast via `localStorage` en eveneens als review-record naar `pin_reports.json` geschreven.
- `Eigen data -> Pin-correcties wissen` verwijdert alle lokale correcties.

Een handmatige kaartcorrectie beïnvloedt niet alleen de visuele pin; waar mogelijk wordt ook een gecorrigeerde wereldpositie uit de kaarttransformatie gebruikt voor navigatie/afstand.

### Alias search

De globale zoekfunctie zoekt nu ook in:
- extract- en community-aliases;
- objective-tekst en questnaam;
- pin notes/faction/category;
- gekoppelde media-keywords.

Voorbeeld: `vent shaft` vindt `Ventilation Shaft`.

### Smart volgende doel

Onder **Dichtbij** verschijnt een slim volgende open questdoel. De score gebruikt:
- werkelijke rechtstreekse afstand vanaf de huidige XYZ;
- een penalty voor een duidelijk andere verdieping;
- een kleine penalty voor lagere positionele zekerheid.

### Smart Route / Raid Plan

`Optimaliseer route` is vervangen door **Smart Route**:
- start bij je actuele positie wanneer beschikbaar;
- bouwt eerst een nearest-neighbour volgorde;
- verbetert de route vervolgens lokaal met een 2-opt stap;
- toont segmentafstanden en een totale directe afstandsschatting;
- kan optioneel eindigen bij de dichtstbijzijnde bekende extraction vanaf het laatste questdoel.

Extractionvoorwaarden blijven belangrijk: het voorgestelde eindextract is een geografische aanbeveling, geen garantie dat die extract voor jouw PMC/Scav in die raid beschikbaar is.

### Betere selectie/highlight

Een geselecteerde pin krijgt een duidelijke focus-ring/crosshair. Geselecteerde questgebieden gebruiken hun echte polygon/zone als sterkere highlight. DOM-pins blijven boven de kaartlaag staan en geselecteerde pins blijven visueel dominant.

## Nauwkeurigheid uit v24.2/v24.3 blijft behouden

- spelerpijl standaard 72 px, los van POI/quest-markermaat;
- raw XYZ is leidend;
- walkable snap standaard uit;
- prediction maximaal 0,35 s;
- kalibratie gebruikt verse raw XYZ en accepteert alleen punten terwijl je vrijwel stilstaat;
- kalibratie-RMS en uitschietercontrole;
- Streets extracts gebruiken RE3MR-specifieke display-anchors;
- extraction/transitpins verdwijnen niet in automatische clusters;
- bottom-center pin-anchor + exact anchorpunt;
- live API extractdata heeft voorrang op de lokale fallback.

## Questdata

De bestaande questpipeline blijft intact:
- canonical taskdata;
- actuele objective-posities;
- meerdere mogelijke locaties per objective;
- overlay-patches op bestaande objectives;
- map-side position corrections/hide/floor fixes;
- storyline pins en echte area-polygons;
- legacy positional data alleen als fallback voor nog lege objectives;
- lokale cache na een succesvolle online refresh.

Zie `QUEST_DATA.md` voor details.

## Kaarten

Alle meegeleverde RE3MR-kaartafbeeldingen blijven lokaal. Hoofdkaarten zijn Customs, Factory, Ground Zero, Icebreaker, Interchange, The Labyrinth, Lighthouse, Reserve, Shoreline, Streets of Tarkov, Terminal en Woods. Er zijn daarnaast detail/reference maps en de legacy The Lab-kaart.

## Bronverwijzingen voor media

De quest-/extractstructuur en image-guide beschikbaarheid zijn tijdens deze build gecontroleerd tegen de Official Escape from Tarkov Wiki. De gebundelde herkenningsscreenshots in v24.4 komen uit de actuele Wand / Team Wand Tarkov-mapchecklists. Bronpagina's staan per media-entry en als credits in `web/data/pin_media.json` en uitgebreider in `MEDIA_AND_SMART_NAV.md`.

## Meer technische documentatie

- `LOCATION_ACCURACY.md` — raw XYZ, prediction en kalibratie.
- `PIN_ALIGNMENT.md` — extraction visual anchors en pane stacking.
- `QUEST_DATA.md` — quest merge/correction pipeline.
- `MEDIA_AND_SMART_NAV.md` — thumbnail fallback, media manifest, confidence, pinfeedback en Smart Route.
- `PROGRESSION_PLANNER.md` — accountstatus, dependency graph, unlock scoring en raid-kit aanbevelingen.
- `QA_REPORT.md` — uitgevoerde regressie- en verpakkingstests.
