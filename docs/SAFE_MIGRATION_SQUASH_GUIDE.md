# Safe Migration Squashing Guide

## Overview

You have 12 migrations (0001 through 0012) and want to consolidate them safely without losing data or breaking anything.

## ✅ SAFE METHOD: Use `squashmigrations`

Django's `squashmigrations` command is the **safest** way to consolidate migrations because it:
- ✅ Creates a new combined migration
- ✅ Keeps original migrations intact (for backward compatibility)
- ✅ ✅ **Doesn't require unapplying existing migrations**
- ✅ Can be tested before committing
- ✅ Works even if migrations have been run in production

## Step-by-Step Process

### Step 1: Backup Your Database (Optional but Recommended)

```bash
# Create a backup before making changes
python manage.py dumpdata universe > backup_before_squash.json
```

### Step 2: Squash the Migrations

```bash
cd mysite
python manage.py squashmigrations universe 0001 0012
```

This will:
- Create a new file: `0001_squashed_0012_*.py`
- Keep all original migrations (0001 through 0012) intact
- The squashed migration contains all operations from 0001-0012

### Step 3: Review the Squashed Migration

Open `mysite/universe/migrations/0001_squashed_0012_*.py` and verify:
- All operations are present
- No duplicate operations
- Field renames are correct (e.g., `variety` → `moon_type`)

### Step 4: Test the Squashed Migration

**If you have an existing database with migrations already applied:**
```bash
# Mark the squashed migration as applied (since original migrations are already applied)
python manage.py migrate universe 0001_squashed_0012 --fake
```

**If you're testing on a fresh database:**
```bash
# Apply the squashed migration normally
python manage.py migrate universe
```

### Step 5: Verify Everything Works

```bash
# Run your test suite
python manage.py test universe

# Test the application manually
python manage.py runserver
# Navigate to universe browser, test imports, etc.
```

### Step 6: Clean Up (Optional - Only After Everything Works)

**⚠️ WARNING: Only do this if:**
- ✅ Squashed migration works perfectly
- ✅ All tests pass
- ✅ You've tested thoroughly
- ✅ You're confident no one else is using the old migrations

**If safe to clean up:**
1. Delete original migrations 0001-0012 (keep `__init__.py`)
2. Rename the squashed migration to `0001_initial.py`
3. Update any migration dependencies in other apps

**But honestly, you can just leave them.** The original migrations don't hurt anything - they're just not used anymore after squashing.

## What Happens After Squashing?

- **New installations**: Will use the squashed migration (faster, one operation instead of 12)
- **Existing installations**: Already have migrations applied, so nothing changes
- **Future migrations**: Will depend on the squashed migration (e.g., `0013_*.py` depends on `0001_squashed_0012_*.py`)

## ❌ What NOT to Do

**DON'T use `migrate zero`** unless:
- You have a fresh database with no data
- You can restore from backup
- You're in development and can afford to lose data

**Why it's risky:**
- `migrate zero` unapplies all migrations
- Can drop tables and lose data
- Other apps might break
- Production databases can't do this safely

## Troubleshooting

### "Migration dependencies cannot be found"
- Check that the squashed migration file was created correctly
- Verify the dependency chain in the squashed migration

### "Table already exists" errors
- Use `--fake` flag: `python manage.py migrate universe 0001_squashed_0012 --fake`
- This tells Django: "I already have these tables, just mark the migration as applied"

### "Circular dependency" errors
- This shouldn't happen with squashmigrations, but if it does, check for circular references in your models

## Example Output

After running `squashmigrations`, you'll see something like:

```
Will squash the following migrations:
 - 0001_initial
 - 0002_remove_actor_prompt...
 - 0003_controller_location
 ...
 - 0012_rename_moon_variety_to_moon_type

Do you want to proceed? [yN]: y
Optimizing...
  Optimized from 12 operations to 8 operations.
Created new squashed migration 0001_squashed_0012_*.py
  You should commit this migration but leave the old ones in place;
  the new migration will be used for new installs. Once you are sure
  everything is working correctly, you can delete the old migrations.
```

## Summary

**Safest approach:**
1. Run `squashmigrations universe 0001 0012`
2. Review the generated file
3. Mark it as applied: `python manage.py migrate universe 0001_squashed_0012 --fake`
4. Test everything
5. (Optional) Clean up old migrations later

This is **completely safe** - it doesn't touch your database, just creates a new migration file that combines all the old ones.
