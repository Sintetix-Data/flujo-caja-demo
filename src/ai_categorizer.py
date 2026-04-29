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

PROMPT_TEMPLATE = """Eres un experto en NIF mexicanas categorizando transacciones bancarias.

Transacción: {descripcion_cruda}
Monto: {monto} MXN
Tipo: {tipo}

Asigna en JSON:
1. categoria_principal (Ingresos, Costo de ventas, Gastos operativos, Gastos financieros, Inversiones, Otros)
2. subcategoria
3. cuenta_nif
4. confianza (entero 0-100)
5. revision_humana (true si confianza < 70, false en caso contrario)

Responde SOLO JSON. Sin markdown, sin explicación."""

CLAUDE_TIMEOUT_SECS = 60


def categorize(transaccion: dict) -> dict:
    """Categoriza una transacción usando Claude Code en modo headless.

    Args:
        transaccion: dict con keys `descripcion_cruda`, `monto`, `tipo`.

    Returns:
        dict con keys `categoria_principal`, `subcategoria`, `cuenta_nif`,
        `confianza`, `revision_humana`.
    """
    prompt = PROMPT_TEMPLATE.format(**transaccion)
    raw = _run_claude(prompt)
    return _parse_json(raw)


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


def _parse_json(raw: str) -> dict:
    fence = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    obj = re.search(r"\{.*\}", raw, re.DOTALL)
    if obj:
        raw = obj.group(0)
    return json.loads(raw)
