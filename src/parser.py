"""Parser para estados de cuenta BBVA México (Libretón Básico Cuenta Digital).

Las transacciones aparecen como una línea de cabecera + 0..N sublíneas con
contexto adicional (RFC, AUT, recipiente del SPEI, concepto NOMINA, etc.).

Cabecera: DD/MMM DD/MMM <descripción> <monto> [saldos opcionales]

Para distinguir cargo vs abono, el PDF de BBVA usa COLUMNAS SEPARADAS
en posiciones x distintas: cargos al ~x=417, abonos al ~x=458.
Esto se detecta vía pdfplumber.extract_words() y la coordenada x1 del
primer monto en la línea.

La primera página suele ser imagen — se omite.
"""
import re
from datetime import datetime
from pathlib import Path

import pdfplumber
import pandas as pd

MESES_ES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

TX_PATTERN = re.compile(
    r"^(\d{1,2})/([A-Z]{3})\s+(\d{1,2})/([A-Z]{3})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s+[\d,]+\.\d{2})*\s*$"
)
PERIODO_PATTERN = re.compile(
    r"Periodo DEL (\d{2})/(\d{2})/(\d{4}) AL (\d{2})/(\d{2})/(\d{4})"
)
MONEY_RE = re.compile(r"^[\d,]+\.\d{2}$")

# Umbral de coordenada x1 que separa columna CARGOS de columna ABONOS en
# el PDF BBVA Libretón. Determinado empíricamente:
#   Cargos: x1 ≈ 396-418
#   Abonos: x1 ≈ 425-460
ABONO_X1_THRESHOLD = 422

NOISE_PREFIXES = (
    "Estado de Cuenta",
    "Libretón", "Libreton",
    "PAGINA",
    "No. de Cuenta", "No. de Cliente",
    "Periodo DEL",
    "Fecha de Corte",
    "BBVA MEXICO",
    "Av. Paseo",
)


def parse_bank_statement(pdf_path: str | Path) -> pd.DataFrame:
    """Lee un estado de cuenta BBVA y devuelve un DataFrame con columnas:
    fecha, descripcion_cruda, descripcion_extendida, monto, tipo.

    Usa coordenadas x del PDF para clasificar cargo vs abono según la
    columna donde está el monto en el layout original de BBVA.
    """
    rows: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        period = _extract_period(pdf)
        if period is None:
            now = datetime.now()
            period = (1, now.year, 12, now.year)

        all_lines: list[list[dict]] = []
        for page in pdf.pages[1:]:  # primera página es imagen
            words = page.extract_words(use_text_flow=True)
            all_lines.extend(_group_words_into_lines(words, y_tolerance=3))

        current: dict | None = None
        for line_words in all_lines:
            line_text = " ".join(w["text"] for w in line_words).strip()
            if not line_text or _is_noise(line_text):
                continue

            header = _parse_header(line_words, line_text, period)
            if header is not None:
                if current is not None:
                    rows.append(_finalize(current))
                current = header
                current["sublines"] = []
            elif current is not None:
                current["sublines"].append(line_text)

        if current is not None:
            rows.append(_finalize(current))

    return pd.DataFrame(rows)


def _group_words_into_lines(
    words: list[dict], y_tolerance: float = 3
) -> list[list[dict]]:
    """Agrupa palabras en líneas visuales por proximidad en eje y.

    Las palabras dentro de la misma línea pueden tener variaciones de hasta
    ~1px en `top` por baselines. Usar buckets fijos (round/N) puede separar
    palabras que pertenecen visualmente a la misma línea. Este algoritmo
    ordena por y y agrupa cualquier palabra que esté dentro de tolerance
    pixels de la mediana de la línea actual.
    """
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: w["top"])
    lines: list[list[dict]] = []
    current: list[dict] = [sorted_words[0]]
    line_top = sorted_words[0]["top"]
    for w in sorted_words[1:]:
        if w["top"] - line_top <= y_tolerance:
            current.append(w)
            # Track el top mínimo para que la línea no se "arrastre"
            line_top = min(line_top, w["top"])
        else:
            lines.append(sorted(current, key=lambda x: x["x0"]))
            current = [w]
            line_top = w["top"]
    lines.append(sorted(current, key=lambda x: x["x0"]))
    return lines


def _extract_period(pdf) -> tuple[int, int, int, int] | None:
    """Devuelve (start_month, start_year, end_month, end_year) o None."""
    for page in pdf.pages[:3]:
        text = page.extract_text() or ""
        m = PERIODO_PATTERN.search(text)
        if m:
            _, sm, sy, _, em, ey = m.groups()
            return int(sm), int(sy), int(em), int(ey)
    return None


def _resolve_year(month: int, period: tuple[int, int, int, int]) -> int:
    start_m, start_y, _, end_y = period
    if start_y == end_y:
        return start_y
    return start_y if month >= start_m else end_y


def _is_noise(line: str) -> bool:
    return any(line.startswith(p) for p in NOISE_PREFIXES)


def _parse_header(
    line_words: list[dict],
    line_text: str,
    period: tuple[int, int, int, int],
) -> dict | None:
    m = TX_PATTERN.match(line_text)
    if not m:
        return None

    day_str, mes_es, _, _, descripcion, monto_str = m.groups()
    mes_num = MESES_ES.get(mes_es.upper())
    if mes_num is None:
        return None

    try:
        year = _resolve_year(mes_num, period)
        fecha = datetime(year, mes_num, int(day_str))
        monto_abs = float(monto_str.replace(",", ""))
    except (ValueError, TypeError):
        return None

    # Determinar tipo según la posición x del primer monto en la línea
    monto_word = next(
        (w for w in line_words if MONEY_RE.match(w["text"])),
        None,
    )
    if monto_word is None:
        tipo = "cargo"  # fallback
    else:
        tipo = "abono" if monto_word["x1"] >= ABONO_X1_THRESHOLD else "cargo"

    return {
        "fecha": fecha,
        "descripcion_cruda": descripcion.strip(),
        "monto_abs": monto_abs,
        "tipo": tipo,
    }


def _finalize(current: dict) -> dict:
    sublines = current.pop("sublines", [])
    extended = " | ".join(sublines)
    tipo = current.pop("tipo")
    monto_abs = current.pop("monto_abs")
    return {
        "fecha": current["fecha"],
        "descripcion_cruda": current["descripcion_cruda"],
        "descripcion_extendida": extended,
        "monto": monto_abs if tipo == "abono" else -monto_abs,
        "tipo": tipo,
    }
