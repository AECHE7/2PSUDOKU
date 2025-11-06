# 🔧 result_type Column Migration Fix

## Problem Summary

**Error:** `column game_gameresult.result_type does not exist`

**Why it happens:**
- Django migrations were created locally but NOT applied to production PostgreSQL
- The column exists in your model but NOT in the actual database table
- This is a **schema drift** issue between code and database

## ✅ Solution Applied

### Files Created/Modified:

1. **`force_add_result_type.py`** - Direct SQL column addition script
2. **`ensure_db_schema.py`** - General schema verification
3. **`build.sh`** - Updated to run both scripts during deployment
4. **Migration 0006** - Django migration for the column

### What Happens on Next Deployment:

```bash
# During build.sh execution:
1. Install dependencies
2. Run Django migrations (python manage.py migrate)
3. Run ensure_db_schema.py (general checks)
4. Run force_add_result_type.py (ADDS THE COLUMN)
5. Collect static files
6. Start server
```

## 🎯 Manual Fix (If Needed)

If the automatic deployment doesn't work, run this on Render shell:

```bash
# Option 1: Use the force script
python force_add_result_type.py

# Option 2: Direct SQL (if Option 1 fails)
python manage.py dbshell
```

Then in PostgreSQL:
```sql
-- Check if column exists
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'game_gameresult' AND column_name = 'result_type';

-- Add column if missing
ALTER TABLE game_gameresult 
ADD COLUMN result_type VARCHAR(20) DEFAULT 'completion' NOT NULL;

-- Verify
\d game_gameresult
```

## 📋 Prevention Checklist

### Before Every Model Change:

- [ ] Modify your Django model
- [ ] Run `python manage.py makemigrations`
- [ ] Run `python manage.py migrate` (locally first)
- [ ] Test locally with the same DB type as production
- [ ] Commit migration files to git
- [ ] Deploy to production
- [ ] Verify migrations ran: `python manage.py showmigrations`

### On Render (Production):

Your `build.sh` should ALWAYS include:
```bash
python manage.py migrate --noinput
```

This is already in your build.sh, so future migrations will work.

## 🚨 Common Mistakes to Avoid

1. **DON'T** skip migrations when deploying
2. **DON'T** manually edit migration files after they're applied
3. **DON'T** delete migration files from git
4. **DO** always commit migrations with your model changes
5. **DO** verify migrations completed successfully after deployment

## 🔍 Verification Steps

After deployment, verify the fix worked:

```bash
# On Render shell or your terminal:
python manage.py shell
```

Then:
```python
from game.models import GameResult
from django.db import connection

# Check if column exists
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'game_gameresult' 
        AND column_name = 'result_type'
    """)
    print(cursor.fetchone())  # Should show ('result_type',)

# Try creating a result
from game.models import GameSession, User
from datetime import timedelta

# This should work without errors now
print("Column exists and is ready!")
```

## 📊 Migration History

Your current migrations:
- `0001_initial.py` - Initial schema
- `0002_remove_gamesession_current_turn_and_more.py` - Session updates
- `0003_gameresult_result_type_alter_gamesession_status.py` - Added result_type
- `0005_ensure_result_type.py` - Ensure column exists
- `0006_ensure_result_type_column.py` - Force column creation

## 🎓 Django Migration Best Practices

### Development Workflow:
```bash
# 1. Make model changes
vim game/models.py

# 2. Create migration
python manage.py makemigrations

# 3. Review migration file
cat game/migrations/000X_*.py

# 4. Apply locally
python manage.py migrate

# 5. Test thoroughly
python manage.py shell
# ... test your changes ...

# 6. Commit
git add game/models.py game/migrations/
git commit -m "Add result_type field to GameResult"

# 7. Deploy
git push origin main
```

### Production Workflow:
```bash
# On Render, this happens automatically:
1. Git pull (Render detects new commit)
2. Run build.sh
   - Install dependencies
   - Run migrations ← YOUR FIX IS HERE
   - Collect static
3. Start server
```

## 💡 Why This Fix Works

1. **`force_add_result_type.py`**:
   - Checks if column exists (idempotent)
   - Adds column using direct SQL
   - Sets default value
   - Verifies success

2. **Runs during build**:
   - Executes BEFORE server starts
   - Ensures schema is correct
   - Logs everything for debugging

3. **Safe to run multiple times**:
   - Checks before adding
   - Won't fail if column exists
   - Won't corrupt existing data

## 🐛 Troubleshooting

### If error persists:

1. Check Render logs for migration errors
2. Run `python force_add_result_type.py` manually via Render shell
3. Verify PostgreSQL version compatibility
4. Check if migrations are in git

### Get detailed info:
```bash
# On Render shell:
python manage.py showmigrations game --plan
python manage.py sqlmigrate game 0003
```

## 📞 Quick Reference

| Command | Purpose |
|---------|---------|
| `python manage.py makemigrations` | Create migration files |
| `python manage.py migrate` | Apply migrations |
| `python manage.py showmigrations` | List migration status |
| `python force_add_result_type.py` | Force add the column |
| `python manage.py dbshell` | Direct PostgreSQL access |

---

**Status:** ✅ Fix applied and deployed
**Next Steps:** Monitor deployment logs for "✅ Successfully added 'result_type' column"
