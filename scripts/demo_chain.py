#!/usr/bin/env python3
"""Run the budget example through real CLI subprocesses; no external network calls."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs/superpowers/specs/contracts/v0.1/examples"


def example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


class Demo:
    def __init__(self, data_dir: Path, cli: str | None = None):
        self.data_dir = data_dir
        self.cli = [cli] if cli else [sys.executable, "-m", "yuplus"]
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + self.env.get("PYTHONPATH", "")
        self.prefix = "demo_" + uuid.uuid4().hex[:12]
        self.project_id = None

    def call(self, command: str, *, request: dict | None = None,
             key: str | None = None, flags: tuple[str, ...] = (), expected_code: int = 0) -> dict:
        args = [*self.cli, "--data-dir", str(self.data_dir), *command.split("."), "--json", *flags]
        if self.project_id:
            args += ["--project", self.project_id]
        if key:
            args += ["--request-id", f"{self.prefix}_{key}"]
        if request is not None:
            args += ["--input", "-"]
        run = subprocess.run(args, input=json.dumps(request, ensure_ascii=False) if request is not None else None,
                             text=True, capture_output=True, env=self.env, cwd=ROOT)
        try:
            result = json.loads(run.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{command} 没有返回 JSON：{run.stdout}\n{run.stderr}") from exc
        if run.returncode != expected_code or result["ok"] != (expected_code == 0):
            raise RuntimeError(f"{command} 返回 {run.returncode}，预期 {expected_code}：\n"
                               + json.dumps(result, ensure_ascii=False, indent=2))
        return result

    def run(self) -> dict:
        project = self.call("project.create", key="project", flags=("--name", "Yu+ 最小链路演示"))
        self.project_id = project["data"]["project_id"]
        print(f"1. 已创建独立演示项目：{self.project_id}")

        source = self.call("source.import", request=example("01-source-feishu.input.json"), key="source")
        source_id = source["data"]["source_id"]
        source_version = source["data"]["snapshot_id"]
        print("2. 已收录模拟飞书材料：客户预算 100 万（仅保存示例文本，不访问飞书）。")

        draft_request = example("04-draft-initial.input.json")
        draft_request["objects"][0]["set_items"][0]["source_refs"][0]["source_version_id"] = source_version
        draft = self.call("draft.apply", request=draft_request, key="draft_initial")
        budget = draft["data"]["objects"][0]

        prepare_request = example("05-review-prepare-initial.input.json")
        prepare_request["select_basis"][0]["object_id"] = budget["object_id"]
        prepared = self.call("review.prepare", request=prepare_request)
        review_request = example("06-review-initial.input.json")
        doc = review_request["documents"][0]
        doc["read_basis"] = prepared["data"]["read_basis"]
        doc["set_blocks"][0]["dependencies"][0].update(object_id=budget["object_id"], revision_id=budget["revision_id"])
        review = self.call("review.publish", request=review_request, key="review_initial")
        first_review = review["data"]["documents"][0]
        print("3. 已建立预算 draft，并生成依赖该条目的第一版 Debrief。")

        direct_rewrite = copy.deepcopy(review_request)
        direct_doc = direct_rewrite["documents"][0]
        direct_doc.pop("title")
        direct_doc["target"]["object_id"] = first_review["object_id"]
        direct_doc["base_revision"] = first_review["revision_id"]
        direct_doc["set_blocks"][0]["markdown"] = "现在直接写成 60 万。"
        refusal = self.call("review.publish", request=direct_rewrite, key="rejected_rewrite", expected_code=5)
        if refusal["error"]["code"] != "DRAFT_CHANGE_REQUIRED":
            raise RuntimeError("直接改成果应返回 DRAFT_CHANGE_REQUIRED。")
        print("4. 验证通过：未先修改 draft，CLI 拒绝直接改写 review。")

        instruction = self.call("source.import", request=example("03-source-oral.input.json"), key="instruction")
        instruction_version = instruction["data"]["snapshot_id"]
        update_request = example("07-draft-budget-update.input.json")
        update_request["instruction_source_version_id"] = instruction_version
        operation = update_request["objects"][0]
        operation.update(object_id=budget["object_id"], base_revision=budget["revision_id"])
        operation["set_items"][0]["source_refs"][0]["source_version_id"] = instruction_version
        operation["set_items"][0]["source_refs"][1]["source_version_id"] = source_version
        update_request["decisions"][0]["instruction_source_version_id"] = instruction_version
        revised = self.call("draft.apply", request=update_request, key="draft_update")
        budget_new = revised["data"]["objects"][0]
        if not revised["data"]["affected_reviews"]:
            raise RuntimeError("预算变化没有返回受影响成果。")
        print("5. 已保存用户原话、把 draft 改为采用 60 万并记录决策；旧成果被识别为受影响。")

        prepare_request["target"]["object_id"] = first_review["object_id"]
        prepare_request["cause_change_ids"] = [revised["meta"]["change_id"]]
        prepared_new = self.call("review.prepare", request=prepare_request)
        updated_review = example("09-review-budget-update.input.json")
        updated_doc = updated_review["documents"][0]
        updated_doc["target"]["object_id"] = first_review["object_id"]
        updated_doc["base_revision"] = first_review["revision_id"]
        updated_doc["read_basis"] = prepared_new["data"]["read_basis"]
        block = updated_doc["set_blocks"][0]
        block["dependencies"][0].update(object_id=budget_new["object_id"], revision_id=budget_new["revision_id"])
        block["cause_change_ids"] = [revised["meta"]["change_id"]]
        published = self.call("review.publish", request=updated_review, key="review_update")
        replay = self.call("review.publish", request=updated_review, key="review_update")
        if not replay["meta"]["replayed"] or published["data"] != replay["data"]:
            raise RuntimeError("同一请求没有正确重放原回执。")
        print("6. 已根据 draft 变更发布第二版 Debrief；重复提交返回原回执。")

        with tempfile.TemporaryDirectory(prefix="yu-demo-source-") as input_dir:
            original = Path(input_dir) / "场地资料.txt"
            original.write_text("场地位于展厅一层。\n", encoding="utf-8")
            local_request = example("02-source-local.input.json")
            local_request["snapshot"]["title"] = original.name
            local_request["snapshot"]["provenance"]["method"] = "plain-text-read"
            local_request["snapshot"]["assets"][0].update(
                local_path=str(original), display_name=original.name, mime_type="text/plain")
            local_result = self.call("source.import", request=local_request, key="local_source")
            original.unlink()
            local_replay = self.call("source.import", request=local_request, key="local_source")
            if local_replay["data"] != local_result["data"] or not local_replay["meta"]["replayed"]:
                raise RuntimeError("原始路径已删除后的重放失败。")
        print("7. 已复制本地文件到对象池；原路径删除后，重复导入仍正确返回旧回执。")

        original_source = self.call("source.show", flags=("--source", source_id, "--snapshot", source_version, "--include-body"))
        old_draft = self.call("draft.show", flags=("--object", budget["object_id"], "--revision", budget["revision_id"]))
        current_review = self.call("review.show", flags=("--object", first_review["object_id"]))
        decisions = self.call("decisions.list")
        if ("100 万" not in json.dumps(original_source, ensure_ascii=False)
                or "100000000" not in json.dumps(old_draft)
                or "60 万" not in json.dumps(current_review, ensure_ascii=False)
                or "60 万元" not in json.dumps(decisions, ensure_ascii=False)):
            raise RuntimeError("历史来源、历史 draft、当前成果或决策查询结果不符合预期。")
        print("8. 已核对原始 100 万材料、旧 draft、当前 60 万成果及长期决策记录。")
        return {
            "project_id": self.project_id,
            "source_id": source_id,
            "original_snapshot_id": source_version,
            "draft_object_id": budget["object_id"],
            "draft_revision_id": budget_new["revision_id"],
            "review_object_id": first_review["object_id"],
            "review_revision_id": published["data"]["documents"][0]["revision_id"],
            "data_dir": str(self.data_dir),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path,
                        help="保留演示数据库与对象池的目录；省略时在临时目录运行，结束后自动清理。")
    parser.add_argument("--cli", help="可选：指定已安装的 yu 可执行文件；默认调用当前 Python 的 yuplus 模块。")
    args = parser.parse_args()
    try:
        if args.data_dir is not None:
            result = Demo(args.data_dir.expanduser().resolve(), args.cli).run()
            print("\n演示完成，数据已保留：")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            with tempfile.TemporaryDirectory(prefix="yu-demo-") as temp:
                result = Demo(Path(temp), args.cli).run()
            result.pop("data_dir")
            print("\n演示完成，临时数据已自动清理。加 --data-dir 可保留供后续 CLI 查看。")
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, RuntimeError, KeyError) as exc:
        print(f"演示失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
