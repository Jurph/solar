# Migration Management Best Practices

## The Problem

Django migrations accumulate over time. Every schema change (rename field, add field, etc.) creates a new migration file. This can lead to:
- Hundreds of migration files
- Slow migration runs
- Hard to understand history
- Maintenance burden

## Solutions

### 1. **Squash Migrations Periodically** (Recommended)

Django provides `squashmigrations` to consolidate multiple migrations into one:

```bash
python manage.py squashmigrations universe 0001 0012
```

This creates a new "squashed" migration that combines all operations from 0001 to 0012, while keeping the original migrations for backward compatibility.

**When to squash:**
- After major refactoring sessions
- Before deploying to production
- When you have 10-20+ migrations in an app
- Before a release milestone

**Benefits:**
- Faster migration runs (one operation instead of 20)
- Cleaner history
- Still maintains backward compatibility

### 2. **Reset Migrations in Development** (Development Only!)

If you're still in active development and haven't deployed to production yet:

```bash
# 1. Delete all migration files except __init__.py
# 2. Delete migration records from database
python manage.py migrate universe zero
# 3. Create fresh initial migration
python manage.py makemigrations universe
# 4. Apply it
python manage.py migrate
```

**⚠️ WARNING:** Only do this if:
- You haven't deployed to production
- You're okay losing migration history
- All developers can reset their databases

### 3. **Combine Related Changes**

When making multiple related changes, do them all at once before running `makemigrations`:

```python
# Instead of:
# 1. Rename field → migration
# 2. Add field → migration  
# 3. Remove field → migration

# Do:
# 1. Rename field
# 2. Add field
# 3. Remove field
# 4. Run makemigrations once → single migration
```

### 4. **Use Data Migrations Sparingly**

Data migrations (changing data, not schema) should be separate from schema migrations:

```python
# Good: Separate data migration
class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(migrate_data, reverse_code=reverse_migrate_data),
    ]
```

### 5. **Review Before Committing**

Before committing migrations:
- Review the generated migration file
- Ensure it's doing what you expect
- Check for unnecessary operations
- Consider if it can be combined with upcoming changes

## Recommended Workflow

### During Active Development:
1. Make schema changes
2. Run `makemigrations` frequently (every few changes)
3. Test migrations work (`migrate` and `migrate --fake-initial`)
4. **Before major milestones**: Squash migrations

### Before Production Deployment:
1. Squash all migrations to date
2. Test the squashed migration on a copy of production data
3. Review the final migration file
4. Deploy

### After Production Deployment:
- **Never delete migrations** that have been run in production
- **Never edit existing migrations** that have been run
- Only add new migrations going forward
- Squash periodically, but keep originals

## Example: Squashing Workflow

```bash
# Current state: 20 migration files (0001 through 0020)

# 1. Squash migrations 0001-0020
python manage.py squashmigrations universe 0001 0020

# This creates:
# - 0001_squashed_0020_*.py (the squashed migration)
# - Original migrations remain (for backward compatibility)

# 2. Test the squashed migration
python manage.py migrate universe --fake-initial

# 3. If working, you can optionally remove old migrations
# (But keep them if they've been run in production!)

# 4. Going forward, new migrations start from the squashed one
python manage.py makemigrations universe  # Creates 0021_*.py
```

## When NOT to Squash

- **Don't squash** if migrations have been run in production and you can't guarantee all environments have the same migration state
- **Don't squash** if you're unsure about the migration history
- **Don't squash** right before a deployment (do it well in advance for testing)

## Summary

- **During development**: Make changes, create migrations, squash periodically
- **Before production**: Always squash and test
- **After production**: Never delete/edit existing migrations, only add new ones
- **Best practice**: Squash every 10-20 migrations or before major releases

The key is: **Squash early, squash often, but never break production!**

