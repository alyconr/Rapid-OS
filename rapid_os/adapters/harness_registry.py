from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_write_text,
)
from rapid_os.domain.capabilities import (
    BUILTIN_HARNESS_IDS,
    CANONICAL_CAPABILITY_IDS,
    HARNESS_PROFILE_SCHEMA_VERSION,
    CapabilitySupport,
    CapabilitySupportStatus,
    HarnessCapabilityError,
    HarnessIdentityError,
    HarnessProfile,
    HarnessProfileNotFoundError,
    InvalidHarnessProfileError,
    UnsafeHarnessPathError,
    validate_harness_id,
    validate_harness_profile_source,
)


HARNESSES_DIRNAME = "harnesses"


def _build_conservative_builtin_profile(harness_id: str) -> HarnessProfile:
    supported_reasons: Mapping[str, str] = {
        "context.consume": f"Rapid OS natively compiles and renders context for built-in harness '{harness_id}'.",
        "repository.read": f"Built-in harness '{harness_id}' reads repository files where Rapid OS context is injected.",
        "workspace.current": f"Built-in harness '{harness_id}' operates within the current repository workspace.",
    }
    unknown_reasons: Mapping[str, str] = {
        "git.inspect": "Git inspection depends on local harness runtime permissions and environment.",
        "git.modify": "Git modification depends on local harness runtime permissions and environment.",
        "mcp.invoke": "MCP tool invocation depends on active runtime MCP configuration.",
        "repository.write": "Repository write capability depends on active harness session permissions; confirm in a project profile.",
        "shell.execute": "Shell command execution depends on local sandbox and approval configuration.",
        "subagents.delegate": "Subagent delegation depends on external harness version and configuration.",
        "tests.execute": "Automated test execution depends on local shell and test runner availability.",
        "workspace.isolated": "Isolated workspace or worktree operation depends on external harness configuration.",
    }

    supports: list[CapabilitySupport] = []
    for cap_id in CANONICAL_CAPABILITY_IDS:
        if cap_id in supported_reasons:
            supports.append(
                CapabilitySupport(
                    capability_id=cap_id,
                    status=CapabilitySupportStatus.SUPPORTED,
                    reason=supported_reasons[cap_id],
                )
            )
        else:
            supports.append(
                CapabilitySupport(
                    capability_id=cap_id,
                    status=CapabilitySupportStatus.UNKNOWN,
                    reason=unknown_reasons[cap_id],
                )
            )

    return HarnessProfile(
        schema_version=HARNESS_PROFILE_SCHEMA_VERSION,
        id=harness_id,
        capabilities=tuple(supports),
    )


BUILTIN_HARNESS_PROFILES: Mapping[str, HarnessProfile] = {
    harness_id: _build_conservative_builtin_profile(harness_id)
    for harness_id in BUILTIN_HARNESS_IDS
}


@dataclass(frozen=True)
class ResolvedHarnessProfile:
    id: str
    source: str
    profile_digest: str
    profile: HarnessProfile

    def __post_init__(self):
        validated_id = validate_harness_id(
            self.id,
            "ResolvedHarnessProfile.id",
        )
        object.__setattr__(self, "id", validated_id)
        if not isinstance(self.profile, HarnessProfile):
            raise InvalidHarnessProfileError(
                "ResolvedHarnessProfile.profile must be a HarnessProfile instance."
            )
        if self.profile.id != validated_id:
            raise HarnessIdentityError(
                f"ResolvedHarnessProfile.id '{validated_id}' does not match profile.id '{self.profile.id}'."
            )
        validated_source = validate_harness_profile_source(
            self.source,
            expected_harness_id=validated_id,
        )
        object.__setattr__(self, "source", validated_source)
        if self.profile_digest != self.profile.content_digest:
            raise InvalidHarnessProfileError(
                f"ResolvedHarnessProfile.profile_digest '{self.profile_digest}' does not match profile.content_digest '{self.profile.content_digest}'."
            )

    @property
    def schema_version(self) -> int:
        return self.profile.schema_version

    @property
    def capabilities(self) -> tuple[CapabilitySupport, ...]:
        return self.profile.capabilities

    @property
    def content_digest(self) -> str:
        return self.profile.content_digest

    def __iter__(self):
        yield self.profile
        yield self.source

    def __len__(self) -> int:
        return 2

    def __getitem__(self, index: int):
        return (self.profile, self.source)[index]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source": self.source,
            "profile_digest": self.profile_digest,
            "content_digest": self.profile.content_digest,
            "capabilities": [c.to_dict() for c in self.profile.capabilities],
            "profile": self.profile.to_dict(),
        }


def resolve_harnesses_root_dir(
    project_root: Path,
    project_rapid_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return `(root, rapid_dir, harnesses_dir)` with containment verification."""
    raw_first = Path(project_root)
    if project_rapid_dir is None and raw_first.name == ".rapid-os":
        rapid_dir = raw_first
        root = rapid_dir.parent
    else:
        root = raw_first
        rapid_dir = (
            Path(project_rapid_dir)
            if project_rapid_dir is not None
            else (root / ".rapid-os")
        )

    try:
        contained_rapid = ensure_path_within_root(root, rapid_dir)
        harnesses_dir = resolve_child_path(
            contained_rapid,
            HARNESSES_DIRNAME,
            single_segment=True,
        )
        ensure_path_within_root(root, harnesses_dir)
    except ValueError as exc:
        raise UnsafeHarnessPathError(
            str(exc),
            path=rapid_dir / HARNESSES_DIRNAME,
        ) from exc

    return root, contained_rapid, harnesses_dir


class HarnessRegistry:
    """Deterministic registry resolving built-in and `.rapid-os/harnesses/*.json` profiles without silent fallback."""

    def __init__(
        self,
        project_root: Path = Path("."),
        project_rapid_dir: Path | None = None,
    ):
        root, rapid_dir, harnesses_dir = resolve_harnesses_root_dir(
            project_root,
            project_rapid_dir,
        )
        self.root = root
        self.rapid_dir = rapid_dir
        self.harnesses_dir = harnesses_dir

    def _check_harnesses_dir_safety(self) -> None:
        if self.rapid_dir.is_symlink():
            raise UnsafeHarnessPathError(
                f"Project .rapid-os path '{self.rapid_dir}' cannot be a symlink.",
                path=self.rapid_dir,
            )
        if self.harnesses_dir.is_symlink():
            raise UnsafeHarnessPathError(
                f"Harness registry root '{self.harnesses_dir}' cannot be a symlink.",
                path=self.harnesses_dir,
            )
        if self.harnesses_dir.exists() and not self.harnesses_dir.is_dir():
            raise UnsafeHarnessPathError(
                f"Harness registry path '{self.harnesses_dir}' is not a directory.",
                path=self.harnesses_dir,
            )

    def _resolve_profile_path(self, harness_id: str) -> tuple[str, Path]:
        validated_id = validate_harness_id(harness_id)
        self._check_harnesses_dir_safety()
        filename = f"{validated_id}.json"
        try:
            profile_file = resolve_child_path(
                self.harnesses_dir,
                filename,
                single_segment=True,
            )
            ensure_path_within_root(self.root, profile_file)
        except ValueError as exc:
            raise UnsafeHarnessPathError(
                str(exc),
                path=self.harnesses_dir / filename,
            ) from exc

        if profile_file.is_symlink():
            raise UnsafeHarnessPathError(
                f"Harness profile file '{profile_file}' cannot be a symlink.",
                path=profile_file,
            )
        return validated_id, profile_file

    def _read_project_profile_file(
        self,
        profile_file: Path,
        expected_id: str,
    ) -> HarnessProfile:
        if profile_file.is_symlink():
            raise UnsafeHarnessPathError(
                f"Harness profile file '{profile_file}' cannot be a symlink.",
                path=profile_file,
            )
        if not profile_file.is_file():
            raise UnsafeHarnessPathError(
                f"Harness profile path '{profile_file}' is not a regular file.",
                path=profile_file,
            )
        try:
            raw = profile_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeHarnessPathError(
                f"Harness profile file '{profile_file}' could not be read as UTF-8: {exc}",
                path=profile_file,
            ) from exc

        try:
            profile = HarnessProfile.from_json(raw, verify_digest=True)
        except HarnessCapabilityError as exc:
            raise type(exc)(str(exc), code=exc.code, path=profile_file) from exc

        if profile.id != expected_id:
            raise HarnessIdentityError(
                f"HarnessProfile.id '{profile.id}' does not match file '{profile_file.name}' (expected '{expected_id}').",
                path=profile_file,
            )
        return profile

    def get_builtin(self, harness_id: str) -> HarnessProfile:
        """Return the canonical built-in `HarnessProfile` for `harness_id`, or raise `RAPID1103`."""
        validated_id = validate_harness_id(harness_id)
        if validated_id not in BUILTIN_HARNESS_PROFILES:
            raise HarnessProfileNotFoundError(
                f"Built-in harness profile '{validated_id}' was not found."
            )
        return BUILTIN_HARNESS_PROFILES[validated_id]

    def get_project_profile(self, harness_id: str) -> HarnessProfile | None:
        """Load `.rapid-os/harnesses/<harness_id>.json` if present, raising on corruption without fallback."""
        validated_id, profile_file = self._resolve_profile_path(harness_id)
        if not profile_file.exists():
            return None
        return self._read_project_profile_file(profile_file, validated_id)

    def resolve_active_profile(self, harness_id: str) -> ResolvedHarnessProfile:
        """Resolve active `HarnessProfile` and portable provenance (`project > builtin`), never falling back on corrupt project overrides."""
        validated_id, profile_file = self._resolve_profile_path(harness_id)
        if profile_file.exists():
            profile = self._read_project_profile_file(profile_file, validated_id)
            source = f".rapid-os/harnesses/{validated_id}.json"
            return ResolvedHarnessProfile(
                id=validated_id,
                source=source,
                profile_digest=profile.content_digest,
                profile=profile,
            )

        if validated_id in BUILTIN_HARNESS_PROFILES:
            builtin = BUILTIN_HARNESS_PROFILES[validated_id]
            return ResolvedHarnessProfile(
                id=validated_id,
                source=f"builtin:{validated_id}",
                profile_digest=builtin.content_digest,
                profile=builtin,
            )

        raise HarnessProfileNotFoundError(
            f"Harness profile '{validated_id}' was not found in project registry or built-in profiles.",
            path=profile_file,
        )

    def get(self, harness_id: str) -> HarnessProfile:
        """Return active `HarnessProfile` for `harness_id`."""
        return self.resolve_active_profile(harness_id).profile

    def list_profiles(self) -> tuple[ResolvedHarnessProfile, ...]:
        """Return all active profiles (builtins + project overrides/custom profiles) ordered by `id` ASC without duplicates."""
        self._check_harnesses_dir_safety()
        project_ids: set[str] = set()

        if self.harnesses_dir.exists():
            try:
                entries = sorted(
                    self.harnesses_dir.iterdir(),
                    key=lambda p: p.name,
                )
            except OSError as exc:
                raise UnsafeHarnessPathError(
                    f"Harness registry directory '{self.harnesses_dir}' could not be read: {exc}",
                    path=self.harnesses_dir,
                ) from exc

            for entry in entries:
                if entry.is_symlink():
                    raise UnsafeHarnessPathError(
                        f"Harness profile entry '{entry}' cannot be a symlink.",
                        path=entry,
                    )
                try:
                    ensure_path_within_root(self.root, entry)
                except ValueError as exc:
                    raise UnsafeHarnessPathError(str(exc), path=entry) from exc

                if not entry.is_file() or not entry.name.endswith(".json"):
                    raise InvalidHarnessProfileError(
                        f"Unexpected non-profile entry '{entry.name}' in .rapid-os/harnesses.",
                        path=entry,
                    )
                stem = entry.name[:-5]
                try:
                    validated_stem = validate_harness_id(
                        stem,
                        "harness profile filename",
                    )
                except HarnessIdentityError as exc:
                    raise HarnessIdentityError(
                        str(exc),
                        code=exc.code,
                        path=entry,
                    ) from exc
                project_ids.add(validated_stem)

        all_ids = sorted(set(BUILTIN_HARNESS_IDS) | project_ids)
        return tuple(
            self.resolve_active_profile(harness_id) for harness_id in all_ids
        )

    def write_project_profile(
        self,
        profile: HarnessProfile,
        *,
        overwrite: bool = True,
    ) -> Path:
        """Persist `profile` to `.rapid-os/harnesses/<id>.json` with canonical `content_digest`."""
        if not isinstance(profile, HarnessProfile):
            raise InvalidHarnessProfileError(
                "write_project_profile requires a HarnessProfile instance."
            )
        _, profile_file = self._resolve_profile_path(profile.id)
        if not overwrite and profile_file.exists():
            raise InvalidHarnessProfileError(
                f"Project harness profile '{profile_file}' already exists; refusing to overwrite.",
                path=profile_file,
            )
        ensure_path_within_root(self.root, profile_file)
        safe_write_text(
            profile_file,
            profile.to_json(indent=2) + "\n",
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        return profile_file

    def initialize_project_profile(self, harness_id: str) -> Path:
        """Copy canonical built-in profile to `.rapid-os/harnesses/<id>.json` without overwriting existing files."""
        validated_id = validate_harness_id(harness_id)
        if validated_id not in BUILTIN_HARNESS_PROFILES:
            raise HarnessProfileNotFoundError(
                f"Cannot initialize custom harness '{validated_id}': no built-in profile exists. Create '.rapid-os/harnesses/{validated_id}.json' explicitly."
            )
        builtin = BUILTIN_HARNESS_PROFILES[validated_id]
        return self.write_project_profile(builtin, overwrite=False)

    def validate(self):
        from rapid_os.domain.validation import validate_harness_registry

        return validate_harness_registry(self.rapid_dir, self.root)
