# Movie Watchlist — Roadmap & Changelog

## v1.9.5 (current)
- Flag titles: new ⚑ column (first column); a single click on the cell toggles the flag. Saved in the db and in JSON export/import; click the ⚑ header to sort flagged titles first
- Button row moved above the table, directly below the entry row
- IMDb lookups run in a background thread — the window no longer freezes while fetching
- Fixed crash when editing an entry with a non-IMDb URL
- Manual row order (↑/↓) is now kept across restarts
- Fixed crash pressing ↓ with no row selected
- Database is stored next to the app instead of the launch folder (old db migrated automatically)
- Google Drive sync: only downloads when the Drive copy is newer, never truncates the local db on a failed download
- "Days Left" refreshes at midnight while the app is open; inline date edits re-sort the list
- Remove now asks for confirmation
- Removed the unused MovieManager class; fixed requirements.txt

## v1.9.4
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
