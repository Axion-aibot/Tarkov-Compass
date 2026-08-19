# Tarkov Compass v24.6

v24.6 builds on the quest spot, live position, extraction pin, and media/Smart Route features introduced in v24.1–v24.4. This version adds a local **Account Progression Planner**: PMC level and faction, completed quests, prerequisite chains, future unlocks, raid kit aggregation, and an automatically suggested best next raid.

## Getting Started

1. Extract the entire ZIP into a new folder.
2. In Tarkov, bind `Settings -> Controls -> Screenshot` to `F9`.
3. Launch `START_TARKOV_COMPASS.bat` (the existing `START_TRACKER.bat` remains available as a compatibility launcher).
4. Use Tarkov Compass only for OFFLINE / Practice raids.

## What’s New in v24.6

### Account Progression Planner

Under **Account Progression**, you can set your PMC level and faction (USEC/BEAR). The planner stores locally which quests you explicitly mark as completed and classifies the relevant quest catalog as:

* **Available Now** — level and known quest prerequisites are met;
* **Almost Unlocked** — no more than one prerequisite or a small level increase is still required;
* **Blocked** — multiple prerequisites and/or a higher level are required;
* **Completed** — explicitly marked by you as completed for your account.

The planner builds a dependency graph from the current quest catalog. This allows it to track not only a quest’s direct prerequisite, but also the follow-up chain behind that quest. For each quest, it shows which prerequisites are still missing, how many direct unlocks completing it may provide, and the size of its known follow-up chain.

### Best Next Raid

The planner groups all currently available quests by supported map and provides a **Best Next Raid** recommendation. The score takes into account factors including:

* how many available quests can be combined on the same map;
* whether the quests have exact map locations;
* number of objectives;
* direct unlock impact;
* known future quest chains.

For the selected set, a raid kit is automatically assembled from the structured quest requirements. Keys are not unnecessarily added together, while consumable quest items/markers required by different quests are combined into total quantities. The interface also shows which quests may become immediately available after completing the selected set.

Using **Load … Raid Plan** sends the recommended quest set directly to the existing Raid Plan and then optimizes it using Smart Route. **Best on Current Map** limits the recommendation to the map you are currently viewing.

### Account Completion Integration

A quest can be marked as completed either from the progression list or from the active quest card. When the active quest is marked as account-complete, its local objective checkboxes are also marked as completed.

Progression status is independent of any live Tarkov account integration: the user decides when Tarkov has actually registered the quest as completed.

### Extraction Image Popup

The extraction pin improvement introduced in v24.4.1 remains active: clicking an extraction opens a separate large comparison popup, with the recognition image shown first and the exact RE3MR map location included as an additional slide.

## Media + Smart Navigation from v24.4

### Media for Extraction and Quest Pins

Every navigable pin includes an **Exact Map Location** in its detail window: a local crop of the included RE3MR map with a crosshair placed at exactly the same pin projection used on the map itself. This means that even a pin without an external screenshot always has a useful thumbnail.

The ZIP also includes local WebP recognition images for:

* all 17 current Streets of Tarkov extraction names;
* 20 recognizable Streets quest/objective locations;
* 12 Ground Zero quest/objective locations.

When a recognition image is available, it is displayed together with the exact map location in a carousel. Click the preview to open a large reference view. Hovering over a pin also displays a compact preview.

The images are **not loaded from the internet** at runtime. The bundled screenshots are stored under `web/assets/thumbs/`; mappings, search terms, and source references are stored in `web/data/pin_media.json`.

### Richer Pin and Quest Information

Where available, pin details show:

* extraction/POI type, conditions, and notes from live/local data;
* distance from the current XYZ position;
* recognition image + exact map location;
* location confidence, including score and source type;
* floor/indoor guidance and Y-axis height difference when this can be reliably derived from the data;
* aliases/alternative names;
* for quest pins: trader, minimum level, objective description, requirements, quest-chain prerequisites, XP/important reward items, and Kappa/Lightkeeper relevance.

### Pin Incorrect?

Every extraction and quest pin includes **Pin Incorrect?**.

* `Report Only`: writes the feedback locally to `pin_reports.json`.
* `Choose New Location`: then click the exact correct position on the map. The correction is immediately applied locally through `localStorage` and is also written to `pin_reports.json` as a review record.
* `Custom Data -> Clear Pin Corrections` removes all local corrections.

A manual map correction affects more than just the visual pin. Where possible, a corrected world position derived from the map transformation is also used for navigation and distance calculations.

### Alias Search

The global search function now also searches:

* extraction and community aliases;
* objective text and quest names;
* pin notes/faction/category;
* linked media keywords.

Example: `vent shaft` finds `Ventilation Shaft`.

### Smart Next Objective

Under **Nearby**, a smart recommendation for the next open quest objective is displayed. The score uses:

* actual straight-line distance from the current XYZ position;
* a penalty for objectives that are clearly on a different floor;
* a small penalty for lower positional confidence.

### Smart Route / Raid Plan

`Optimize Route` has been replaced by **Smart Route**:

* starts from your current position when available;
* first builds a nearest-neighbor ordering;
* then locally improves the route using a 2-opt step;
* displays segment distances and an estimated total straight-line distance;
* can optionally finish at the nearest known extraction from the final quest objective.

Extraction conditions remain important: the suggested final extraction is a geographical recommendation, not a guarantee that the extraction will be available to your PMC/Scav in that raid.

### Improved Selection/Highlighting

A selected pin receives a clearly visible focus ring/crosshair. Selected quest areas use their actual polygon/zone as a stronger highlight. DOM pins remain above the map layer, and selected pins remain visually dominant.

## Accuracy Improvements from v24.2/v24.3 Remain in Place

* player arrow defaults to 72 px, independent of POI/quest marker size;
* raw XYZ remains authoritative;
* walkable snap is disabled by default;
* prediction is limited to a maximum of 0.35 s;
* calibration uses fresh raw XYZ and only accepts points while you are nearly stationary;
* calibration RMS and outlier checks;
* Streets extracts use RE3MR-specific display anchors;
* extraction/transit pins are not hidden inside automatic clusters;
* bottom-center pin anchor + exact anchor point;
* live API extraction data takes priority over the local fallback.

## Quest Data

The existing quest pipeline remains intact:

* canonical task data;
* current objective positions;
* multiple possible locations per objective;
* overlay patches for existing objectives;
* map-side position corrections/hide/floor fixes;
* storyline pins and actual area polygons;
* legacy positional data only as a fallback for objectives that still have no location data;
* local caching after a successful online refresh.

See `QUEST_DATA.md` for details.

## Maps

All included RE3MR map images remain local. The main maps are Customs, Factory, Ground Zero, Icebreaker, Interchange, The Labyrinth, Lighthouse, Reserve, Shoreline, Streets of Tarkov, Terminal, and Woods. Additional detail/reference maps and the legacy The Lab map are also included.

## Media Source References

The quest/extraction structure and image-guide availability were checked against the Official Escape from Tarkov Wiki during this build. The bundled recognition screenshots introduced in v24.4 come from the current Wand / Team Wand Tarkov map checklists.

Source pages are listed for each media entry and included as credits in `web/data/pin_media.json`, with more extensive documentation in `MEDIA_AND_SMART_NAV.md`.

## Additional Technical Documentation

* `LOCATION_ACCURACY.md` — raw XYZ, prediction, and calibration.
* `PIN_ALIGNMENT.md` — extraction visual anchors and panel stacking.
* `QUEST_DATA.md` — quest merge/correction pipeline.
* `MEDIA_AND_SMART_NAV.md` — thumbnail fallback, media manifest, confidence, pin feedback, and Smart Route.
* `PROGRESSION_PLANNER.md` — account status, dependency graph, unlock scoring, and raid kit recommendations.
* `QA_REPORT.md` — completed regression and packaging tests.
