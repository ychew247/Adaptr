from src.module1_identity_flow import identify_user, run_identity_flow
from src.m1_user_identity import UserIdentityService, normalize_name


class FakeUserRepository:
    def __init__(self):
        self.users_by_normalized_name = {}

    def find_by_normalized_name(self, normalized_name):
        return self.users_by_normalized_name.get(normalized_name)

    def create_user(self, display_name, normalized_name):
        user = {
            "id": f"user-{len(self.users_by_normalized_name) + 1}",
            "display_name": display_name,
            "normalized_name": normalized_name,
        }
        self.users_by_normalized_name[normalized_name] = user
        return user


def test_normalize_name_trims_and_lowercases_spacing():
    assert normalize_name("  Alex   Tan  ") == "alex tan"


def test_get_or_create_user_loads_existing_user_without_creating_duplicate():
    repository = FakeUserRepository()
    existing = repository.create_user("Alex Tan", "alex tan")
    service = UserIdentityService(repository)

    result = service.get_or_create_user(" alex TAN ")

    assert result.user == existing
    assert result.created is False
    assert len(repository.users_by_normalized_name) == 1


def test_get_or_create_user_registers_new_user_when_name_does_not_exist():
    repository = FakeUserRepository()
    service = UserIdentityService(repository)

    result = service.get_or_create_user("Sam")

    assert result.user["display_name"] == "Sam"
    assert result.user["normalized_name"] == "sam"
    assert result.created is True


def test_get_or_create_user_rejects_blank_name():
    service = UserIdentityService(FakeUserRepository())

    try:
        service.get_or_create_user("   ")
    except ValueError as error:
        assert str(error) == "User name is required"
    else:
        raise AssertionError("Expected blank names to be rejected")


def test_identity_flow_registers_new_user_and_returns_static_onboarding_step():
    repository = FakeUserRepository()
    messages = []
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return "Mira"

    next_step = run_identity_flow(
        repository=repository,
        ask=ask,
        say=messages.append,
    )

    assert next_step == "static_onboarding"
    assert repository.find_by_normalized_name("mira")["display_name"] == "Mira"
    assert prompts == [
        "Hi, I am your adaptive fitness memory agent. What name should I use for your fitness profile?"
    ]
    assert messages == [
        "I do not have a profile for Mira yet, so I created one. Next I will collect your stable fitness profile.",
    ]


def test_identity_flow_loads_existing_user_and_returns_checkin_step():
    repository = FakeUserRepository()
    repository.create_user("Alex", "alex")
    messages = []
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return " alex "

    next_step = run_identity_flow(
        repository=repository,
        ask=ask,
        say=messages.append,
    )

    assert next_step == "adaptive_checkin"
    assert prompts == [
        "Hi, I am your adaptive fitness memory agent. What name should I use for your fitness profile?"
    ]
    assert messages == [
        "Welcome back, Alex. I loaded your fitness memory. Next I will ask for today's adaptive check-in.",
    ]


def test_identify_user_returns_user_and_next_step():
    repository = FakeUserRepository()
    messages = []

    user, next_step = identify_user(
        repository=repository,
        ask=lambda prompt: "Nora",
        say=messages.append,
    )

    assert user["display_name"] == "Nora"
    assert user["normalized_name"] == "nora"
    assert next_step == "static_onboarding"
