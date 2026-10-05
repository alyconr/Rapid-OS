import json
import unittest
from pathlib import Path

from rapid_os.domain.project import (
    Confidence,
    Evidence,
    PROJECT_MODEL_SCHEMA_VERSION,
    ProjectFact,
    ProjectModel,
    SourceType,
    canonical_detector_id,
    normalize_evidence_path,
    normalize_facts,
)


class ProjectModelTests(unittest.TestCase):
    def test_project_fact_creation_and_serialization(self):
        evidence = Evidence(
            path="pyproject.toml",
            reason="Found FastAPI in dependencies",
            source_type=SourceType.DEPENDENCY,
            detector="framework.fastapi",
        )
        fact = ProjectFact(
            category="framework",
            value="fastapi",
            confidence=Confidence.HIGH,
            evidence=(evidence,),
            detector="framework.fastapi",
        )

        self.assertEqual(fact.category, "framework")
        self.assertEqual(fact.value, "fastapi")
        self.assertEqual(fact.confidence, Confidence.HIGH)
        self.assertEqual(fact.detector, "framework.fastapi")
        self.assertEqual(
            fact.to_dict(),
            {
                "category": "framework",
                "value": "fastapi",
                "confidence": "high",
                "detector": "framework.fastapi",
                "evidence": [
                    {
                        "path": "pyproject.toml",
                        "reason": "Found FastAPI in dependencies",
                        "source_type": "dependency",
                        "detector": "framework.fastapi",
                    }
                ],
            },
        )

    def test_confidence_and_source_type_serialize_as_canonical_strings(self):
        self.assertEqual(Confidence.HIGH.value, "high")
        self.assertEqual(Confidence.MEDIUM.value, "medium")
        self.assertEqual(Confidence.LOW.value, "low")
        self.assertTrue(Confidence.HIGH.rank > Confidence.MEDIUM.rank > Confidence.LOW.rank)

        self.assertEqual(SourceType.FILE.value, "file")
        self.assertEqual(SourceType.MANIFEST.value, "manifest")
        self.assertEqual(SourceType.CONFIG.value, "config")
        self.assertEqual(SourceType.DIRECTORY.value, "directory")
        self.assertEqual(SourceType.ENVIRONMENT_KEY.value, "environment-key")
        self.assertEqual(SourceType.DEPENDENCY.value, "dependency")
        self.assertEqual(SourceType.WORKFLOW.value, "workflow")

    def test_relative_evidence_path_normalization_produces_portable_posix_paths(self):
        root = Path("/tmp/project")
        self.assertEqual(
            normalize_evidence_path("/tmp/project/package.json", root),
            "package.json",
        )
        self.assertEqual(
            normalize_evidence_path("/tmp/project/apps/api/pyproject.toml", root),
            "apps/api/pyproject.toml",
        )
        self.assertEqual(
            normalize_evidence_path("apps\\api\\pyproject.toml"),
            "apps/api/pyproject.toml",
        )

        ev = Evidence.from_source(
            Path("/tmp/project/apps/api/pyproject.toml"),
            "Found FastAPI in pyproject.toml",
            root=root,
            source_type=SourceType.DEPENDENCY,
            detector="framework.fastapi",
        )
        self.assertEqual(ev.portable_path(), "apps/api/pyproject.toml")

    def test_relative_evidence_path_rejects_escape_and_absolute_paths_outside_root(self):
        with self.assertRaises(ValueError):
            normalize_evidence_path("../outside/package.json")

        with self.assertRaises(ValueError):
            normalize_evidence_path("/etc/passwd", Path("/tmp/project"))

        with self.assertRaises(ValueError):
            Evidence.from_dict({"path": "/absolute/path/file.json", "reason": "Found file"})

    def test_normalize_facts_deduplicates_merges_evidence_and_keeps_strongest_confidence(self):
        f_env = ProjectFact(
            category="database",
            value="postgres",
            confidence=Confidence.LOW,
            evidence=(
                Evidence(
                    path=".env",
                    reason="Found DATABASE_URL key in .env",
                    source_type=SourceType.ENVIRONMENT_KEY,
                    detector="database.postgres",
                ),
            ),
            detector="database.postgres",
        )
        f_pkg = ProjectFact(
            category="database",
            value="postgres",
            confidence=Confidence.MEDIUM,
            evidence=(
                Evidence(
                    path="package.json",
                    reason="Found pg in package.json",
                    source_type=SourceType.DEPENDENCY,
                    detector="database.postgres",
                ),
            ),
            detector="database.postgres",
        )
        f_req = ProjectFact(
            category="database",
            value="postgres",
            confidence=Confidence.MEDIUM,
            evidence=(
                Evidence(
                    path="requirements.txt",
                    reason="Found psycopg in requirements.txt",
                    source_type=SourceType.DEPENDENCY,
                    detector="database.postgres",
                ),
                Evidence(
                    path="package.json",
                    reason="Found pg in package.json",
                    source_type=SourceType.DEPENDENCY,
                    detector="database.postgres",
                ),
            ),
            detector="database.postgres",
        )

        normalized = normalize_facts([f_env, f_pkg, f_req])

        self.assertEqual(len(normalized), 1)
        merged = normalized[0]
        self.assertEqual(merged.category, "database")
        self.assertEqual(merged.value, "postgres")
        self.assertEqual(merged.confidence, Confidence.MEDIUM)
        self.assertEqual(merged.detector, "database.postgres")
        self.assertEqual(
            [e.portable_path() for e in merged.evidence],
            [".env", "package.json", "requirements.txt"],
        )

    def test_normalize_facts_preserves_multiple_values_in_same_category_deterministically(self):
        fastapi = ProjectFact(
            category="framework",
            value="fastapi",
            confidence=Confidence.HIGH,
            evidence=(
                Evidence(
                    path="pyproject.toml",
                    reason="Found FastAPI",
                    source_type=SourceType.DEPENDENCY,
                ),
            ),
            detector="framework.fastapi",
        )
        nextjs = ProjectFact(
            category="framework",
            value="nextjs",
            confidence=Confidence.HIGH,
            evidence=(
                Evidence(
                    path="package.json",
                    reason="Found next",
                    source_type=SourceType.DEPENDENCY,
                ),
            ),
            detector="framework.nextjs",
        )

        forward = normalize_facts([nextjs, fastapi])
        backward = normalize_facts([fastapi, nextjs])

        self.assertEqual(forward, backward)
        self.assertEqual([f.value for f in forward], ["fastapi", "nextjs"])

    def test_project_model_roundtrip_serialization_and_query_methods(self):
        facts = (
            ProjectFact(
                category="language",
                value="python",
                confidence=Confidence.HIGH,
                evidence=(
                    Evidence(
                        path="pyproject.toml",
                        reason="Found Python project file",
                        source_type=SourceType.MANIFEST,
                        detector="language.python",
                    ),
                ),
                detector="language.python",
            ),
            ProjectFact(
                category="framework",
                value="fastapi",
                confidence=Confidence.HIGH,
                evidence=(
                    Evidence(
                        path="pyproject.toml",
                        reason="Found FastAPI in pyproject.toml",
                        source_type=SourceType.DEPENDENCY,
                        detector="framework.fastapi",
                    ),
                ),
                detector="framework.fastapi",
            ),
        )
        model = ProjectModel(root=Path("."), facts=facts)

        self.assertEqual(model.schema_version, PROJECT_MODEL_SCHEMA_VERSION)
        self.assertEqual(model.values("language"), ("python",))
        self.assertTrue(model.has("framework", "fastapi"))
        self.assertFalse(model.has("framework", "nextjs"))
        self.assertIsNotNone(model.fact("language", "python"))
        self.assertEqual(model.categories(), ("language", "framework"))

        as_dict = model.to_dict()
        self.assertEqual(as_dict["schema_version"], 1)
        self.assertNotIn("root", as_dict)

        as_json = model.to_json()
        parsed = json.loads(as_json)
        self.assertEqual(parsed, as_dict)

        restored_from_dict = ProjectModel.from_dict(as_dict)
        restored_from_json = ProjectModel.from_json(as_json)
        self.assertEqual(restored_from_dict, model)
        self.assertEqual(restored_from_json, model)

    def test_invalid_states_are_rejected(self):
        valid_evidence = (
            Evidence(
                path="package.json",
                reason="Found package",
                source_type=SourceType.MANIFEST,
            ),
        )

        with self.assertRaises(ValueError):
            ProjectFact(
                category="",
                value="python",
                confidence=Confidence.HIGH,
                evidence=valid_evidence,
                detector="language.python",
            )

        with self.assertRaises(ValueError):
            ProjectFact(
                category="language",
                value="python",
                confidence=Confidence.HIGH,
                evidence=(),
                detector="language.python",
            )

        with self.assertRaises(ValueError):
            ProjectFact(
                category="language",
                value="python",
                confidence=Confidence.HIGH,
                evidence=valid_evidence,
                detector="_detect_languages",
            )

        with self.assertRaises(ValueError):
            ProjectModel.from_dict({"schema_version": 999, "root": ".", "facts": []})

        self.assertEqual(
            canonical_detector_id("deploy_provider", "github-actions"),
            "deploy.github-actions",
        )


if __name__ == "__main__":
    unittest.main()
