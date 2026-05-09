"""Anonimiza data/transactions.json para uso público (video, demo, repo).

Remueve datos personales identificables:
- RFCs reales → 'RFC: XXX 000000XXX'
- AUT codes → 'AUT: 000000'
- Números de referencia → '******0000'
- Números de cuenta largos → '0000000000'
- Nombres de personas → 'USUARIO'

Mantiene:
- categoria_principal, subcategoria, cuenta_nif (categorización Claude)
- fecha, monto (datos numéricos del flujo de caja)
- Merchant identification general (OXXO ALEMÁN, CHOPO, etc.) — no es PII

Salida: data/transactions_anonimo.json (no sobreescribe el original)
"""
import hashlib
import json
import re
from pathlib import Path

INPUT = Path("data/transactions.json")
OUTPUT = Path("data/transactions_anonimo.json")

# Nombres reales completos
NOMBRES_REALES = [
    "IVAN ALEJANDRO AYALA GARCIA",
    "IVAN AYALA GARCIA",
    "IVAN AYALA",
    "JONATHAN GARCIA",
    "RICARDO LOPEZ",
    "IVAN ANTONIO AYALA CANTU",
    "ALEJANDRO AYALA",
]

# Fragmentos parciales que pueden aparecer truncados en sublines BBVA
# (ej. "A AYALA GAR", "AYALA GA", etc.)
NOMBRE_FRAGMENTOS = [
    "AYALA",
    "GARCIA",
    "IVAN",
    "ALEJANDRO",
    "JONATHAN",
    "RICARDO",
    "LOPEZ",
    "CANTU",
]


def anonimize_extendida(text: str) -> str:
    if not text:
        return text
    # RFC: XXX 000000XXX (cualquier letra-numero después de RFC:)
    text = re.sub(r"RFC:\s*\S+\s+\S+", "RFC: XXX 000000XXX", text)
    # AUT: 123456 → AUT: 000000
    text = re.sub(r"AUT:\s*\d+", "AUT: 000000", text)
    # Referencia ******1351 o Referencia 0091762771 → Referencia ******0000
    text = re.sub(r"Referencia\s+[\*\d]+(\s+\d+)?", "Referencia ******0000", text)
    # Números de cuenta largos (10+ dígitos)
    text = re.sub(r"\b\d{10,}\b", "0000000000", text)
    # MBAN o BNET pre + número
    text = re.sub(r"(MBAN\d+|BNET\s*\d+)", lambda m: m.group(1)[:4] + "00000000", text)
    # Folios
    text = re.sub(r"FOLIO:?\s*\d+", "FOLIO: 0000", text)
    # Códigos de despacho/empresa con letras+números (ACO8310135K8 etc.)
    text = re.sub(r"\b[A-Z]{3,4}\d{6,}[A-Z]\d?\b", "XXXXXXXXXXX", text)
    # NC + número
    text = re.sub(r"NC\s*\d+", "NC 00000000", text)
    # Capturar nombres "Apellido Apellido Apellido" (3+ palabras MAYÚSCULAS seguidas)
    # antes de fragmentar — atrapa beneficiarios de SPEI cuyo nombre no conocemos
    text = re.sub(
        r"\b[A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,}){1,}\b",
        "BENEFICIARIO",
        text,
    )
    # Nombres completos
    for nombre in NOMBRES_REALES:
        text = text.replace(nombre, "USUARIO")
        text = text.replace(nombre.title(), "USUARIO")
    # Fragmentos parciales: substring match (no word boundary) para capturar
    # casos tipo "0109250IVAN" o "AAYALA" donde el regex de palabra falla
    for frag in NOMBRE_FRAGMENTOS:
        text = re.sub(frag, "X", text, flags=re.IGNORECASE)
    # Limpieza: colapsar múltiples X seguidas
    text = re.sub(r"X{2,}", "X", text)
    text = re.sub(r"(?:\bX\b\s*){2,}", "USUARIO ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def anonimize_cruda(desc: str) -> str:
    """Anonimiza descripción cruda manteniendo el tipo de transacción."""
    if not desc:
        return desc
    # TRANSFER BBVA <num> [letra] → TRANSFER BBVA NOMINA (asumir nómina)
    desc = re.sub(r"TRANSFER BBVA\s+\d+\s*[A-Z]?", "TRANSFER BBVA", desc)
    # SPEI ENVIADO sigue igual (el banco destino es info pública)
    return desc.strip()


def make_id(fecha: str, descripcion: str, monto: float) -> str:
    year, month = fecha[:4], fecha[5:7]
    digest = hashlib.md5(f"{fecha}|{descripcion}|{abs(monto)}".encode()).hexdigest()[:6]
    return f"tx_{year}_{month}_{digest}"


def main():
    if not INPUT.is_file():
        raise FileNotFoundError(f"No existe {INPUT}")

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    txs = data["transactions"]

    for tx in txs:
        tx["descripcion_cruda"] = anonimize_cruda(tx["descripcion_cruda"])
        tx["descripcion_extendida"] = anonimize_extendida(tx["descripcion_extendida"])
        tx["id"] = make_id(tx["fecha"], tx["descripcion_cruda"], tx["monto"])

    # Re-deduplicar por si la anonimización colapsó IDs
    seen = set()
    unique = []
    for tx in txs:
        if tx["id"] not in seen:
            seen.add(tx["id"])
            unique.append(tx)

    data["transactions"] = unique
    data["metadata"]["total_transactions"] = len(unique)

    OUTPUT.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"OK: {len(unique)} transacciones anonimizadas")
    print(f"   Original: {len(txs)} | Tras dedup: {len(unique)} ({len(txs) - len(unique)} colapsadas)")
    print(f"   Salida: {OUTPUT}")


if __name__ == "__main__":
    main()
