USER_PROFILE = {}

def save_profile(profile: dict):
    global USER_PROFILE
    USER_PROFILE = profile

def get_profile():
    return USER_PROFILE
