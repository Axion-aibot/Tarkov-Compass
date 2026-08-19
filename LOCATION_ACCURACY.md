# Tarkov Compass · Live locatie nauwkeurigheid - v24.2

De tracker leest de echte Unity XYZ en kijkrichting uit de Tarkov screenshotbestandsnaam. De grootste resterende afwijking is daarom meestal niet de XYZ-meting zelf, maar de omzetting van wereldcoordinaten naar de pixels van de gebruikte RE3MR-kaart.

## Standaard nauwkeurige instellingen

- Capture: 0,5 seconde.
- Smoothing: 20%.
- Predictive tracking: aan, maar maximaal 0,35 seconde.
- Visueel snappen naar walkable gebied: uit.
- Spelerpijl: 72 px, apart instelbaar van POI/questpins.

## Een map exact kalibreren

1. Ga in raid naar een zeer herkenbaar punt waarvan je exact weet waar het op de kaart staat.
2. Sta kort stil en wacht tot de live XYZ net is bijgewerkt.
3. Open `Exacte kaartkalibratie` en zet `Kalibratiemodus` aan.
4. Klik op de kaart exact op de plek waar je werkelijk staat. De tracker koppelt die kaartpixel aan de laatste ruwe XYZ-meting.
5. Herhaal dit op 4-6 punten die zo ver mogelijk over de map verspreid liggen. Gebruik liever verschillende hoeken/gebieden dan punten op een rechte lijn.
6. Controleer de RMS-indicatie. `goed` betekent dat de punten onderling consistent zijn. Een sterke uitschieter wordt bij voldoende punten buiten de fit gehouden; `Laatste wissen` kan een fout punt direct verwijderen.

Met deze affine kalibratie worden schaal, rotatie, offset en kleine kaartvervorming tegelijk gecorrigeerd. De kalibratie wordt per map lokaal in de browser opgeslagen.

## Waarom de oude positie soms verschoof

V24.1 kon de spelerpin naar een 96x96 walkable raster verplaatsen en tot meer dan een seconde vooruit voorspellen. Bij bochten, stoppen of een onnauwkeurig walkable-masker kon dat zichtbaar meerdere meters naast de echte positie uitkomen. V24.2 gebruikt standaard de ruwe kaartprojectie en beperkt extrapolatie sterk.
