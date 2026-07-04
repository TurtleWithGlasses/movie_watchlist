# Movie Watchlist — Roadmap & Changelog

## v1.9.4 (current)
- Auto-sort new/edited/imported entries into the active sort order immediately after insertion

## v1.9.3
- Added IMDb Rating column — fetched from OMDb API on add/edit
- DB schema migrated automatically for existing installations

## v1.9.2
- Added Episodes column for TV series — fetched via TVMaze API (fallback: IMDb JSON-LD scrape)
- DB schema migrated automatically for existing installations

## v1.9.1
- Fixed blue cell highlight appearing on hover/focus/scroll (Qt stylesheet + delegate fix)
- Rebuilt installer from scratch to resolve broken in-app updater on older versions

## v1.9.0
- Hide Update/Skip buttons once download starts; restore them on error
- Fix Qt platform plugin crash on relaunch after in-place update

## v1.7.0
- In-process rename-swap updater (replaces external bat/ps1 scripts)

---

## Planned / Ideas
- Bulk refresh ratings & episodes for existing entries (re-fetch all without re-adding)
- "Refresh" context-menu action on a selected row to re-fetch its data
