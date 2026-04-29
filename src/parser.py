"""PDF parser para estados de cuenta bancarios mexicanos.

Asume un layout de 3 columnas: fecha | descripción | monto.
Negativos = cargos, positivos = abonos.
"""
from datetime import datetime
from pathlib import Path

import pdfplumber
import pandas as pd


def parse_bank_statement(pdf_path: str | Path) -> pd.DataFrame:
    """Lee un PDF y devuelve un DataFrame con columnas:
    fecha (datetime), descripcion_cruda (str), monto (float), tipo (str).
    """
    rows: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    parsed = _parse_row(row)
                    if parsed is not None:
                        rows.append(parsed)
    return pd.DataFrame(rows)


def _parse_row(row: list[str | None]) -> dict | None:
    if not row or len(row) < 3:
        return None

    fecha_str = (row[0] or "").strip()
    descripcion = (row[1] or "").strip()
    monto_str = (row[2] or "").strip()

    if not fecha_str or not descripcion or not monto_str:
        return None

    try:
        fecha = datetime.strptime(fecha_str, "%d/%m/%Y")
        monto = _parse_monto(monto_str)
    except ValueError:
        return None

    return {
        "fecha": fecha,
        "descripcion_cruda": descripcion,
        "monto": monto,
        "tipo": "cargo" if monto < 0 else "abono",
    }


def _parse_monto(s: str) -> float:
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return float(s)
