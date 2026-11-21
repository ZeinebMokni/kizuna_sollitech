-- Runs once, when the database volume is first created.
-- Extensions are (re)declared idempotently in Alembic migrations too.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Separate database for the automated test suite.
CREATE DATABASE qatra_test;
\connect qatra_test
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
