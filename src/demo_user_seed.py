from src.m1_user_identity import UserIdentityService


DEMO_PROFILE = {
    "age": 25,
    "height_cm": 175.0,
    "starting_weight_kg": 72.0,
    "training_experience": "intermediate",
    "equipment_access": ["full gym", "treadmill"],
    "weekly_availability": "4 days/week, 60 minutes each, Mon/Tue/Thu/Sat evenings",
    "injury_notes": "mild knee discomfort after heavy squats",
    "medical_constraints": "none",
    "diet_preferences": "high protein, no strict restrictions",
    "activity_level": "lightly active",
}


def seed_demo_user(user_repository, profile_repository):
    identity = UserIdentityService(user_repository).get_or_create_user("Alex")
    profile = {"user_id": identity.user["id"], **DEMO_PROFILE}
    saved_profile = profile_repository.upsert_profile(profile)

    return {
        "user": identity.user,
        "profile": saved_profile,
        "created_user": identity.created,
    }
