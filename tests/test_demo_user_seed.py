from src.demo_user_seed import DEMO_PROFILE, seed_demo_user
from tests.test_static_profile import FakeProfileRepository
from tests.test_user_identity import FakeUserRepository


def test_seed_demo_user_creates_alex_with_static_profile():
    user_repository = FakeUserRepository()
    profile_repository = FakeProfileRepository()

    result = seed_demo_user(user_repository, profile_repository)

    user = user_repository.find_by_normalized_name("alex")
    profile = profile_repository.find_by_user_id(user["id"])
    assert result["created_user"] is True
    assert user["display_name"] == "Alex"
    assert profile["age"] == DEMO_PROFILE["age"]
    assert profile["equipment_access"] == ["full gym", "treadmill"]
    assert profile["activity_level"] == "lightly active"


def test_seed_demo_user_updates_existing_alex_profile_without_duplicate_user():
    user_repository = FakeUserRepository()
    existing = user_repository.create_user("Alex", "alex")
    profile_repository = FakeProfileRepository()

    result = seed_demo_user(user_repository, profile_repository)

    assert result["created_user"] is False
    assert result["user"]["id"] == existing["id"]
    assert len(user_repository.users_by_normalized_name) == 1
    assert profile_repository.find_by_user_id(existing["id"])["starting_weight_kg"] == 72.0
