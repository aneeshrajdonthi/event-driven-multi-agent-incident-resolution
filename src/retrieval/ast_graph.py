"""AST-based code graph extraction for Python source files.

Used by the root-cause agent to trace function/class definitions and call
relationships across a codebase.
"""

from __future__ import annotations

import ast
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ASTGraphBuilder:
    """Build a lightweight call graph from Python source code."""

    def __init__(self) -> None:
        self._nodes: list[dict[str, Any]] = []
        self._edges: list[dict[str, str]] = []
        # name -> node for fast lookup
        self._node_map: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_graph(self, source_code: str) -> dict[str, Any]:
        """Parse *source_code* and return ``{"nodes": [...], "edges": [...]}``."""
        self._nodes.clear()
        self._edges.clear()
        self._node_map.clear()

        try:
            tree = ast.parse(source_code)
        except SyntaxError as exc:
            logger.error("Failed to parse source: %s", exc)
            return {"nodes": [], "edges": []}

        self._extract_definitions(tree)
        self._extract_calls(tree)

        return {
            "nodes": list(self._nodes),
            "edges": list(self._edges),
        }

    def find_related_functions(self, function_name: str) -> list[str]:
        """Return names of functions that call *or are called by* function_name."""
        related: set[str] = set()
        for edge in self._edges:
            if edge["caller"] == function_name:
                related.add(edge["callee"])
            elif edge["callee"] == function_name:
                related.add(edge["caller"])
        return sorted(related)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _extract_definitions(self, tree: ast.Module) -> None:
        """Walk the AST and register function / class definition nodes."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                info: dict[str, Any] = {
                    "name": node.name,
                    "type": "function",
                    "lineno": node.lineno,
                    "args": [a.arg for a in node.args.args],
                    "decorators": [
                        ast.dump(d) for d in node.decorator_list
                    ],
                }
                self._nodes.append(info)
                self._node_map[node.name] = info

            elif isinstance(node, ast.ClassDef):
                info = {
                    "name": node.name,
                    "type": "class",
                    "lineno": node.lineno,
                    "bases": [ast.dump(b) for b in node.bases],
                    "methods": [],
                }
                # Register methods as sub-nodes
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        method_name = f"{node.name}.{item.name}"
                        method_info: dict[str, Any] = {
                            "name": method_name,
                            "type": "method",
                            "lineno": item.lineno,
                            "args": [a.arg for a in item.args.args],
                        }
                        self._nodes.append(method_info)
                        self._node_map[method_name] = method_info
                        info["methods"].append(method_name)  # type: ignore[union-attr]

                self._nodes.append(info)
                self._node_map[node.name] = info

    def _extract_calls(self, tree: ast.Module) -> None:
        """Walk the AST and record call edges between known functions."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue

            caller = node.name
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue

                callee = self._resolve_call_name(child)
                if callee and callee != caller:
                    self._edges.append({"caller": caller, "callee": callee})

    @staticmethod
    def _resolve_call_name(call: ast.Call) -> str | None:
        """Best-effort extraction of the callee name from an ast.Call node."""
        func = call.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None
