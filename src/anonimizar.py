"""Anonimización aplicada al pipeline.

Usado por main.py para garantizar que el JSON resultante no contiene
datos personales identificables (PII): RFCs, nombres, números de cuenta.
"""
import re

NOMBRES_REALES = (
    "IVAN ALEJANDRO AYALA GARCIA",
    "IVAN AYALA GARCIA",
    "IVAN AYALA",
    "JONATHAN GARCIA",
    "RICARDO LOPEZ",
    "IVAN ANTONIO AYALA CANTU",
    "ALEJANDRO AYALA",
)

NOMBRE_FRAGMENTOS = (
    "AYALA",
    "GARCIA",
    "IVAN",
    "ALEJANDRO",
    "JONATHAN",
    "RICARDO",
    "LOPEZ",
    "CANTU",
)


def anonimize_extendida(text: str) -> str:
    """Elimina PII de la descripción extendida (RFCs, AUT, referencias, nombres)."""
    if not text:
        return text
    text = re.sub(r"RFC:\s*\S+\s+\S+", "RFC: XXX 000000XXX", text)
    text = re.sub(r"AUT:\s*\d+", "AUT: 000000", text)
    text = re.sub(r"Referencia\s+[\*\d]+(\s+\d+)?", "Referencia ******0000", text)
    text = re.sub(r"\b\d{10,}\b", "0000000000", text)
    text = re.sub(
        r"(MBAN\d+|BNET\s*\d+)",
        lambda m: m.group(1)[:4] + "00000000",
        text,
    )
    text = re.sub(r"FOLIO:?\s*\d+", "FOLIO: 0000", text)
    text = re.sub(r"\b[A-Z]{3,4}\d{6,}[A-Z]\d?\b", "XXXXXXXXXXX", text)
    text = re.sub(r"NC\s*\d+", "NC 00000000", text)
    text = re.sub(
        r"\b[A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,}){1,}\b",
        "BENEFICIARIO",
        text,
    )
    for nombre in NOMBRES_REALES:
        text = text.replace(nombre, "USUARIO")
        text = text.replace(nombre.title(), "USUARIO")
    for frag in NOMBRE_FRAGMENTOS:
        text = re.sub(frag, "X", text, flags=re.IGNORECASE)
    text = re.sub(r"X{2,}", "X", text)
    text = re.sub(r"(?:\bX\b\s*){2,}", "USUARIO ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def anonimize_cruda(desc: str) -> str:
    """Anonimiza descripción cruda manteniendo el tipo de transacción."""
    if not desc:
        return desc
    desc = re.sub(r"TRANSFER BBVA\s+\d+\s*[A-Z]?", "TRANSFER BBVA", desc)
    return desc.strip()
