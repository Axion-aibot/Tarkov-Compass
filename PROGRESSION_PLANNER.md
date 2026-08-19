# Tarkov Compass v24.6 · Account Progression Planner

## Doel

De planner maakt van questtracking een accountbrede beslislaag: welke quest is nu speelbaar, welke prerequisite ontbreekt, welke map combineert de meeste progressie en welke items/keys moeten mee.

## Lokale accountstatus

- PMC-level: `eft-v246-player-level` in browser localStorage.
- Faction: `eft-v246-faction` (`USEC`, `BEAR` of leeg voor onbekend/alle).
- Voltooide quests: `eft-v246-completed-quests`.
- Bestaande objective-vinkjes blijven in `eft-mvp-quest-progress-<questId>`.

Er is geen Tarkov-accountlogin nodig of ingebouwd. De gebruiker markeert een quest pas account-complete wanneer Tarkov hem werkelijk als voltooid toont.

## Dependency graph

`/api/quests` publiceert vanaf v24.6 naast de bestaande catalogusvelden ook compacte `prerequisites`, `requirements`, `experience`, `faction` en `story` metadata. Volledige objectives/locaties blijven via `/api/quest?id=...` lopen.

De browser bouwt een reverse dependency graph: prerequisite quest -> quests die ervan afhangen. Daarmee worden directe unlocks en bekende downstream questketens berekend.

## Statusregels

- `completed`: handmatig account-complete.
- `ready`: minimumlevel gehaald en alle bekende prerequisite quest IDs completed.
- `near`: maximaal 1 prerequisite ontbreekt met een kleine level-gap, of alleen een beperkte level-gap.
- `blocked`: overige gevallen.

Quest requirements met bijzondere statusvormen blijven zichtbaar in de brondata; de planner gebruikt quest-completion conservatief als veilige dependency-basis.

## Beste volgende raid

Alle `ready` quests worden per ondersteunde hoofdmap gegroepeerd. De score beloont: kaartspots, objective-dichtheid, directe unlocks en downstream progression. Maximaal zes quests worden in een aanbevolen raidset gezet.

De raid-kit wordt uit de compacte questrequirements samengevoegd. Voor keys/keycards wordt de hoogste benodigde hoeveelheid gebruikt; verbruikbare items uit verschillende quests worden bij elkaar opgeteld.

De knop **Laad raid plan** gebruikt de bestaande `saveRaidPlanIds`, haalt volledige questdetails op en laat Smart Route daarna de objectivevolgorde optimaliseren.

## Faction

Als USEC of BEAR is geselecteerd, worden quests die expliciet aan de andere faction zijn gekoppeld buiten de stats, recommendations en progression-lijst gehouden. Quests zonder faction worden voor beide behouden.
