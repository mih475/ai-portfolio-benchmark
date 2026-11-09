"""Regression test for ChatGPT-only full-exit tool schema.

Uses stdlib AST extraction so CI never imports API packages or calls models.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    tree = ast.parse((ROOT / "agent_runner.py").read_text())
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef)
              and x.name == "get_trade_tool")
    ns = {"json": json, "Path": Path, "__file__": str(ROOT / "agent_runner.py")}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "agent_runner.get_trade_tool", "exec"), ns)
    make = ns["get_trade_tool"]
    def limit(agent):
        return make(agent)["parameters"]["properties"]["trades"]["items"]["properties"]["allocation_pct"]["maximum"]
    assert limit("chatgpt_aggressive") == 100
    assert limit("claude_aggressive") == 25
    assert limit(None) == 25
    print("PASS: ChatGPT SELL envelope 100%; Claude contract unchanged")


if __name__ == "__main__":
    main()
