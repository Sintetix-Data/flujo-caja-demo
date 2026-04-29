"""Parser para estados de cuenta BBVA México (Libretón Básico Cuenta Digital).

Las transacciones aparecen como una línea de cabecera + 0..N sublíneas con
contexto adicional (RFC, AUT, recipiente del SPEI, concepto NOMINA, etc.).

Cabecera: DD/MMM DD/MMM <descripción> <monto> [saldos opcionales]
Sublíneas: cualquier línea entre cabeceras (excepto ruido fijo del PDF).

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
    r"Periodo DEL \d{2}/\d{2}/(\d{4}) AL \d{2}/\d{2}/(\d{4})"
)

ABONO_KEYWORDS = (
    "RECIBIDO", "ABONO", "DEPOSITO", "DEPÓSITO",
    "DEVOLUCION", "DEVOLUCIÓN", "NOMINA", "NÓMINA",
    "PGO NOMINA",
)

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
    """
    rows: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        year = _extract_year(pdf) or datetime.now().year

        all_lines: list[str] = []
        for page in pdf.pages[1:]:  # primera página es imagen
            text = page.extract_text() or ""
            all_lines.extend(text.split("\n"))

        current: dict | None = None
        for raw in all_lines:
            line = raw.strip()
            if not line or _is_noise(line):
                continue

            header = _parse_header(line, year)
            if header is not None:
                if current is not None:
                    rows.append(_finalize(current))
                current = header
                current["sublines"] = []
            elif current is not None:
                current["sublines"].append(line)

        if current is not None:
            rows.append(_finalize(current))

    return pd.DataFrame(rows)


def _extract_year(pdf) -> int | None:
    for page in pdf.pages[:3]:
        text = page.extract_text() or ""
        m = PERIODO_PATTERN.search(text)
        if m:
            return int(m.group(2))
    return None


def _is_noise(line: str) -> bool:
    return any(line.startswith(p) for p in NOISE_PREFIXES)


def _parse_header(line: str, year: int) -> dict | None:
    m = TX_PATTERN.match(line)
    if not m:
        return None

    day_str, mes_es, _, _, descripcion, monto_str = m.groups()
    mes_num = MESES_ES.get(mes_es.upper())
    if mes_num is None:
        return None

    try:
        fecha = datetime(year, mes_num, int(day_str))
        monto_abs = float(monto_str.replace(",", ""))
    except (ValueError, TypeError):
        return None

    return {
        "fecha": fecha,
        "descripcion_cruda": descripcion.strip(),
        "monto_abs": monto_abs,
    }


def _finalize(current: dict) -> dict:
    sublines = current.pop("sublines", [])
    extended = " | ".join(sublines)
    full_text = current["descripcion_cruda"] + " " + extended
    tipo = _classify_tipo(full_text)
    monto_abs = current.pop("monto_abs")
    return {
        "fecha": current["fecha"],
        "descripcion_cruda": current["descripcion_cruda"],
        "descripcion_extendida": extended,
        "monto": monto_abs if tipo == "abono" else -monto_abs,
        "tipo": tipo,
    }


def _classify_tipo(texto: str) -> str:
    texto_upper = texto.upper()
    if any(kw in texto_upper for kw in ABONO_KEYWORDS):
        return "abono"
    return "cargo"
