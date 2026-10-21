"""The skill's read-only helper must expose executable, type-scoped contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills/yuplus/scripts/inspect_contract.py"
EXAMPLES = ROOT / "docs/superpowers/specs/contracts/v0.1/examples"


class SkillContractTests(unittest.TestCase):
    def test_human_chinese_review_copies_are_not_installable_or_routed(self):
        self.assertTrue(list((ROOT/'docs/skills').rglob('*.zh-CN.md')))
        for path in (ROOT/'skills').rglob('*'):
            self.assertNotIn('zh-CN',path.name)
            if path.suffix=='.md':
                text=path.read_text()
                self.assertNotIn('docs/skills',text)
                self.assertNotIn('.zh-CN.md',text)
        installer=(ROOT/'scripts/install.py').read_text()
        self.assertIn("shutil.copytree(repo/'skills'/name",installer)
        self.assertNotIn("repo/'docs'",installer)

    def run_helper(self, *args):
        return subprocess.run([sys.executable, str(HELPER), *args],
                              capture_output=True, text=True, cwd=ROOT)

    def output(self, *args):
        result = self.run_helper(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_type_exposes_meaning_and_only_selected_data(self):
        result = self.output("type", "budget_range")
        self.assertEqual(result["type"]["code"], "D07")
        self.assertIn("possible_sources", result["type"])
        self.assertIn("currency", result["schema"]["properties"])
        self.assertNotIn("data_venue", json.dumps(result))

    def test_scoped_schemas_validate_real_examples(self):
        cases = [("source.import", None, "01-source-feishu"),
                 ("source.import", None, "02-source-local"),
                 ("source.import", None, "03-source-oral"),
                 ("draft.apply", "budget_range", "04-draft-initial"),
                 ("draft.apply", "expression_guide", "12-draft-expression-guide"),
                 ("review.prepare", None, "05-review-prepare-initial"),
                 ("review.publish", None, "06-review-initial")]
        for command, type_key, name in cases:
            with self.subTest(name=name):
                args = ["command", command]
                if type_key:
                    args += ["--type", type_key]
                schema = self.output(*args)["schema"]
                Draft202012Validator.check_schema(schema)
                payload = json.loads((EXAMPLES / (name + ".input.json")).read_text())
                Draft202012Validator(schema).validate(payload)
                if type_key:
                    self.assertEqual([k for k in schema["$defs"] if k.startswith("data_")],
                                     ["data_" + type_key])
                    wrong = copy.deepcopy(payload)
                    wrong["objects"][0]["type_key"] = "venue"
                    self.assertFalse(Draft202012Validator(schema).is_valid(wrong))

    def test_invalid_requests_fail_without_json_success(self):
        for args in [("type", "imaginary"), ("command", "draft.apply"),
                     ("command", "source.check"),
                     ("command", "source.import", "--type", "budget_range")]:
            with self.subTest(args=args):
                result = self.run_helper(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertTrue(result.stderr)
