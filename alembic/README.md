# Database Migrations

This directory contains Alembic database migrations for the Universal Insurance AI Agent.

## Quick Commands

```bash
# Create a new migration (auto-detect changes)
alembic revision --autogenerate -m "description of changes"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback all migrations
alembic downgrade base

# Show current migration version
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic history --indicate-current
```

## Using the Helper Script

A helper script is provided for common operations:

```bash
# Create new migration
./scripts/db.sh migrate "add user roles"

# Apply migrations
./scripts/db.sh upgrade

# Rollback last migration
./scripts/db.sh downgrade

# Show status
./scripts/db.sh status

# Reset database (DANGEROUS)
./scripts/db.sh reset
```

## Migration Best Practices

1. **Always review auto-generated migrations** before applying them
2. **Test migrations** on a copy of production data before deploying
3. **Keep migrations small** and focused on one change
4. **Include both upgrade and downgrade** functions
5. **Use meaningful names** for your migration descriptions

## Directory Structure

```
alembic/
├── env.py              # Migration environment configuration
├── script.py.mako      # Template for new migrations
├── README.md           # This file
└── versions/           # Individual migration scripts
    ├── 001_initial_schema.py
    └── ...
```

## Environment Variables

- `DATABASE_URL`: Database connection string (overrides alembic.ini)

## Troubleshooting

### Migration conflicts
If you get migration conflicts after merging branches:
```bash
alembic merge heads -m "merge branch migrations"
```

### Reset migrations (development only)
```bash
rm -rf alembic/versions/*.py
alembic revision --autogenerate -m "initial schema"
```

