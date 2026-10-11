"""Unsafe user profile intake accepting arbitrary strings without validation (starter)."""

class UserProfileManager:
    def __init__(self):
        self.profiles: dict[str, dict[str, object]] = {}

    def register_user(self, username: str, email: str, bio: str) -> dict[str, object]:
        # Sin validación de longitud, sin validación de formato ni caracteres de control
        profile = {
            "username": username,
            "email": email,
            "bio": bio,
        }
        self.profiles[username] = profile
        return profile
