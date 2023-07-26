DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS projects;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    public BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (author_id) REFERENCES users (id)
);

create table projects (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    name TEXT NOT NULL,
    startdate TIMESTAMP,
    enddate TIMESTAMP,
    brief TEXT,
    content TEXT NOT NULL,
    public BOOLEAN NOT NULL DEFAULT FALSE,
    pinned BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (author_id) REFERENCES users (id)
);
