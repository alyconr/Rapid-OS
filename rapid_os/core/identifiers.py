import re


LOCAL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REMOTE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REMOTE_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
WINDOWS_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def validate_identifier(value: str, label: str = "identifier") -> str:
    """Validate a single local slug identifier (no paths, traversal, or shell metacharacters)."""
    if not isinstance(value, str):
        raise ValueError(f"Invalid {label}: expected a string.")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Invalid {label}: value cannot be empty.")

    if "\x00" in cleaned:
        raise ValueError(f"Invalid {label}: null bytes are not allowed.")

    if "/" in cleaned or "\\" in cleaned or WINDOWS_DRIVE_PREFIX.match(cleaned):
        raise ValueError(
            f"Invalid {label} '{cleaned}': path separators and drive prefixes are not allowed."
        )

    if cleaned in {".", ".."} or ".." in cleaned:
        raise ValueError(
            f"Invalid {label} '{cleaned}': traversal sequences are not allowed."
        )

    if cleaned.endswith("."):
        raise ValueError(
            f"Invalid {label} '{cleaned}': trailing dots are not allowed."
        )

    if not LOCAL_IDENTIFIER_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid {label} '{cleaned}': must start with an alphanumeric character and contain only letters, digits, '.', '_', or '-'."
        )

    return cleaned


def validate_remote_package_reference(
    value: str,
    label: str = "remote package reference",
) -> str:
    """Validate a remote package/skill reference such as `owner/package`, `@scope/pkg`, or `pkg@1.0.0`."""
    if not isinstance(value, str):
        raise ValueError(f"Invalid {label}: expected a string.")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"Invalid {label}: value cannot be empty.")

    if "\x00" in cleaned or any(ch.isspace() for ch in cleaned):
        raise ValueError(
            f"Invalid {label} '{cleaned}': whitespace and control characters are not allowed."
        )

    if cleaned.startswith("-"):
        raise ValueError(
            f"Invalid {label} '{cleaned}': option flags are not allowed."
        )

    if "\\" in cleaned or WINDOWS_DRIVE_PREFIX.match(cleaned) or cleaned.startswith("/"):
        raise ValueError(
            f"Invalid {label} '{cleaned}': local or absolute filesystem paths are not allowed."
        )

    package_part = cleaned
    version_part = None
    if "@" in cleaned[1:]:
        split_index = cleaned.rfind("@")
        package_part = cleaned[:split_index]
        version_part = cleaned[split_index + 1 :]
        if not version_part or not REMOTE_VERSION_PATTERN.match(version_part):
            raise ValueError(
                f"Invalid {label} '{cleaned}': invalid version specifier."
            )

    if package_part.startswith("@"):
        scoped_body = package_part[1:]
        segments = scoped_body.split("/")
        if len(segments) != 2:
            raise ValueError(
                f"Invalid {label} '{cleaned}': scoped packages must match '@scope/package'."
            )
    else:
        segments = package_part.split("/")
        if len(segments) not in (1, 2):
            raise ValueError(
                f"Invalid {label} '{cleaned}': expected 'package' or 'owner/package'."
            )

    for segment in segments:
        if (
            not segment
            or segment in {".", ".."}
            or ".." in segment
            or segment.endswith(".")
            or not REMOTE_SEGMENT_PATTERN.match(segment)
        ):
            raise ValueError(
                f"Invalid {label} '{cleaned}': invalid segment '{segment}'."
            )

    return cleaned
