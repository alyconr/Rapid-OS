import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.scope import (
    NOT_SPECIFIED,
    ScopeSpec,
    normalize_mode,
    parse_list,
    render_acceptance,
    render_scope_artifacts,
    render_specs,
    render_tasks,
    write_scope_artifacts,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


def sample_spec():
    return ScopeSpec(
        initiative_name="Checkout Flow",
        mode="new feature",
        business_objective="Increase completed purchases",
        problem_statement="Users abandon checkout before payment",
        scope=["Add payment step", "Send receipt email"],
        out_of_scope=["Subscriptions"],
        actors_users=["Shopper", "Admin"],
        main_flow=["Shopper opens cart", "Shopper pays"],
        edge_cases=["Payment declined", "Email service unavailable"],
        business_rules=["Orders require payment confirmation"],
        technical_constraints=["Use existing payment provider"],
        affected_files_modules=["checkout.py", "payments.py"],
        data_impact="Adds order receipt timestamp",
        acceptance_criteria=["Payment creates order", "Receipt email is queued"],
        testing_strategy=["Unit test payment service", "Integration test checkout"],
        implementation_tasks=["Create payment endpoint", "Queue receipt email"],
    )


class ScopeSpecTests(unittest.TestCase):
    def test_mode_normalization_supports_expected_modes_and_aliases(self):
        self.assertEqual(normalize_mode("1"), "new feature")
        self.assertEqual(normalize_mode("feature"), "new feature")
        self.assertEqual(normalize_mode("2"), "refactor")
        self.assertEqual(normalize_mode("refactoring"), "refactor")
        self.assertEqual(normalize_mode("3"), "bugfix")
        self.assertEqual(normalize_mode("fix"), "bugfix")
        self.assertEqual(normalize_mode("4"), "legacy hardening")
        self.assertEqual(normalize_mode("legacy"), "legacy hardening")
        self.assertEqual(normalize_mode("unknown"), "new feature")

    def test_list_parsing_supports_commas_and_semicolons(self):
        self.assertEqual(
            parse_list("alpha, beta; gamma ,, ; delta"),
            ["alpha", "beta", "gamma", "delta"],
        )
        self.assertEqual(parse_list("   "), [])

    def test_render_specs_exact_content(self):
        self.assertEqual(
            render_specs(sample_spec()),
            "# SPEC: Checkout Flow\n\n"
            "## Mode\nnew feature\n\n"
            "## Business Objective\nIncrease completed purchases\n\n"
            "## Problem Statement\nUsers abandon checkout before payment\n\n"
            "## Scope\n- Add payment step\n- Send receipt email\n\n"
            "## Out of Scope\n- Subscriptions\n\n"
            "## Actors / Users\n- Shopper\n- Admin\n\n"
            "## Main Flow\n- Shopper opens cart\n- Shopper pays\n\n"
            "## Edge Cases\n- Payment declined\n- Email service unavailable\n\n"
            "## Business Rules\n- Orders require payment confirmation\n\n"
            "## Technical Constraints\n- Use existing payment provider\n\n"
            "## Affected Files / Modules\n- checkout.py\n- payments.py\n\n"
            "## Data Impact\nAdds order receipt timestamp",
        )

    def test_render_tasks_exact_content(self):
        self.assertEqual(
            render_tasks(sample_spec()),
            "# TASKS: Checkout Flow\n\n"
            "## Implementation Tasks\n"
            "- [ ] Create payment endpoint\n"
            "- [ ] Queue receipt email\n\n"
            "## Execution Notes\n"
            "- Work from `SPECS.md` as the source of scope.\n"
            "- Validate each task against `ACCEPTANCE.md`.\n"
            "- Keep implementation changes inside the documented scope.",
        )

    def test_render_acceptance_exact_content(self):
        self.assertEqual(
            render_acceptance(sample_spec()),
            "# ACCEPTANCE: Checkout Flow\n\n"
            "## Acceptance Criteria\n"
            "- [ ] Payment creates order\n"
            "- [ ] Receipt email is queued\n\n"
            "## Testing Strategy\n"
            "- Unit test payment service\n"
            "- Integration test checkout\n\n"
            "## Definition of Done\n"
            "- [ ] Acceptance criteria reviewed\n"
            "- [ ] Testing strategy completed or explicitly deferred\n"
            "- [ ] Implementation matches `SPECS.md`\n"
            "- [ ] Tasks in `TASKS.md` are complete or intentionally deferred",
        )

    def test_blank_fields_render_as_not_specified(self):
        spec = ScopeSpec(
            initiative_name="",
            mode="",
            business_objective="",
            problem_statement="",
            scope=[],
            out_of_scope=[],
            actors_users=[],
            main_flow=[],
            edge_cases=[],
            business_rules=[],
            technical_constraints=[],
            affected_files_modules=[],
            data_impact="",
            acceptance_criteria=[],
            testing_strategy=[],
            implementation_tasks=[],
        )

        self.assertIn(f"# SPEC: {NOT_SPECIFIED}", render_specs(spec))
        self.assertIn(f"## Scope\n{NOT_SPECIFIED}", render_specs(spec))
        self.assertIn(f"## Data Impact\n{NOT_SPECIFIED}", render_specs(spec))
        self.assertIn(f"## Implementation Tasks\n{NOT_SPECIFIED}", render_tasks(spec))
        self.assertIn(
            f"## Acceptance Criteria\n{NOT_SPECIFIED}",
            render_acceptance(spec),
        )
        self.assertIn(
            f"## Testing Strategy\n{NOT_SPECIFIED}",
            render_acceptance(spec),
        )

    def test_blank_list_items_are_ignored_before_rendering(self):
        spec = ScopeSpec(
            initiative_name="Whitespace Lists",
            mode="refactor",
            business_objective="Keep artifacts clean",
            problem_statement="Blank list items should not render as empty bullets",
            scope=["  ", "Keep this"],
            out_of_scope=[""],
            actors_users=[],
            main_flow=[],
            edge_cases=[],
            business_rules=[],
            technical_constraints=[],
            affected_files_modules=[],
            data_impact="",
            acceptance_criteria=["  ", "Reviewed"],
            testing_strategy=["  "],
            implementation_tasks=["", "Ship cleanup"],
        )

        self.assertIn("## Scope\n- Keep this", render_specs(spec))
        self.assertIn(f"## Out of Scope\n{NOT_SPECIFIED}", render_specs(spec))
        self.assertIn(
            "## Acceptance Criteria\n- [ ] Reviewed",
            render_acceptance(spec),
        )
        self.assertIn(
            f"## Testing Strategy\n{NOT_SPECIFIED}",
            render_acceptance(spec),
        )
        self.assertIn(
            "## Implementation Tasks\n- [ ] Ship cleanup",
            render_tasks(spec),
        )

    def test_write_scope_artifacts_creates_all_files(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)

            written = write_scope_artifacts(sample_spec(), current_dir)

            self.assertEqual(
                [path.name for path in written],
                ["SPECS.md", "TASKS.md", "ACCEPTANCE.md"],
            )
            self.assertTrue((current_dir / "SPECS.md").exists())
            self.assertTrue((current_dir / "TASKS.md").exists())
            self.assertTrue((current_dir / "ACCEPTANCE.md").exists())

            for filename, content in render_scope_artifacts(sample_spec()).items():
                self.assertEqual(
                    (current_dir / filename).read_text(encoding="utf-8"),
                    content,
                )

    def test_write_scope_artifacts_creates_backups_when_files_exist(self):
        with workspace_tempdir() as tmp:
            current_dir = Path(tmp)
            for filename in ("SPECS.md", "TASKS.md", "ACCEPTANCE.md"):
                (current_dir / filename).write_text("old", encoding="utf-8")

            write_scope_artifacts(sample_spec(), current_dir)

            for filename in ("SPECS.md", "TASKS.md", "ACCEPTANCE.md"):
                backups = list(current_dir.glob(f"{filename}.*.bak"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
