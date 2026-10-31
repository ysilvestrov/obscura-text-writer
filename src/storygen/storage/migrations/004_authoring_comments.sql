CREATE TABLE authoring_comment_sets(
 id TEXT PRIMARY KEY,
 story_id TEXT NOT NULL REFERENCES stories(id),
 scene_id TEXT NOT NULL REFERENCES scenes(id),
 material_kind TEXT NOT NULL CHECK(material_kind='draft'),
 revision INTEGER NOT NULL CHECK(revision>0),
 source_version_id TEXT NOT NULL REFERENCES versions(id),
 payload TEXT NOT NULL,
 UNIQUE(scene_id,material_kind,revision)
);
CREATE TRIGGER authoring_comment_sets_no_update BEFORE UPDATE ON authoring_comment_sets
 BEGIN SELECT RAISE(ABORT,'authoring comments are append-only'); END;
CREATE TRIGGER authoring_comment_sets_no_delete BEFORE DELETE ON authoring_comment_sets
 BEGIN SELECT RAISE(ABORT,'authoring comments are append-only'); END;
