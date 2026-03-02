-- SQLite does not support DROP COLUMN; recreate table instead
CREATE TABLE users_backup (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
INSERT INTO users_backup SELECT id, name FROM users;
DROP TABLE users;
ALTER TABLE users_backup RENAME TO users;
