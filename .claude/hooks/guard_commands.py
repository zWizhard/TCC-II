#!/usr/bin/env python3
"""PreToolUse (Bash/PowerShell): bloqueia comandos destrutivos e SQL de alteracao.

Protocolo: le JSON no stdin. exit 0 = permite; exit 2 = bloqueia e envia stderr ao Claude.
Deliberadamente conservador: prefere deixar passar a bloquear trabalho legitimo.
"""
import json
import re
import sys

# (regex, motivo). Case-insensitive. Alvo: acao irreversivel, nao "palavra perigosa".
RULES = [
    (r"\bgit\s+reset\s+(--hard|--merge\b.*--hard)", "git reset --hard descarta alteracoes nao commitadas"),
    (r"\bgit\s+clean\b[^|;]*-[a-z]*[fd]", "git clean remove arquivos nao rastreados de forma irreversivel"),
    (r"\bgit\s+push\b[^|;]*(--force(?!-with-lease)|(?<![-\w])-f(?![-\w]))", "git push --force reescreve historico remoto"),
    (r"\bgit\s+checkout\s+--\s", "git checkout -- <arquivo> descarta alteracoes locais"),
    (r"\bgit\s+restore\b(?![^|;]*--staged)", "git restore descarta alteracoes locais"),
    (r"\bgit\s+branch\s+-D\b", "git branch -D descarta branch nao mesclada"),
    (r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", "rm -rf e irreversivel"),
    (r"Remove-Item[^|;]*-Recurse[^|;]*-Force|Remove-Item[^|;]*-Force[^|;]*-Recurse", "Remove-Item -Recurse -Force e irreversivel"),
    (r"\b(rmdir|rd)\s+/s\b", "rmdir /s remove arvore de diretorios"),
    (r">\s*[^\s|;&]*\.env\b", "redirecionamento sobrescreveria um arquivo .env"),
    (r"\b(DROP|TRUNCATE)\s+(TABLE|SCHEMA|DATABASE|VIEW)\b", "SQL destrutivo (DROP/TRUNCATE) — o banco e read-only"),
    (r"\bDELETE\s+FROM\b", "SQL destrutivo (DELETE) — o banco e read-only"),
    (r"\bUPDATE\s+[\w.\"`\[\]]+\s+SET\b", "SQL destrutivo (UPDATE) — o banco e read-only"),
    (r"\bINSERT\s+INTO\b", "SQL de escrita (INSERT) — o banco e read-only"),
    (r"\bALTER\s+(TABLE|SCHEMA|DATABASE)\b", "SQL destrutivo (ALTER) — o banco e read-only"),
    (r"\b(GRANT|REVOKE)\s+\w+", "SQL de permissao (GRANT/REVOKE) — o banco e read-only"),
]

# Impressao de segredo no terminal (o valor acabaria no transcript).
SECRET_ECHO = re.compile(
    r"\b(cat|type|Get-Content|gc)\b[^|;]*(\.env(?!\.example|\.sample|\.template)\b"
    r"|\bsecrets?\.(json|ya?ml|toml)\b|\bcredentials?\b|id_rsa\b|\.pem\b)",
    re.IGNORECASE,
)

COMPILED = [(re.compile(p, re.IGNORECASE), why) for p, why in RULES]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # entrada ilegivel nunca bloqueia trabalho

    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return 0

    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd:
        return 0

    for rx, why in COMPILED:
        if rx.search(cmd):
            sys.stderr.write(
                f"BLOQUEADO pelo hook guard_commands: {why}.\n"
                "Se for realmente necessario, explique o motivo ao usuario e peca autorizacao "
                "explicita antes de tentar de novo.\n"
            )
            return 2

    if SECRET_ECHO.search(cmd):
        sys.stderr.write(
            "BLOQUEADO pelo hook guard_commands: leitura de arquivo de credenciais no terminal "
            "colocaria o segredo no transcript.\n"
            "Use .env.example para conferir o formato, ou peca ao usuario o nome da variavel.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
