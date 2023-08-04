# Alembic Database Migrations

A single-database configuration with an async dbapi.

## Developer Notes

### Manual Migrations

    alembic revision -m "commit msg here"

### Auto Migrations

    alembic revision --autogenerate -m "commit msg here"

### Applying Migrations

    alembic upgrade head
