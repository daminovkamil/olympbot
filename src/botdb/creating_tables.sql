CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL ,
    activity_id INTEGER NOT NULL ,
    name        TEXT NOT NULL ,
    first_date  DATE,
    second_date DATE
);

CREATE TABLE IF NOT EXISTS event_scheduler (
    id          INTEGER PRIMARY KEY,
    date        DATE NOT NULL,
    event_id    INTEGER NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS last_post (
    post_id     INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS pages (
    url     VARCHAR(256) PRIMARY KEY,
    html    TEXT NOT NULL,
    loaded  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
