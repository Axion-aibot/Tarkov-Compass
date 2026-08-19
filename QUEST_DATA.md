# Tarkov Compass · Questdata en quest-spots in v24.2

Tarkov Compass houdt de browser volledig lokaal: de kaart en quest-tracking lezen alleen de lokale backend/API. De backend synchroniseert actuele questdata en schrijft daarna een persistente `quests_cache.json` in de uitgepakte map. Na een succesvolle sync blijft die laatste goede catalogus beschikbaar wanneer de pc later offline is.

## Synchronisatievolgorde

1. **Actuele questcatalogus:** `json.tarkov.dev` voor tasks/items/maps/traders.
2. **Community-correcties:** `tarkovtracker-org/tarkov-data-overlay`. Shared patches, mode-patches, locale-patches, `tasksAdd`, objective-patches en `objectivesAdd` worden nu allemaal verwerkt. Dit is belangrijk omdat extra `zones` op bestaande objectives anders verdwenen.
3. **Actuele positie-slice:** `szepiz/tarkov-quest-data/api/quests/objectives.json`. Deze levert gestructureerde `zones` en `possibleLocations.positions`, inclusief meerdere mogelijke spawnplekken voor één objective.
4. **In-game gecontroleerde mapcorrecties en storyline:** `szepiz/tarkov-quest-data/api/maps.json`. Bekend fout geplaatste objective-pins worden verplaatst, expliciet foutieve API-markers worden verborgen, floor-overrides worden toegepast en story-chapters met handmatig geplaatste punten worden toegevoegd als normale interactieve quests onder trader/filter **Story**.
5. **Noodfallback:** de gearchiveerde TarkovLab questdataset wordt alleen gebruikt als de actuele positie-slice niet beschikbaar is. Oude locaties mogen uitsluitend een nog volledig lege objective aanvullen en worden nooit naast een actuele locatie gezet.

## Wat verschijnt als pin?

Elke objective met een bekende wereldpositie (`x/z`) voor een lokaal ondersteunde map kan als interactieve quest-pin verschijnen. Als een objective meerdere geldige locaties heeft, blijven **alle** locaties behouden en krijg je dus meerdere navigeerbare pins. Objectives zonder fysieke locatie (bijvoorbeeld alleen een item inleveren, level halen of een trader spreken) krijgen bewust geen verzonnen kaartpin.

De frontend gebruikt dezelfde `objective.locations[]` voor:
- actieve quest-pins;
- multi-quest Raid Plan;
- kaarttabs per quest;
- "volgende open questlocatie";
- objective completion/progress;
- popup en navigatiedoel.

Floor `0` is een geldige verdieping en wordt nergens meer als "leeg" behandeld. Storyline-locaties die als een gebied/polygon zijn gepubliceerd, worden als één interactieve objective-spot weergegeven met een zichtbare zone-omtrek; de polygon-hoekpunten worden dus niet ten onrechte als losse quest-spots geteld. Storyline `needs`-vereisten worden meegenomen in de objective- en questvereisten.

## Wiki / verificatie

De Escape from Tarkov Wiki (`https://escapefromtarkov.fandom.com/wiki`) blijft een belangrijke inhoudelijke referentie. De actuele samengestelde bron die voor de extra questlaag wordt gebruikt vergelijkt tarkov.dev, de Wiki en tarkov-data-overlay en publiceert daarnaast handmatig in-game gecontroleerde kaartposities. Wiki-links per quest blijven in de questrecords beschikbaar wanneer de bron ze levert.

## Eerste start

De meegeleverde cache is bewust een lege bootstrap-cache: questdata verandert met patches en hoort bij de eerste online start actueel te worden opgehaald. De UI vraagt direct een refresh aan en de backend refresht daarna periodiek. Zodra één refresh succesvol is geweest, staat de volledige laatste goede catalogus lokaal in `quests_cache.json`.
