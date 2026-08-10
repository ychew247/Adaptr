from openpyxl import load_workbook
import pytest

from src.workout_plan_excel_export import export_sessions_workbook


VALIDATED_PLAN = {
    "plan_json": {
        "sessions": [
            {
                "day": "Day 1",
                "focus": "Lower-body strength",
                "exercises": ["Goblet squat", "Dumbbell Romanian deadlift"],
                "sets_reps": "3 sets of 8 reps",
                "adjustment": "Reduce working sets by 20%.",
            },
            {
                "day": "Day 2",
                "focus": "Badminton conditioning",
                "exercises": ["Badminton footwork intervals"],
                "sets_reps": "20 minutes",
                "adjustment": "Train as planned.",
            },
        ]
    }
}


def test_export_sessions_workbook_writes_one_readable_row_per_session(tmp_path):
    output_path = export_sessions_workbook(
        VALIDATED_PLAN,
        tmp_path / "yu_latest_workout_plan.xlsx",
    )

    workbook = load_workbook(output_path)
    sheet = workbook["Sessions"]

    assert workbook.sheetnames == ["Sessions"]
    assert [cell.value for cell in sheet[1]] == [
        "Day",
        "Focus",
        "Exercises",
        "Sets/Reps",
        "Adjustment",
    ]
    assert [cell.value for cell in sheet[2]] == [
        "Day 1",
        "Lower-body strength",
        "Goblet squat\nDumbbell Romanian deadlift",
        "3 sets of 8 reps",
        "Reduce working sets by 20%.",
    ]
    assert sheet["C2"].alignment.wrap_text is True
    assert sheet.freeze_panes == "A2"


def test_export_sessions_workbook_rejects_an_empty_session_list(tmp_path):
    with pytest.raises(ValueError, match="no sessions"):
        export_sessions_workbook(
            {"plan_json": {"sessions": []}},
            tmp_path / "empty_plan.xlsx",
        )

