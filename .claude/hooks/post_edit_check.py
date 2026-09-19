#!/usr/bin/env python3
"""PostToolUse (Edit/Write): verifica APENAS o arquivo que acabou de mudar.

Nunca roda a suite de testes nem formata o projeto inteiro.
exit 0 = ok; exit 2 = devolve o problema ao Claude para correcao.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys

# Segredo obviamente hardcoded (nao heuristica agressiva: exige valor longo e literal).
# (?<![A-Za-z]) em vez de \b: precisa casar dentro de DB_PASSWORD / apiKey,
# onde '_' e caractere de palavra e portanto nao ha word boundary.
HARDCODED = re.compile(
    r"""(?ix)
    (?<![A-Za-z])
    (password|senha|passwd|secret|api[-_]?key|access[-_]?token|
     client[-_]?secret|private[-_]?key|connection[-_]?string)
    (?![A-Za-z])
    \s*[:=]\s*
    ["'][^"'\s{}$<>]{8,}["']
    """
)
SAFE_VALUE = re.compile(
    r"(?i)(getenv|environ|os\.env|process\.env|\{\{|\$\{|<|your|change|seu|troque|example|exemplo|placeholder|xxx|dummy|fake|redacted|\*\*\*)"
)


def check_python(path: str, src: str) -> str | None:
    try:
        ast.parse(src, filename=path)
    except SyntaxError as e:
        return f"SyntaxError em {os.path.basename(path)}:{e.lineno}: {e.msg}"
    ruff = shutil.which("ruff")
    if ruff:
        try:
            # So regras de DEFEITO, nunca de estilo. Este hook bloqueia a edicao, e
            # bloquear por I001/E501/UP/SIM trava trabalho legitimo a cada arquivo novo
            # (ex.: I001 dispara so por faltar linha em branco depois do import).
            # F401/F841 ficam de fora: import e variavel ainda sem uso sao normais no meio
            # de uma edicao. Estilo se resolve em `ruff check` no release-check.
            r = subprocess.run(
                [ruff, "check", "--quiet", "--output-format", "concise",
                 "--select", "F,E9,B", "--ignore", "F401,F841", path],
                capture_output=True, text=True, timeout=20,
            )
            if r.returncode not in (0, 1):
                return None
            out = (r.stdout or "").strip()
            if out:
                lines = out.splitlines()
                head = "\n".join(lines[:10])
                more = f"\n(+{len(lines) - 10} outros)" if len(lines) > 10 else ""
                return f"ruff apontou problemas:\n{head}{more}"
        except Exception:
            return None
    return None


def check_json(path: str, src: str) -> str | None:
    try:
        json.loads(src)
    except ValueError as e:
        return f"JSON invalido em {os.path.basename(path)}: {e}"
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        return 0

    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        if os.path.getsize(path) > 2_000_000:
            return 0
        # utf-8-sig: no Windows e comum o arquivo ter BOM; sem isso o BOM
        # vira U+FEFF e produz SyntaxError falso.
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            src = f.read()
    except OSError:
        return 0

    problems = []

    for m in HARDCODED.finditer(src):
        if not SAFE_VALUE.search(m.group(0)):
            line = src[: m.start()].count("\n") + 1
            problems.append(
                f"Possivel segredo hardcoded em {os.path.basename(path)}:{line} "
                f"('{m.group(1)}'). Use variavel de ambiente / .env."
            )
            break

    ext = os.path.splitext(path)[1].lower()
    checker = {".py": check_python, ".json": check_json}.get(ext)
    if checker:
        issue = checker(path, src)
        if issue:
            problems.append(issue)

    if problems:
        sys.stderr.write("post_edit_check:\n- " + "\n- ".join(problems) + "\n")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
