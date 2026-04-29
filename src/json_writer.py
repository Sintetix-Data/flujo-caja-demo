"""JSON writer para transactions.json — merge con dedup y pretty-print."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def make_id(fecha: str, descripcion: str, monto: float) -> str:
    """ID determinístico tx_YYYY_MM_<hash6> a partir de fecha+descripción+monto."""
    year, month = fecha[:4], fecha[5:7]
    digest = hashlib.md5(f"{fecha}|{descripcion}|{monto}".encode()).hexdigest()[:6]
    return f"tx_{year}_{month}_{digest}"


def merge_into_json(new_transactions: list[dict], json_path: str | Path) -> dict:
    """Carga transactions.json, agrega transacciones nuevas (dedup por id),
    actualiza metadata y escribe el archivo de vuelta.

    Returns:
        Metadata final del archivo, con key extra `added` (cantidad real
        de transacciones nuevas que se agregaron tras dedup).
    """
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    existing_ids = {tx["id"] for tx in data["transactions"]}
    new_unique = [tx for tx in new_transactions if tx["id"] not in existing_ids]

    data["transactions"].extend(new_unique)
    data["transactions"].sort(key=lambda tx: (tx["fecha"], tx["id"]))

    data["metadata"]["last_updated"] = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    data["metadata"]["total_transactions"] = len(data["transactions"])

    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    return {**data["metadata"], "added": len(new_unique)}
