"""Acceptance checks through the public CLI, using isolated disposable data."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs/superpowers/specs/contracts/v0.1/examples"


def example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


class CliAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output_validator = Draft202012Validator(json.loads(
            (EXAMPLES.parent / "cli-output.schema.json").read_text(encoding="utf-8")))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="yu-cli-test-")
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "data"
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + self.env.get("PYTHONPATH", "")

    def invoke(self, *args, payload=None, raw=None, code=0):
        command = [sys.executable, "-m", "yuplus", "--data-dir", str(self.data_dir), *args, "--json"]
        if payload is not None:
            command.extend(["--input", "-"])
            raw = json.dumps(payload, ensure_ascii=False)
        run = subprocess.run(command, input=raw, text=True, capture_output=True, env=self.env, cwd=ROOT)
        self.assertEqual(run.returncode, code, f"{command}\nstdout={run.stdout}\nstderr={run.stderr}")
        try:
            result = json.loads(run.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"stdout is not one JSON response: {run.stdout!r}\nstderr={run.stderr}\n{exc}")
        self.assertEqual(result["api_version"], "1")
        self.assertEqual(result["ok"], code == 0)
        self.assertIn("meta", result)
        self.output_validator.validate(result)
        return result

    def project(self, request_id="project_first", name="城市展项目"):
        return self.invoke("project", "create", "--name", name, "--request-id", request_id)

    def write(self, project, command, payload, request, code=0):
        return self.invoke(*command.split("."), "--project", project, "--request-id", request,
                           payload=payload, code=code)

    def initial_chain(self):
        project = self.project()["data"]["project_id"]
        source_input = example("01-source-feishu.input.json")
        source = self.write(project, "source.import", source_input, "source_initial")
        draft_input = example("04-draft-initial.input.json")
        draft_input["objects"][0]["set_items"][0]["source_refs"][0]["source_version_id"] = source["data"]["snapshot_id"]
        draft = self.write(project, "draft.apply", draft_input, "draft_initial")
        budget = draft["data"]["objects"][0]
        prepare_input = example("05-review-prepare-initial.input.json")
        prepare_input["select_basis"][0]["object_id"] = budget["object_id"]
        prepared = self.invoke("review", "prepare", "--project", project, payload=prepare_input)
        self.assertEqual(prepared["data"]["read_basis"][0]["revision_id"], budget["revision_id"])
        self.assertIsNone(prepared["meta"]["change_id"])
        review_input = example("06-review-initial.input.json")
        document = review_input["documents"][0]
        document["read_basis"] = prepared["data"]["read_basis"]
        document["set_blocks"][0]["dependencies"][0].update(
            object_id=budget["object_id"], revision_id=budget["revision_id"])
        review = self.write(project, "review.publish", review_input, "review_initial")
        self.assertEqual(review["data"]["documents"][0]["version"], 1)
        return project, source, draft, review, review_input

    def test_project_is_persistent_and_create_is_idempotent(self):
        first = self.project()
        replay = self.project()
        self.assertEqual(first["data"], replay["data"])
        self.assertTrue(replay["meta"]["replayed"])
        second = self.project("project_second", "另一个项目")
        self.assertNotEqual(first["data"]["project_id"], second["data"]["project_id"])
        listing = self.invoke("project", "list")
        self.assertIn(first["data"]["project_id"], json.dumps(listing))
        self.assertIn(second["data"]["project_id"], json.dumps(listing))

    def test_budget_change_goes_through_draft_and_preserves_original(self):
        project, source, draft, review, _ = self.initial_chain()
        old_budget = draft["data"]["objects"][0]
        old_review = review["data"]["documents"][0]
        instruction = self.write(project, "source.import", example("03-source-oral.input.json"), "source_instruction")
        update = example("07-draft-budget-update.input.json")
        update["instruction_source_version_id"] = instruction["data"]["snapshot_id"]
        operation = update["objects"][0]
        operation.update(object_id=old_budget["object_id"], base_revision=old_budget["revision_id"])
        refs = operation["set_items"][0]["source_refs"]
        refs[0]["source_version_id"] = instruction["data"]["snapshot_id"]
        refs[1]["source_version_id"] = source["data"]["snapshot_id"]
        update["decisions"][0]["instruction_source_version_id"] = instruction["data"]["snapshot_id"]
        revised = self.write(project, "draft.apply", update, "draft_update")
        budget = revised["data"]["objects"][0]
        self.assertEqual(budget["version"], 2)
        self.assertEqual(revised["data"]["affected_reviews"][0]["block_ids"], ["budget"])

        publish = example("09-review-budget-update.input.json")
        document = publish["documents"][0]
        document["target"]["object_id"] = old_review["object_id"]
        document["base_revision"] = old_review["revision_id"]
        document["read_basis"] = [{"object_id": budget["object_id"], "revision_id": budget["revision_id"]}]
        block = document["set_blocks"][0]
        block["dependencies"][0].update(object_id=budget["object_id"], revision_id=budget["revision_id"])
        block["cause_change_ids"] = [revised["meta"]["change_id"]]
        published = self.write(project, "review.publish", publish, "review_update")
        self.assertEqual(published["data"]["documents"][0]["version"], 2)
        replay = self.write(project, "review.publish", publish, "review_update")
        self.assertTrue(replay["meta"]["replayed"])
        self.assertEqual(replay["data"], published["data"])

        original = self.invoke("source", "show", "--project", project, "--source", source["data"]["source_id"],
                               "--snapshot", source["data"]["snapshot_id"], "--include-body")
        self.assertIn("100 万", json.dumps(original, ensure_ascii=False))
        old = self.invoke("draft", "show", "--project", project, "--object", budget["object_id"],
                          "--revision", old_budget["revision_id"])
        self.assertIn("100000000", json.dumps(old))
        current = self.invoke("review", "show", "--project", project, "--object", old_review["object_id"])
        self.assertIn("60 万", json.dumps(current, ensure_ascii=False))
        decisions = self.invoke("decisions", "list", "--project", project)
        self.assertIn("60 万元", json.dumps(decisions, ensure_ascii=False))

    def test_review_cannot_be_rewritten_without_new_draft_cause(self):
        project, _, _, review, initial_input = self.initial_chain()
        changed = copy.deepcopy(initial_input)
        doc = changed["documents"][0]
        doc["target"]["object_id"] = review["data"]["documents"][0]["object_id"]
        doc["base_revision"] = review["data"]["documents"][0]["revision_id"]
        doc.pop("title")
        doc["set_blocks"][0]["markdown"] = "把预算改成 60 万。"
        rejected = self.write(project, "review.publish", changed, "review_without_cause", code=5)
        self.assertEqual(rejected["error"]["code"], "DRAFT_CHANGE_REQUIRED")

    def test_local_file_is_copied_and_replay_does_not_reread_it(self):
        project = self.project()["data"]["project_id"]
        original = Path(self.temp.name) / "场地 资料.txt"
        original.write_text("展厅位于一层。\n", encoding="utf-8")
        request = example("02-source-local.input.json")
        asset = request["snapshot"]["assets"][0]
        asset.update(local_path=str(original), display_name=original.name, mime_type="text/plain")
        first = self.write(project, "source.import", request, "local_file")
        original.unlink()
        replay = self.write(project, "source.import", request, "local_file")
        self.assertTrue(replay["meta"]["replayed"])
        self.assertEqual(first["data"], replay["data"])
        sha = first["data"]["assets"][0]["sha256"]
        matches = list(self.data_dir.rglob(sha))
        self.assertTrue(matches, "the local original should survive in the content-addressed pool")
        self.assertEqual(matches[0].read_text(encoding="utf-8"), "展厅位于一层。\n")

    def test_project_isolation_rejects_foreign_evidence(self):
        first = self.project()["data"]["project_id"]
        second = self.project("project_second", "另一个项目")["data"]["project_id"]
        source = self.write(first, "source.import", example("03-source-oral.input.json"), "oral")
        request = example("04-draft-initial.input.json")
        request["objects"][0]["set_items"][0]["source_refs"][0]["source_version_id"] = source["data"]["snapshot_id"]
        rejected = self.write(second, "draft.apply", request, "foreign_evidence", code=5)
        self.assertEqual(rejected["error"]["code"], "CROSS_PROJECT_REFERENCE")

    def test_malformed_json_is_a_json_error(self):
        result = self.invoke("source", "import", "--project", "prj_missing", "--request-id", "bad_json",
                             "--input", "-", raw="{", code=2)
        self.assertEqual(result["error"]["code"], "INVALID_INPUT")

    def test_duplicate_keys_and_nonfinite_numbers_are_rejected(self):
        for raw in ['{"api_version":"1","api_version":"2"}', '{"number":NaN}', '{"number":Infinity}']:
            with self.subTest(raw=raw):
                result = self.invoke("source", "import", "--project", "prj_missing", "--request-id", "bad_json",
                                     "--input", "-", raw=raw, code=2)
                self.assertEqual(result["error"]["code"], "INVALID_INPUT")

    def test_missing_parameter_is_a_json_error(self):
        result = self.invoke("project", "create", "--request-id", "missing_name", code=2)
        self.assertEqual(result["error"]["code"], "INVALID_INPUT")

    def test_input_file_and_flags_after_subcommand_work(self):
        project = self.project()["data"]["project_id"]
        input_file = Path(self.temp.name) / "输入 内容.json"
        input_file.write_text(json.dumps(example("03-source-oral.input.json"), ensure_ascii=False), encoding="utf-8")
        result = self.invoke("source", "import", "--project", project, "--request-id", "input_file",
                             "--input", str(input_file))
        self.assertEqual(result["command"], "source.import")
        self.assertEqual(result["data"]["effect"], "changed")

    def test_business_fields_can_be_incomplete(self):
        project = self.project()["data"]["project_id"]
        request = {
            "api_version": "1", "command": "draft.apply", "reason": "先记录一个待讨论问题",
            "objects": [{
                "op_id": "context", "type_key": "bd_context", "scope_key": "project", "base_revision": None,
                "set_items": [{"item_id": "question", "data": {"core_problem": "如何让观众理解这段历史？"},
                               "epistemic_kind": "hypothesis", "source_refs": [], "dependencies": []}],
            }],
            "decisions": [],
        }
        result = self.write(project, "draft.apply", request, "partial_draft")
        self.assertEqual(result["data"]["objects"][0]["version"], 1)

    def test_write_flags_can_precede_the_command(self):
        project = self.project()["data"]["project_id"]
        result = self.invoke("--project", project, "--request-id", "flags_before", "source", "import",
                             payload=example("03-source-oral.input.json"))
        self.assertEqual(result["command"], "source.import")

    def test_corrupt_database_reports_json_and_preserves_original_bytes(self):
        self.data_dir.mkdir()
        original=b'not a sqlite database'
        (self.data_dir/'yuplus.sqlite').write_bytes(original)
        result=self.invoke('project','list',code=70)
        self.assertEqual(result['error']['code'],'INTEGRITY_FAILURE')
        self.assertEqual((self.data_dir/'yuplus.sqlite').read_bytes(),original)

    def test_source_query_returns_metadata_unless_body_requested(self):
        project=self.project()['data']['project_id']
        request=example('03-source-oral.input.json')
        source=self.write(project,'source.import',request,'source_body')['data']['source_id']
        metadata=self.invoke('source','show','--project',project,'--source',source)
        self.assertTrue(metadata['data']['snapshot']['body_omitted'])
        self.assertIsNone(metadata['data']['snapshot']['body'])
        full=self.invoke('source','show','--project',project,'--source',source,'--include-body')
        self.assertEqual(full['data']['snapshot']['body']['text'],request['snapshot']['body']['text'])


if __name__ == "__main__":
    unittest.main()
