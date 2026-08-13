from pathlib import Path


def test_daily_checkins_migration_defines_the_upsert_conflict_key():
    sql = Path("sql/004_create_daily_checkins.sql").read_text(encoding="utf-8")

    assert "CREATE UNIQUE INDEX IF NOT EXISTS daily_checkins_user_date_unique_idx" in sql
    assert "ON daily_checkins (user_id, checkin_date);" in sql
