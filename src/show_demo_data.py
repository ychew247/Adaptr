def format_table_rows(title, columns, rows):
    lines = [f"== {title} =="]
    if not rows:
        lines.append("No rows found.")
        return "\n".join(lines)

    values = [[_stringify(value) for value in row] for row in rows]
    widths = [
        max(len(column), *(len(row[index]) for row in values))
        for index, column in enumerate(columns)
    ]

    lines.append(" | ".join(column.ljust(widths[index]) for index, column in enumerate(columns)))
    lines.append("-+-".join("-" * width for width in widths))
    for row in values:
        lines.append(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip())
    return "\n".join(lines)


def fetch_memory_tables(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, display_name, normalized_name, created_at
            FROM users
            ORDER BY created_at DESC
            """
        )
        users = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              u.display_name,
              p.age,
              p.height_cm,
              p.starting_weight_kg,
              p.training_experience,
              p.equipment_access,
              p.weekly_availability,
              p.activity_level
            FROM user_profiles AS p
            JOIN users AS u ON u.id = p.user_id
            ORDER BY p.updated_at DESC
            """
        )
        profiles = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              u.display_name,
              g.goal_type,
              g.plan_duration_weeks,
              g.goal_details,
              g.status,
              g.updated_at
            FROM goals AS g
            JOIN users AS u ON u.id = g.user_id
            ORDER BY g.updated_at DESC
            """
        )
        goals = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              u.display_name,
              c.checkin_date,
              c.sleep_hours,
              c.stress_level,
              c.energy_level,
              c.soreness_level,
              c.sore_muscle_groups,
              c.pain_notes,
              c.nutrition_adherence,
              c.checkin_details
            FROM daily_checkins AS c
            JOIN users AS u ON u.id = c.user_id
            ORDER BY c.checkin_date DESC, c.created_at DESC
            """
        )
        checkins = cursor.fetchall()

        cursor.execute(
            """
            SELECT
              u.display_name,
              p.week_start,
              p.exercise_names,
              p.target_muscle_groups,
              p.intensity_band,
              p.plan_json,
              p.status
            FROM workout_plans AS p
            JOIN users AS u ON u.id = p.user_id
            ORDER BY p.created_at DESC
            """
        )
        plans = cursor.fetchall()

    return users, profiles, goals, checkins, plans


def fetch_users_and_profiles(connection):
    users, profiles, _goals, _checkins, _plans = fetch_memory_tables(connection)
    return users, profiles


def _stringify(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
