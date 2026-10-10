"""Hardened user profile intake with strict boundary validation (solution)."""

import re

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
MAX_BIO_LENGTH = 200

class ValidationError(ValueError):
    """Raised when input validation fails."""

class UserProfileManager:
    def __init__(self):
        self.profiles: dict[str, dict[str, object]] = {}

    def register_user(self, username: str, email: str, bio: str) -> dict[str, object]:
        if not isinstance(username, str) or not USERNAME_RE.match(username):
            raise ValidationError("Invalid username: must be 3-32 alphanumeric characters, dashes or underscores.")

        if not isinstance(email, str) or not EMAIL_RE.match(email):
            raise ValidationError("Invalid email format.")

        if not isinstance(bio, str) or len(bio) > MAX_BIO_LENGTH:
            raise ValidationError(f"Bio exceeds maximum allowed length of {MAX_BIO_LENGTH} characters.")

        if "\x00" in bio:
            raise ValidationError("Null bytes are forbidden in bio.")

        profile = {
            "username": username,
            "email": email,
            "bio": bio.strip(),
        }
        self.profiles[username] = profile
        return profile
