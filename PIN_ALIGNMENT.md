# Tarkov Compass · v24.3 pin alignment

## Waarom de extract-pin kon verschuiven

De build had twee verschillende problemen die samen zichtbaar werden bij bijvoorbeeld **Ventilation Shaft** op Streets:

1. Streets voegde een lokale curated extractlijst samen met live POI-data. Als dezelfde extractnaam verschillende wereldcoördinaten had, bleven beide records bestaan omdat de dedupe ook de coördinaten meenam.
2. Een wereldcoördinaat wordt via de mapprojectie naar een afbeelding vertaald. Voor een pin die precies boven een reeds op de RE3MR-afbeelding getekend extracticoon moet staan, is een direct gemeten afbeeldingsanker betrouwbaarder dan een oude fallback-wereldcoördinaat.

## v24.3 model

Voor RE3MR Streets bestaan daarom twee soorten gegevens naast elkaar:

- **Live world coordinate**: gebruikt wanneer beschikbaar voor echte in-game afstandsdata.
- **Visual RE3MR anchor**: genormaliseerde afbeeldingscoördinaat van de punt van het extracticoon; gebruikt voor de positie van de pin op de kaart en voor het visuele route-eindpunt.

De visual anchors staan in `web/data/map_pin_anchors.json`. Ze gelden alleen voor de RE3MR-stijl. Andere kaartstijlen blijven de normale world-to-map projectie gebruiken.

## Bronprioriteit

Voor extraction/transit records is de volgorde:

1. actuele backend/API POI;
2. lokale curated fallback;
3. eventuele starter pin.

Records worden voor extracts/transits op genormaliseerde naam gededupliceerd. Hierdoor matchen onder andere `Klimov Street (Flare)` met `Klimov Street`, `Pinewood Basement (Co-Op)` met `Pinewood Basement`, en apostrofvarianten van Smugglers' Basement met elkaar.

## DOM anchor

De locatie van een DOM-pin is zijn **bottom-center**. De locatorvorm eindigt daar en een kleine stip markeert de exacte datacoördinaat. Hierdoor ontstaat geen vaste pixel-offset meer tussen de data en de zichtbare punt van de pin.

## Streets QA

Alle 17 extraction anchors zijn gecontroleerd op de meegeleverde `web/maps/reemr/streetsoftarkov.jpg`. Voor Ventilation Shaft is de vaste RE3MR anchor `nx=0.758381`, `ny=0.896132`. De oude lokale fallback projecteerde deze extract ongeveer naar `0.796236, 0.802768`, wat honderden bronbeeldpixels verschilde. De fallbackwereldpositie is daarom ook opnieuw uit de juiste RE3MR-kaartpositie afgeleid en als `worldApproximate` gemarkeerd; live API-worlddata blijft leidend zodra die beschikbaar is.
