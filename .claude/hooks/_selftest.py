#!/usr/bin/env python3
"""Regressao dos hooks. Rodar apos qualquer alteracao neles:

    python .claude/hooks/_selftest.py

Cobre tanto o que DEVE bloquear quanto o que NAO pode bloquear — falso positivo
em hook e pior que falso negativo, porque trava trabalho legitimo em toda sessao.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HOOKS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HOOKS))

GUARD = [
    ("git reset --hard HEAD~1", True),
    ("git clean -fd", True),
    ("git push --force origin main", True),
    ("git checkout -- src/app.py", True),
    ("rm -rf ./build", True),
    ("Remove-Item -Recurse -Force node_modules", True),
    ("DROP TABLE censo.ies", True),
    ("DELETE FROM censo.cursos WHERE ano = 2023", True),
    ("UPDATE censo.ies SET nome = 'x'", True),
    ("INSERT INTO censo.ies VALUES (1)", True),
    ("GRANT SELECT ON censo TO leitor", True),
    ("cat .env", True),
    ("Get-Content credentials.json", True),
    # nao podem bloquear
    ("git status", False),
    ("git diff --stat", False),
    ("git log --oneline -10", False),
    ("git push origin main", False),
    ("git push --force-with-lease origin feat", False),
    ("git add -A", False),
    ("git commit -m 'feat: mapa'", False),
    ("git restore --staged src/app.py", False),
    ("SELECT COUNT(*) FROM censo.ies LIMIT 10", False),
    ("python -m pytest tests/", False),
    ("npm run build", False),
    ("cat .env.example", False),
    ("ruff check src/", False),
    ("Get-ChildItem -Recurse docs", False),
    ("uv add sqlglot", False),
]

SECRETS = [
    ("Read", ".env", None, True),
    ("Write", ".env", "X=1", True),
    ("Read", "secrets.json", None, True),
    ("Read", "key.pem", None, True),
    ("Read", "id_rsa", None, True),
    ("Write", ".env.example", "DB_PASSWORD=\nOLLAMA_MODEL=", False),
    ("Write", ".env.example", "DB_PASSWORD=<sua senha>", False),
    ("Write", ".env.example", "DB_PASSWORD=Xk9!mQ2vLp8w", True),
    ("Read", "src/app.py", None, False),
    ("Read", "docs/README.md", None, False),
]

EDIT_FILES = [
    ('DB_PASSWORD = "Xk9mQ2vLp8wZr4"\n', True, "segredo hardcoded"),
    ('import os\ndb_password = os.getenv("BIGDATA_PASSWORD")\npassword = "<sua senha>"\n', False, "uso via env"),
    ("def f(:\n", True, "erro de sintaxe"),
    ("# comentario\nx = 1\n", False, "arquivo valido"),
    # Regressao: o hook so pode bloquear por DEFEITO, nunca por estilo.
    ("import os\nprint(os.getcwd())\n", False, "import sem linha em branco (ruff I001)"),
    ("import json\nx = 1\n", False, "import ainda sem uso (ruff F401)"),
    ("x = nome_inexistente\n", True, "nome indefinido (ruff F821)"),
]


def run(script, payload):
    p = subprocess.run(
        [sys.executable, os.path.join(HOOKS, script)],
        input=json.dumps(payload), capture_output=True, text=True, timeout=60,
    )
    return p.returncode, (p.stderr or "").strip(), (p.stdout or "").strip()


def report(name, fails, total):
    status = "OK" if fails == 0 else f"{fails} FALHA(S)"
    print(f"{name:26} {total:>3} casos  {status}")
    return fails


def main() -> int:
    total_fails = 0

    fails = 0
    for cmd, expect in GUARD:
        rc, _, _ = run("guard_commands.py", {"tool_name": "PowerShell", "tool_input": {"command": cmd}})
        if (rc == 2) != expect:
            fails += 1
            print(f"  FALHOU guard: esperado={'BLOQUEIA' if expect else 'PERMITE'} :: {cmd}")
    total_fails += report("guard_commands.py", fails, len(GUARD))

    fails = 0
    for tool, rel, content, expect in SECRETS:
        ti = {"file_path": os.path.join(ROOT, rel.replace("/", os.sep))}
        if content is not None:
            ti["content"] = content
        rc, _, _ = run("protect_secrets.py", {"tool_name": tool, "tool_input": ti})
        if (rc == 2) != expect:
            fails += 1
            print(f"  FALHOU secrets: esperado={'BLOQUEIA' if expect else 'PERMITE'} :: {tool} {rel} {content!r}")
    total_fails += report("protect_secrets.py", fails, len(SECRETS))

    fails = 0
    with tempfile.TemporaryDirectory() as td:
        for i, (src, expect, label) in enumerate(EDIT_FILES):
            fp = os.path.join(td, f"c{i}.py")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(src)
            rc, err, _ = run("post_edit_check.py", {"tool_name": "Edit", "tool_input": {"file_path": fp}})
            if (rc == 2) != expect:
                fails += 1
                print(f"  FALHOU post_edit ({label}): esperado={'BLOQUEIA' if expect else 'PERMITE'} :: {err[:120]}")
        # BOM nao pode virar SyntaxError falso
        fp = os.path.join(td, "bom.py")
        with open(fp, "w", encoding="utf-8-sig") as f:
            f.write("x = 1\n")
        rc, err, _ = run("post_edit_check.py", {"tool_name": "Edit", "tool_input": {"file_path": fp}})
        if rc == 2:
            fails += 1
            print(f"  FALHOU post_edit (BOM): arquivo valido com BOM foi bloqueado :: {err[:120]}")
    total_fails += report("post_edit_check.py", fails, len(EDIT_FILES) + 1)

    fails = 0
    t0 = time.time()
    rc, _, out = run("stop_devlog_reminder.py", {"stop_hook_active": False, "cwd": ROOT})
    dt = time.time() - t0
    if rc != 0:
        fails += 1
        print(f"  FALHOU stop: NUNCA pode bloquear (rc={rc})")
    if dt > 3:
        fails += 1
        print(f"  FALHOU stop: lento demais ({dt:.2f}s)")
    rc2, _, out2 = run("stop_devlog_reminder.py", {"stop_hook_active": True, "cwd": ROOT})
    if rc2 != 0 or out2:
        fails += 1
        print("  FALHOU stop: salvaguarda anti-loop nao funcionou")
    total_fails += report("stop_devlog_reminder.py", fails, 3)
    print(f"{'':26} (stop levou {dt:.2f}s)")

    print()
    print("RESULTADO:", "TODOS OS TESTES PASSARAM" if total_fails == 0 else f"{total_fails} FALHA(S)")
    return 1 if total_fails else 0


if __name__ == "__main__":
    sys.exit(main())
