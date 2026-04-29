"""Parser para estados de cuenta BBVA México (Libretón Básico Cuenta Digital).

Las transacciones aparecen como líneas de texto, no como tablas formales.
Patrón por línea: DD/MMM DD/MMM <descripción> <monto> [saldos opcionales]

La primera página suele ser imagen (sin texto extraíble) — se omite.
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

# Palabras en la descripción que indican que la transacción es un ABONO
# (dinero entrante). Por defecto las transacciones se asumen cargos.
ABONO_KEYWORDS = (
    "RECIBIDO", "ABONO", "DEPOSITO", "DEPÓSITO",
    "DEVOLUCION", "DEVOLUCIÓN", "NOMINA", "NÓMINA",
)


def parse_bank_statement(pdf_path: str | Path) -> pd.DataFrame:
    """Lee un estado de cuenta BBVA y devuelve un DataFrame con
    columnas: fecha (datetime), descripcion_cruda (str), monto (float),
    tipo (cargo | abono).
    """
    rows: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        year = _extract_year(pdf) or datetime.now().year
        for page in pdf.pages[1:]:  # primera página es imagen
            text = page.extract_text() or ""
            for line in text.split("\n"):
                tx = _parse_line(line, year)
                if tx is not None:
                    rows.append(tx)
    return pd.DataFrame(rows)


def _extract_year(pdf) -> int | None:
    for page in pdf.pages[:3]:
        text = page.extract_text() or ""
        m = PERIODO_PATTERN.search(text)
        if m:
            return int(m.group(2))
    return None


def _parse_line(line: str, year: int) -> dict | None:
    m = TX_PATTERN.match(line.strip())
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

    descripcion = descripcion.strip()
    tipo = _classify_tipo(descripcion)
    monto = monto_abs if tipo == "abono" else -monto_abs

    return {
        "fecha": fecha,
        "descripcion_cruda": descripcion,
        "monto": monto,
        "tipo": tipo,
    }


def _classify_tipo(descripcion: str) -> str:
    desc_upper = descripcion.upper()
    if any(kw in desc_upper for kw in ABONO_KEYWORDS):
        return "abono"
    return "cargo"
