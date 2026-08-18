from dataclasses import dataclass
import re


def normalize_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip()).lower()
    if not normalized:
        raise ValueError("User name is required")
    return normalized


@dataclass(frozen=True)
class UserIdentityResult:
    user: dict
    created: bool


class UserIdentityService:
    def __init__(self, repository):
        self.repository = repository

    def get_or_create_user(self, display_name: str) -> UserIdentityResult:
        normalized_name = normalize_name(display_name)
        user = self.repository.find_by_normalized_name(normalized_name)
        if user is not None:
            return UserIdentityResult(user=user, created=False)

        user = self.repository.create_user(display_name.strip(), normalized_name)
        return UserIdentityResult(user=user, created=True)
