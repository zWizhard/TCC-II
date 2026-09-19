#!/usr/bin/env python3
"""PreToolUse (Read/Edit/Write): impede leitura e escrita de arquivos de segredo.

.env.example / .env.sample / .env.template sao liberados desde que sem valor real.
exit 0 = permite; exit 2 = bloqueia.
"""
import json
import os
import re
import sys

TOOLS = ("Read", "Edit", "Write", "NotebookEdit", "MultiEdit")

SECRET_NAME = re.compile(
    r"(^|[/\\])("
    r"\.env(\.[\w-]+)?"          # .env, .env.local, .env.production
    r"|secrets?\.(json|ya?ml|toml|ini)"
    r"|credentials?(\.[\w]+)?"
    r"|service[-_]account.*\.json"
    r"|id_[rd]sa|id_ecdsa|id_ed25519"
    r"|.*\.(pem|key|pfx|p12|keytab)"
    r")$",
    re.IGNORECASE,
)

EXAMPLE_NAME = re.compile(r"(^|[/\\])\.env\.(example|sample|template|dist)$", re.IGNORECASE)

# Valor que parece real num arquivo de exemplo (chave=valor nao vazio e nao placeholder).
PLACEHOLDER = re.compile(
    r"^\s*($|#|[\w.]+\s*=\s*($|\"\"$|''$|<.*>$|\.\.\.$|(your|change|seu|sua|troque|exemplo|example|placeholder|xxx|todo|dummy|fake)))",
    re.IGNORECASE,
)


def looks_like_real_secret(text: str) -> str | None:
    for line in (text or "").splitlines():
        if not line.strip() or PLACEHOLDER.match(line):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            val = val.strip().strip("\"'")
            if len(val) >= 8 and not val.startswith("<"):
                return key.strip()
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    if data.get("tool_name") not in TOOLS:
        return 0

    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not path:
        return 0

    base = os.path.basename(path)

    if EXAMPLE_NAME.search(path.replace("\\", "/")) or EXAMPLE_NAME.search("/" + base):
        content = ti.get("content") or ti.get("new_string") or ""
        leaked = looks_like_real_secret(content)
        if leaked:
            sys.stderr.write(
                f"BLOQUEADO pelo hook protect_secrets: '{base}' e um arquivo de exemplo e a variavel "
                f"'{leaked}' parece conter um valor real.\n"
                "Deixe o valor vazio ou como <placeholder>.\n"
            )
            return 2
        return 0

    if SECRET_NAME.search(path.replace("\\", "/")) or SECRET_NAME.search("/" + base):
        sys.stderr.write(
            f"BLOQUEADO pelo hook protect_secrets: '{base}' contem credenciais e nao deve ser "
            "lido nem escrito pelo agente.\n"
            "Edite .env.example (sem valores) e peca ao usuario para preencher o .env manualmente.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
