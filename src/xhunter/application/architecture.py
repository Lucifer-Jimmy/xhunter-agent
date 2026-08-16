"""AST-based dependency checks used by CI and local review."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ImportViolation:
    path: Path
    line: int
    imported: str
    reason: str


def check_architecture(source_root: Path) -> tuple[ImportViolation, ...]:
    violations: list[ImportViolation] = []
    for path in source_root.rglob("*.py"):
        relative = path.relative_to(source_root)
        module = ".".join(relative.with_suffix("").parts)
        imports = _imports(path)
        for imported, line in imports:
            reason = _violation_reason(module, imported)
            if reason is not None:
                violations.append(ImportViolation(path, line, imported, reason))
    return tuple(violations)


def _imports(path: Path) -> tuple[tuple[str, int], ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.module, node.lineno))
    return tuple(imports)


def _violation_reason(module: str, imported: str) -> str | None:
    if module.startswith("xhunter.kernel"):
        if imported.startswith("xhunter.") and not imported.startswith(
            "xhunter.kernel"
        ):
            return "kernel may only depend on kernel"
    if module.startswith("xhunter.contracts"):
        allowed = ("xhunter.contracts", "xhunter.kernel")
        if imported.startswith("xhunter.") and not imported.startswith(allowed):
            return "contracts may only depend on contracts and kernel"
    if module.startswith("xhunter.runtime"):
        forbidden = (
            "xhunter.adapters",
            "xhunter.application",
            "xhunter.domains",
            "xhunter.plugins",
        )
        if imported.startswith(forbidden):
            return "runtime may not depend on concrete outer layers"
    if module.startswith("xhunter.domains"):
        forbidden = ("xhunter.adapters", "xhunter.application")
        if imported.startswith(forbidden):
            return "domain may not depend on adapters or application"
    if module.startswith("xhunter.orchestration.planner"):
        forbidden = ("xhunter.adapters", "xhunter.contracts.storage")
        if imported.startswith(forbidden):
            return "planner may not access repositories or adapters"
    return None
