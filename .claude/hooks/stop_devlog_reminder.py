#!/usr/bin/env python3
"""Stop: lembrete leve de que mudancas persistentes devem ter registro no devlog.

NAO bloqueia: sempre exit 0, emitindo systemMessage. Por construcao nao pode criar loop de Stop.
Custo alvo: poucas dezenas de ms — a varredura e podada e limitada.
"""
import json
import os
import sys
import time

SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", "dist", "build", ".next", ".turbo", "coverage",
    ".claude", "docs", "data", ".idea", ".vscode", ".ipynb_checkpoints",
}
WATCHED_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".sql", ".json", ".toml", ".yml", ".yaml",
    ".css", ".md", ".ipynb",
}
MAX_FILES = 4000
WINDOW_S = 6 * 3600  # so considera o que mudou nesta sessao de trabalho


def newest_devlog_mtime(root: str) -> float:
    newest = 0.0
    devlog = os.path.join(root, "docs", "tcc", "devlog")
    if not os.path.isdir(devlog):
        return 0.0
    try:
        for name in os.listdir(devlog):
            if name.endswith(".md"):
                newest = max(newest, os.path.getmtime(os.path.join(devlog, name)))
    except OSError:
        return 0.0
    return newest


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    # Salvaguarda anti-loop, embora este hook nunca bloqueie.
    if data.get("stop_hook_active"):
        return 0

    root = data.get("cwd") or os.getcwd()
    now = time.time()
    cutoff = max(now - WINDOW_S, newest_devlog_mtime(root))

    changed, seen = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            seen += 1
            if seen > MAX_FILES:
                changed = []  # projeto grande demais para varrer barato: nao palpita
                break
            if os.path.splitext(fn)[1].lower() not in WATCHED_EXT:
                continue
            try:
                if os.path.getmtime(os.path.join(dirpath, fn)) > cutoff:
                    changed.append(fn)
            except OSError:
                continue
            if len(changed) >= 5:
                break
        if seen > MAX_FILES or len(changed) >= 5:
            break

    if changed:
        amostra = ", ".join(sorted(set(changed))[:4])
        print(json.dumps({
            "systemMessage": (
                f"Lembrete: ha alteracoes sem registro de devlog mais recente ({amostra}). "
                "Se esta tarefa produziu mudanca persistente relevante, chame o subagent "
                "tcc-documentarian com um TASK HANDOFF compacto."
            )
        }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
