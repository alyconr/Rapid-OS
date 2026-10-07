from pathlib import Path
import re


HARNESS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

BUILTIN_HARNESS_IDS: tuple[str, ...] = (
    "antigravity",
    "claude",
    "codex",
    "cursor",
    "vscode",
)


class HarnessCapabilityError(ValueError):
    """Base domain error for Phase 5 Harness Capability Registry operations (RAPID1101-RAPID1112)."""

    default_code = "RAPID1102"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        path: Path | str | None = None,
    ):
        super().__init__(message)
        self.code = code or self.default_code
        self.path = path


class InvalidCapabilityIdError(HarnessCapabilityError):
    default_code = "RAPID1101"


class InvalidHarnessProfileError(HarnessCapabilityError):
    default_code = "RAPID1102"


class HarnessProfileNotFoundError(HarnessCapabilityError):
    default_code = "RAPID1103"


class HarnessIdentityError(HarnessCapabilityError):
    default_code = "RAPID1104"


class UnsafeHarnessPathError(HarnessCapabilityError):
    default_code = "RAPID1105"


class InvalidCapabilitySupportError(HarnessCapabilityError):
    default_code = "RAPID1106"


class InvalidCapabilityRequirementError(HarnessCapabilityError):
    default_code = "RAPID1107"


class InvalidCapabilityResolutionError(HarnessCapabilityError):
    default_code = "RAPID1108"


class CapabilityResolutionDigestMismatchError(HarnessCapabilityError):
    default_code = "RAPID1109"


class IncompatibleHarnessError(HarnessCapabilityError):
    default_code = "RAPID1110"


class InvalidCapabilityLockError(HarnessCapabilityError):
    default_code = "RAPID1111"


CapabilityLockError = InvalidCapabilityLockError


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def validate_harness_id(raw_id: object, label: str = "harness id") -> str:
    """Validate that `raw_id` is a canonical, lowercase, path-safe harness identifier."""
    if not isinstance(raw_id, str):
        raise HarnessIdentityError(
            f"Invalid {label}: expected a non-empty lowercase string."
        )
    if "\x00" in raw_id:
        raise HarnessIdentityError(
            f"Invalid {label}: null bytes are not allowed."
        )
    if not raw_id:
        raise HarnessIdentityError(
            f"Invalid {label}: value cannot be empty."
        )
    if raw_id != raw_id.strip() or any(ch.isspace() for ch in raw_id):
        raise HarnessIdentityError(
            f"Invalid {label} '{raw_id}': whitespace is not allowed."
        )
    if (
        ".." in raw_id
        or "/" in raw_id
        or "\\" in raw_id
        or _WINDOWS_DRIVE_RE.match(raw_id)
    ):
        raise HarnessIdentityError(
            f"Invalid {label} '{raw_id}': path segments or drives are not allowed."
        )
    if any(ch.isupper() for ch in raw_id):
        raise HarnessIdentityError(
            f"Invalid {label} '{raw_id}': uppercase characters are not allowed."
        )
    if not HARNESS_ID_RE.match(raw_id):
        raise HarnessIdentityError(
            f"Invalid {label} '{raw_id}': must match {HARNESS_ID_RE.pattern}."
        )
    return raw_id


def validate_harness_profile_source(
    source: object,
    *,
    expected_harness_id: str | None = None,
    error_cls=UnsafeHarnessPathError,
) -> str:
    """Validate that a profile provenance string is portable (`builtin:<id>` or `.rapid-os/harnesses/<id>.json`)."""
    if not isinstance(source, str) or not source.strip():
        raise error_cls("Profile provenance source must be a non-empty string.")
    if "\x00" in source:
        raise error_cls("Profile provenance source cannot contain null bytes.")
    if source != source.strip():
        raise error_cls(
            f"Profile provenance source '{source}' cannot have leading or trailing whitespace."
        )
    if "\\" in source or _WINDOWS_DRIVE_RE.match(source) or source.startswith("/"):
        raise error_cls(
            f"Profile provenance source '{source}' must be a portable POSIX provenance string, not a host path."
        )
    segments = [seg for seg in source.split("/") if seg]
    if ".." in segments:
        raise error_cls(
            f"Profile provenance source '{source}' cannot contain '..' traversal segments."
        )

    if source.startswith("builtin:"):
        builtin_id = source[len("builtin:") :]
        try:
            validated_id = validate_harness_id(builtin_id, "builtin harness id")
        except HarnessIdentityError as exc:
            raise error_cls(str(exc)) from exc
        if expected_harness_id is not None and validated_id != expected_harness_id:
            raise error_cls(
                f"Profile provenance '{source}' does not match harness id '{expected_harness_id}'."
            )
        return source

    prefix = ".rapid-os/harnesses/"
    suffix = ".json"
    if source.startswith(prefix) and source.endswith(suffix):
        middle = source[len(prefix) : -len(suffix)]
        if "/" not in middle:
            try:
                validated_id = validate_harness_id(middle, "project harness id")
            except HarnessIdentityError as exc:
                raise error_cls(str(exc)) from exc
            if (
                expected_harness_id is not None
                and validated_id != expected_harness_id
            ):
                raise error_cls(
                    f"Profile provenance '{source}' does not match harness id '{expected_harness_id}'."
                )
            return source

    raise error_cls(
        f"Invalid profile provenance source '{source}': expected 'builtin:<id>' or '.rapid-os/harnesses/<id>.json'."
    )
