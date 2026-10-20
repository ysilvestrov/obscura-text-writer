UPDATE stories SET payload=json_set(payload,'$.trashed_at',NULL);
UPDATE scenes SET payload=json_set(payload,'$.trashed_at',NULL,'$.trashed_position',NULL);
