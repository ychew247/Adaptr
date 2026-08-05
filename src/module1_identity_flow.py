from src.m1_user_identity import UserIdentityService


def run_identity_flow(repository, ask=input, say=print):
    _user, next_step = identify_user(repository, ask=ask, say=say)
    return next_step


def identify_user(repository, ask=input, say=print):
    prompt = "Hi, I am your adaptive fitness memory agent. What name should I use for your fitness profile?"
    name = ask(prompt)

    result = UserIdentityService(repository).get_or_create_user(name)
    display_name = result.user["display_name"]

    if result.created:
        say(
            f"I do not have a profile for {display_name} yet, so I created one. "
            "Next I will collect your stable fitness profile."
        )
        next_step = "static_onboarding"
    else:
        say(
            f"Welcome back, {display_name}. I loaded your fitness memory. "
            "Next I will ask for today's adaptive check-in."
        )
        next_step = "adaptive_checkin"

    return result.user, next_step
