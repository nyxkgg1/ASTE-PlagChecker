# Golden Copy 011126 — Database Setup

This setup guide accompanies [`Golden Copy 011126.sql`](./Golden%20Copy%20011126.sql), a schema-only PostgreSQL backup generated from the database configured for this local application on 1 November 2026.

## What is included

The SQL file contains database objects such as tables, constraints, indexes, and extension declarations. It also contains the single Alembic revision marker (`b36a058b4481`) so future migrations recognize the restored schema. It does **not** contain users, scans, uploaded-document records, audit events, or other application data. It does not contain database roles, passwords, application secrets, uploaded files, or model weights.

## Requirements

- PostgreSQL 17 or a compatible supported PostgreSQL version
- The PostgreSQL `pgvector` server extension installed for that PostgreSQL instance
- The PostgreSQL `pgcrypto` extension (usually included with PostgreSQL contrib packages)
- The application backend dependencies from [`../requirements.txt`](../requirements.txt)

## Create an empty application database

Connect as a PostgreSQL administrator and create a role and an empty database. Replace the example password with a strong local secret; do not save it in this backup.

```sql
CREATE ROLE aste_app LOGIN PASSWORD 'replace-with-a-strong-local-password';
CREATE DATABASE aste_plagchecker OWNER aste_app;
```

Connect to the new database and enable the required extensions:

```sql
\connect aste_plagchecker
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
```

## Restore the schema

From the repository root, restore the schema into the empty database:

```sh
psql --set=ON_ERROR_STOP=on \
  --host=localhost \
  --username=aste_app \
  --dbname=aste_plagchecker \
  --file="backend/Golden Copy/Golden Copy 011126.sql"
```

`psql` will prompt for the database password unless configured with a protected local `.pgpass` file or another secure credential method. Do not put a real password directly in shell history.

## Configure and run the application

Set `DATABASE_URL` in the private `backend/.env` file to point at the restored database. Generate fresh application secrets as described in the root [`README.md`](../../README.md), then install backend requirements and start the application using that README's setup instructions.

The SQL file is a structural snapshot, not an application-data restore. For a database initialized from migrations instead, follow the root README's PostgreSQL and Alembic setup steps.
