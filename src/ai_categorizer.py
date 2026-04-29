"""Categorizador de transacciones bancarias usando Claude Code (subprocess).

Plan B: NO usa la API de Anthropic. Invoca el CLI `claude -p` que se autentica
con la suscripción Claude.ai del usuario logueado en la máquina.
"""
import json
import re
import shutil
import subprocess

CLAUDE_EXE = shutil.which("claude")
if CLAUDE_EXE is None:
    raise RuntimeError(
        "Claude Code CLI no encontrado en PATH. "
        "Instala con: npm install -g @anthropic-ai/claude-code"
    )

CLAUDE_TIMEOUT_SECS = 180
DEFAULT_BATCH_SIZE = 10

PROMPT_SINGLE = """Eres un experto en NIF mexicanas categorizando transacciones bancarias.

Transacción: {descripcion_cruda}
Monto: {monto} MXN
Tipo: {tipo}

Asigna en JSON:
1. categoria_principal (Ingresos, Costo de ventas, Gastos operativos, Gastos financieros, Inversiones, Otros)
2. subcategoria
3. cuenta_nif
4. confianza (entero 0-100)
5. revision_humana (true si confianza < 70)

Responde SOLO JSON. Sin markdown, sin explicación."""

PROMPT_BATCH = """Eres un experto en NIF mexicanas categorizando transacciones bancarias.

Categoriza las siguientes {n} transacciones. Devuelve un JSON array con
EXACTAMENTE {n} elementos en el MISMO orden, donde cada elemento tiene:

- categoria_principal (Ingresos, Costo de ventas, Gastos operativos, Gastos financieros, Inversiones, Otros)
- subcategoria
- cuenta_nif
- confianza (entero 0-100)
- revision_humana (true si confianza < 70)

Transacciones:
{items}

Responde SOLO el JSON array de {n} objetos. Sin markdown, sin explicación."""


def categorize(transaccion: dict) -> dict:
    """Categoriza UNA transacción. Útil para debugging."""
    prompt = PROMPT_SINGLE.format(**transaccion)
    raw = _run_claude(prompt)
    return _parse_json_obj(raw)


def categorize_batch(
    transactions: list[dict], batch_size: int = DEFAULT_BATCH_SIZE
) -> list[dict]:
    """Categoriza N transacciones en lotes de `batch_size` por llamada."""
    results: list[dict] = []
    for i in range(0, len(transactions), batch_size):
        chunk = transactions[i : i + batch_size]
        results.extend(_categorize_chunk(chunk))
    return results


def _categorize_chunk(chunk: list[dict]) -> list[dict]:
    items = "\n".join(
        f"{i + 1}. Descripción: {tx['descripcion_cruda']} | "
        f"Monto: {tx['monto']} MXN | Tipo: {tx['tipo']}"
        for i, tx in enumerate(chunk)
    )
    prompt = PROMPT_BATCH.format(n=len(chunk), items=items)
    raw = _run_claude(prompt)
    parsed = _parse_json_array(raw)

    if len(parsed) != len(chunk):
        raise RuntimeError(
            f"Claude regresó {len(parsed)} items, esperados {len(chunk)}. "
            f"Considera reducir batch_size."
        )
    return parsed


def _run_claude(prompt: str) -> str:
    result = subprocess.run(
        [CLAUDE_EXE, "-p"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=CLAUDE_TIMEOUT_SECS,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p falló (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _parse_json_obj(raw: str) -> dict:
    raw = _strip_markdown_fences(raw)
    obj = re.search(r"\{.*\}", raw, re.DOTALL)
    if obj:
        raw = obj.group(0)
    return json.loads(raw)


def _parse_json_array(raw: str) -> list[dict]:
    raw = _strip_markdown_fences(raw)
    arr = re.search(r"\[.*\]", raw, re.DOTALL)
    if arr:
        raw = arr.group(0)
    return json.loads(raw)


def _strip_markdown_fences(raw: str) -> str:
    fence = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    return fence.group(1).strip() if fence else raw
