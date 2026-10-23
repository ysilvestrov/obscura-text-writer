CREATE TABLE publication_signatures(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, archived_at TEXT, payload TEXT NOT NULL);
CREATE TABLE story_publications(story_id TEXT PRIMARY KEY REFERENCES stories(id), revision INTEGER NOT NULL, payload TEXT NOT NULL);
CREATE TABLE publication_assets(id TEXT PRIMARY KEY, story_id TEXT NOT NULL REFERENCES stories(id), sha256 TEXT NOT NULL, relative_path TEXT UNIQUE NOT NULL, mime_type TEXT NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL, payload TEXT NOT NULL);
