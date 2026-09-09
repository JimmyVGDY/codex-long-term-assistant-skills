from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from documentation import DocumentationError, audit, load_catalog, rewrite_links


class DocumentationSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cp-doc-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("manifest.json", {"version": "7.6.1"})
        self.write("hooks/hooks.json", {"hooks": {"Stop": [], "Interrupt": []}})
        self.write("docs/GUIDE.md", "# 当前指南\n")
        self.write("locales/en/docs/GUIDE.md", "# Current guide\n\n[Other](OTHER.md)\n")
        self.write("locales/en/docs/OTHER.md", "# Other\n")
        self.write("README.md", "<!-- cp-fact:hook-count -->2<!-- /cp-fact -->\n")
        self.catalog = {
            "schema_version": 1,
            "documents": [{"path": "docs/GUIDE.md", "status": "active", "english_source": "locales/en/docs/GUIDE.md"}],
            "english_projections": [{"source": "locales/en/docs/GUIDE.md", "target": "docs/GUIDE.en.md"}],
            "fact_files": {"README.md": ["hook-count"]}, "aliases": [],
        }
        self.write("config/documentation.json", self.catalog)

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value, encoding="utf-8")

    def codes(self):
        return {item["code"] for item in audit(self.root)["findings"]}

    def test_generation_is_idempotent_and_projects_existing_english_links(self):
        first = audit(self.root, write=True)
        self.assertTrue(first["ok"])
        self.assertEqual(["docs/GUIDE.en.md"], first["updated"])
        self.assertIn("../locales/en/docs/OTHER.md", (self.root / "docs/GUIDE.en.md").read_text())
        self.assertEqual([], audit(self.root, write=True)["updated"])
        self.assertTrue(audit(self.root)["ok"])

    def test_manual_edit_of_generated_copy_is_detected_and_rebuilt(self):
        audit(self.root, write=True)
        self.write("docs/GUIDE.en.md", "# Missing operating requirements\n")
        self.assertIn("ENGLISH_PROJECTION_DRIFT", self.codes())
        audit(self.root, write=True)
        self.assertTrue(audit(self.root)["ok"])

    def test_hook_registry_change_invalidates_count_until_regenerated(self):
        audit(self.root, write=True)
        self.write("hooks/hooks.json", {"hooks": {"Stop": [], "Interrupt": [], "UserPromptSubmit": []}})
        self.assertIn("FACT_DRIFT", self.codes())
        audit(self.root, write=True)
        self.assertIn("-->3<!--", (self.root / "README.md").read_text())

    def test_deleted_fact_marker_cannot_silently_disable_check(self):
        self.write("README.md", "2 Hooks\n")
        self.assertIn("FACT_MARKER_MISSING", self.codes())
        self.assertFalse(audit(self.root, write=True)["ok"])

    def test_removing_only_one_of_multiple_required_facts_is_detected(self):
        self.catalog["fact_files"]["README.md"].append("package-version")
        self.write("config/documentation.json", self.catalog)
        self.assertIn("FACT_MARKER_MISSING", self.codes())

    def contract_fixture(self):
        manifest = {
            "version": "7.6.1",
            "quality_limits": {"task_execution_envelope_schema_version": 3, "execution_state_schema_version": 4,
                               "review_state_schema_version": 7, "review_result_schema_version": 4,
                               "delegation_budget_schema_version": "2.0"},
            "execution_determinism": {"task_envelope": "template.yaml", "guard": "guard.py",
                                      "review_controller": "review.py", "project_runtime": "runtime"},
            "model_routing": {"delegation_budget": {"accounting_owner": "delegation-budget-v2"}},
            "authority_registry": {"delegation_budget": "external DelegationBudget V2 JSONL",
                                   "review_dispatch_state": "review-state.json via review_controller.py"},
        }
        self.write("manifest.json", manifest)
        self.write("template.yaml", "schema_version: 3\n")
        self.write("guard.py", "SCHEMA = 4\n")
        self.write("review.py", "SCHEMA_VERSION = 7\n")
        self.write("runtime/delegation_budget.py", 'SCHEMA_VERSION = "2.0"\n')
        self.write("skills/multi-agent-independent-review/assets/schemas/review-result.schema.json",
                   {"properties": {"schema_version": {"const": 4}}})
        return manifest

    def test_schema_change_requires_matching_manifest_before_regenerating(self):
        manifest = self.contract_fixture()
        self.assertTrue(audit(self.root, write=True)["ok"])
        self.write("guard.py", "SCHEMA = 5\n")
        self.assertIn("SCHEMA_DECLARATION_DRIFT", self.codes())
        manifest["quality_limits"]["execution_state_schema_version"] = 5
        self.write("manifest.json", manifest)
        self.assertTrue(audit(self.root)["ok"])

    def test_stale_budget_owner_is_rejected_even_when_documents_agree(self):
        manifest = self.contract_fixture()
        manifest["model_routing"]["delegation_budget"]["accounting_owner"] = "delegation-budget-v1"
        manifest["authority_registry"]["delegation_budget"] = "external DelegationBudget V1 JSONL"
        self.write("manifest.json", manifest)
        self.assertIn("AUTHORITY_DRIFT", self.codes())

    def test_duplicate_json_keys_cannot_override_document_policy(self):
        self.write("config/documentation.json", '{"schema_version":1,"schema_version":2}')
        with self.assertRaisesRegex(DocumentationError, "duplicate JSON key"):
            load_catalog(self.root)

    def alias_fixture(self):
        self.write("docs/operations/GUIDE.md", '# Current guide\n\n## Existing anchor\n\n[Other](../OTHER.md#part "Title")\n```text\n[Example](../OTHER.md)\n```\n')
        self.write("locales/en/docs/operations/GUIDE.md", "# Current guide\n")
        self.catalog["documents"][0]["status"] = "generated"
        self.catalog["documents"].append({"path": "docs/operations/GUIDE.md", "status": "active", "english_source": "locales/en/docs/operations/GUIDE.md"})
        self.catalog["aliases"] = [{"source": "docs/GUIDE.md", "target": "docs/operations/GUIDE.md"}]
        self.write("config/documentation.json", self.catalog)

    def test_compatibility_copy_retains_anchors_and_rebases_links(self):
        self.alias_fixture()
        self.assertTrue(audit(self.root, write=True)["ok"])
        text = (self.root / "docs/GUIDE.md").read_text(encoding="utf-8")
        self.assertIn('## Existing anchor', text)
        self.assertIn('[Other](OTHER.md#part "Title")', text)
        self.assertIn('[Example](../OTHER.md)', text)
        self.assertEqual([], audit(self.root, write=True)["updated"])
        self.write("docs/GUIDE.md", "# Independent stale copy\n")
        self.assertIn("COMPATIBILITY_COPY_DRIFT", self.codes())

    def test_alias_cycles_and_multiple_writers_are_rejected(self):
        self.alias_fixture()
        self.catalog["aliases"].append({"source": "docs/operations/GUIDE.md", "target": "docs/GUIDE.md"})
        self.write("config/documentation.json", self.catalog)
        with self.assertRaisesRegex(DocumentationError, "chains and cycles"):
            load_catalog(self.root)
        self.catalog["aliases"].pop()
        self.catalog["fact_files"]["docs/GUIDE.md"] = ["package-version"]
        self.write("config/documentation.json", self.catalog)
        with self.assertRaisesRegex(DocumentationError, "another writer"):
            load_catalog(self.root)

    def test_current_migration_and_title_errors_fail_but_history_remains_original(self):
        self.write("docs/GUIDE.md", "# V7.4 Current guide\nV7.6.2 及更早版本\n")
        self.assertTrue({"CURRENT_TITLE_VERSION", "MIGRATION_SOURCE_DRIFT"}.issubset(self.codes()))
        self.catalog["documents"][0]["status"] = "historical"
        self.write("config/documentation.json", self.catalog)
        self.assertFalse({"CURRENT_TITLE_VERSION", "MIGRATION_SOURCE_DRIFT"}.intersection(self.codes()))

    def test_new_document_requires_owner_and_status_registration(self):
        self.write("docs/NEW.md", "# New\n")
        self.assertIn("UNREGISTERED_DOCUMENT", self.codes())

    def test_duplicate_projection_and_external_path_are_rejected(self):
        self.catalog["english_projections"].append(self.catalog["english_projections"][0])
        self.write("config/documentation.json", self.catalog)
        with self.assertRaises(DocumentationError):
            load_catalog(self.root)
        self.catalog["english_projections"] = [{"source": "locales/en/../../escape.md", "target": "docs/out.en.md"}]
        self.write("config/documentation.json", self.catalog)
        with self.assertRaises(DocumentationError):
            load_catalog(self.root)

    def test_link_projection_preserves_nested_fences(self):
        source = "[link](old.md)\n````text\n```\n[example](old.md)\n```\n````\n<a href=\"old.md\">link</a>\n"
        result = rewrite_links(source, lambda value: "new.md")
        self.assertIn("[link](new.md)", result)
        self.assertIn("[example](old.md)", result)
        self.assertIn('href="new.md"', result)

    def test_inline_examples_are_preserved_and_only_link_destinations_are_transformed(self):
        source = ('`[example](old.md)` and ``[example ` nested](old.md)``\n'
                  '[actual](old.md#part "Link title") and [angle](<old.md> \'Title\')\n'
                  '`<a href="old.md">example</a>` <a href="old.md">actual</a>\n')
        seen = []

        def transform(value):
            seen.append(value)
            return value.replace("old.md", "new.md")

        rendered = rewrite_links(source, transform)
        self.assertEqual(["old.md#part", "old.md", "old.md"], seen)
        self.assertIn('`[example](old.md)`', rendered)
        self.assertIn('``[example ` nested](old.md)``', rendered)
        self.assertIn('[actual](new.md#part "Link title")', rendered)
        self.assertIn('[angle](<new.md> \'Title\')', rendered)
        self.assertIn('`<a href="old.md">example</a>`', rendered)

    def test_english_projection_resolves_titled_links_without_changing_examples(self):
        self.write("locales/en/docs/GUIDE.md", '# Guide\n\n[Other](OTHER.md#part "Title")\n`[Example](OTHER.md)`\n')
        self.assertTrue(audit(self.root, write=True)["ok"])
        rendered = (self.root / "docs/GUIDE.en.md").read_text(encoding="utf-8")
        self.assertIn('[Other](../locales/en/docs/OTHER.md#part "Title")', rendered)
        self.assertIn('`[Example](OTHER.md)`', rendered)
        self.assertEqual([], audit(self.root, write=True)["updated"])


if __name__ == "__main__":
    unittest.main()
