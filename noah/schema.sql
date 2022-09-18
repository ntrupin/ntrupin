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

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    name TEXT NOT NULL,
    startdate TIMESTAMP NOT NULL,
    enddate TIMESTAMP NOT NULL,
    link TEXT DEFAULT '.',
    about TEXT NOT NULL,
    langs TEXT[],
    deps TEXT[],
    platforms TEXT[],
    images TEXT[],
    public BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (author_id) REFERENCES users (id)
);