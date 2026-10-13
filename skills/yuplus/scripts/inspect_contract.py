#!/usr/bin/env python3
"""Print a focused contract from installed Yu+ resources; never open a datastore."""
import argparse
import copy
from importlib.resources import files
import json

COMMANDS = {"source.import": "sourceImport", "draft.apply": "draftApply",
            "review.prepare": "reviewPrepare", "review.publish": "reviewPublish"}


def referenced_defs(value):
    if isinstance(value, dict):
        ref = value.get("$ref", "")
        if ref.startswith("#/$defs/"):
            yield ref.removeprefix("#/$defs/")
        for child in value.values():
            yield from referenced_defs(child)
    elif isinstance(value, list):
        for child in value:
            yield from referenced_defs(child)


def command_schema(contract, command, type_key):
    definitions = copy.deepcopy(contract["$defs"])
    if command == "draft.apply":
        operation = definitions["draftOperation"]
        operation["properties"]["type_key"]["enum"] = [type_key]
        operation["allOf"] = [condition for condition in operation["allOf"]
                              if condition["if"]["properties"]["type_key"]["const"] == type_key]
        if not operation["allOf"]:
            raise ValueError("Installed contract lacks the selected draft type rule")
    selected = {}
    pending = [COMMANDS[command]]
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected[name] = definitions[name]
        pending.extend(referenced_defs(selected[name]))
    return {"$schema": contract["$schema"], "$ref": "#/$defs/" + COMMANDS[command],
            "$defs": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="mode", required=True)
    subs.add_parser("type").add_argument("type_key")
    command = subs.add_parser("command")
    command.add_argument("command", choices=COMMANDS)
    command.add_argument("--type", dest="type_key")
    args = parser.parse_args()
    if args.mode == "command":
        if args.command == "draft.apply" and not args.type_key:
            parser.error("draft.apply requires --type; inspect only the types you need")
        if args.command != "draft.apply" and args.type_key:
            parser.error("--type is only supported for draft.apply")
    try:
        resources = files("yuplus").joinpath("contracts")
        catalog = json.loads(resources.joinpath("object-types.json").read_text(encoding="utf-8"))
        contract = json.loads(resources.joinpath("cli-input.schema.json").read_text(encoding="utf-8"))
        types = {entry["type_key"]: entry for entry in catalog["objects"] + catalog["internal_types"]}
        if args.type_key and args.type_key not in types:
            parser.error("Unknown installed type: " + args.type_key)
        if args.mode == "type":
            result = {"type": types[args.type_key],
                      "schema": contract["$defs"]["data_" + args.type_key]}
        else:
            result = {"command": args.command,
                      "schema": command_schema(contract, args.command, args.type_key)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ImportError, OSError, KeyError, ValueError) as exc:
        parser.error("Cannot read installed Yu+ contract; use its Python environment/help: " + str(exc))


if __name__ == "__main__":
    main()
