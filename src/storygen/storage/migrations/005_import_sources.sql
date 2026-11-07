CREATE TABLE active_sources(story_id TEXT NOT NULL REFERENCES stories(id), kind TEXT NOT NULL CHECK(kind IN ('source_plan','source_characters')), version_id TEXT NOT NULL REFERENCES versions(id), PRIMARY KEY(story_id,kind));
INSERT INTO active_sources(story_id,kind,version_id)
SELECT s.story_id,json_extract(s.payload,'$.kind'),json_extract(s.payload,'$.version_id') FROM source_files s
WHERE s.rowid=(SELECT MAX(t.rowid) FROM source_files t WHERE t.story_id=s.story_id AND json_extract(t.payload,'$.kind')=json_extract(s.payload,'$.kind'));
