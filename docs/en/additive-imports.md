# Additive imports: server core

Character imports add new names only. Duplicate names are skipped; edit existing cards on Characters. IDs, descriptions and availability markers are preserved.

Scene duplicates use the explicit author number: “Сцена 2. Зустріч” and “Сцена 2: Друзі” match. Titles and list positions do not identify duplicates. Unnumbered sections are always new, including on repeated imports. New scenes are appended; the active plan retains its previous text and adds only new sections. Renumbering a manually saved plan updates its author number; an occupied number is rejected.

This core release provides APIs; the Writing form field and dated import-log UI follow separately. GET story adds source_files (name, UTC created_at) and active_sources. PUT settings accepts target_words with profile and expected_revision in one atomic save. Minimum: 5,000; recommended up to 15,000 words. Existing scene targets stay unchanged.

Multipart results contain files with imported, failed or not_processed status. A partial success returns200 and partial=true. Do not retry the whole batch automatically; unnumbered scenes would be added again. Initial format/UTF-8 validation rejects the whole batch before publication; a runtime failure stops subsequent files.

Database schema5 preserves previous active sources and exact original bytes. Make a cold backup before upgrade; downgrading requires a matching older data backup.
