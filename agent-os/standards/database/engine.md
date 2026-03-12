# Database Engine: PostgreSQL

Always use **PostgreSQL** as the database engine.

## Rules

- Use PostgreSQL for all relational data storage needs
- Do not use MySQL, SQLite (except for tests if explicitly agreed), MariaDB, or other RDBMS
- Use PostgreSQL-specific features when beneficial (JSONB, arrays, CTEs, window functions, etc.)
- Use `psql` for CLI database interaction
- Connection strings should follow the format: `postgresql://user:password@host:port/dbname`

## Configuration

- Default port: `5432`
- Environment variable for connection: `DATABASE_URL`
- Use connection pooling for production (e.g., PgBouncer or built-in pool)

## Migrations

- Use a migration tool appropriate to your framework (e.g., Alembic for Python, Prisma/Drizzle for Node.js)
- All schema changes must go through migrations — no manual DDL in production

## Docker

When using Docker for local development:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
```
