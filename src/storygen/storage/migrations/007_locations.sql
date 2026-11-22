CREATE TABLE story_locations(id TEXT PRIMARY KEY, story_id TEXT NOT NULL REFERENCES stories(id), payload TEXT NOT NULL);
CREATE INDEX story_locations_story ON story_locations(story_id);
CREATE TABLE location_dismissals(story_id TEXT NOT NULL REFERENCES stories(id), a TEXT NOT NULL, b TEXT NOT NULL, PRIMARY KEY(story_id,a,b));
