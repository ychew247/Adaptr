from src.user_identity import UserIdentityService


def run_identity_flow(repository, ask=input, say=print):
    prompt = "Hi, I am your adaptive fitness memory agent. What name should I use for your fitness profile?"
    name = ask(prompt)
    say(prompt)

    result = UserIdentityService(repository).get_or_create_user(name)
    display_name = result.user["display_name"]

    if result.created:
        say(
            f"I do not have a profile for {display_name} yet, so I created one. "
            "Next I will collect your stable fitness profile."
        )
        return "static_onboarding"

    say(
        f"Welcome back, {display_name}. I loaded your fitness memory. "
        "Next I will ask for today's adaptive check-in."
    )
    return "adaptive_checkin"
