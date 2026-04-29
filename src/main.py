"""Orquestador del pipeline.

Uso:
    python -m src.main --pdf data/estado_marzo_2026.pdf
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.ai_categorizer import DEFAULT_BATCH_SIZE, categorize_chunk
from src.json_writer import make_id, merge_into_json
from src.parser import parse_bank_statement

JSON_PATH = Path("data/transactions.json")
CATEGORIZADO_POR = "claude-code"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = _parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        print(f"❌ PDF no encontrado: {pdf_path}")
        return 1

    print("=" * 50)
    print("🏦 Flujo de Caja Demo — Sintetix Data")
    print("=" * 50)
    print()

    t0 = time.time()

    print(f"📄 Parsing PDF: {pdf_path}")
    df = parse_bank_statement(pdf_path)
    if df.empty:
        print("   ❌ No se extrajeron transacciones del PDF.")
        return 1
    print(f"   ✓ {len(df)} transacciones extraídas")
    print()

    txs = df.to_dict("records")
    n_batches = (len(txs) + args.batch_size - 1) // args.batch_size
    print(
        f"🤖 Categorizando con Claude Code (Plan B, $0) — "
        f"{n_batches} lotes de hasta {args.batch_size}"
    )

    cat_t0 = time.time()
    categorizations: list[dict] = []
    for i in range(0, len(txs), args.batch_size):
        chunk = txs[i : i + args.batch_size]
        batch_idx = i // args.batch_size + 1
        batch_t0 = time.time()
        chunk_cats = categorize_chunk(chunk)
        batch_elapsed = time.time() - batch_t0
        categorizations.extend(chunk_cats)
        print(
            f"   ✓ Lote {batch_idx}/{n_batches} ({len(chunk)} tx) — {batch_elapsed:.1f}s"
        )

    cat_elapsed = time.time() - cat_t0
    revision_count = sum(1 for c in categorizations if c.get("revision_humana"))
    print(f"   Total categorización: {cat_elapsed:.1f}s")
    print(f"   ⚠ {revision_count} marcadas para revisión humana")
    print()

    now_iso = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    full_txs: list[dict] = []
    for tx, cat in zip(txs, categorizations):
        fecha = tx["fecha"]
        fecha_iso = fecha.strftime("%Y-%m-%d") if hasattr(fecha, "strftime") else str(fecha)[:10]
        full_txs.append(
            {
                "id": make_id(fecha_iso, tx["descripcion_cruda"], tx["monto"]),
                "fecha": fecha_iso,
                "descripcion_cruda": tx["descripcion_cruda"],
                "monto": float(tx["monto"]),
                "tipo": tx["tipo"],
                **cat,
                "categorizado_por": CATEGORIZADO_POR,
                "categorizado_en": now_iso,
            }
        )

    print(f"💾 Escribiendo {JSON_PATH}")
    meta = merge_into_json(full_txs, JSON_PATH)
    duplicates = len(full_txs) - meta["added"]
    print(
        f"   ✓ {meta['added']} nuevas | {duplicates} duplicadas | "
        f"total: {meta['total_transactions']}"
    )
    print()

    elapsed = time.time() - t0
    print(f"⏱  Total: {elapsed:.1f} segundos")
    print("✅ Listo. Haz commit + push para refrescar Power BI.")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pipeline de conciliación bancaria con IA")
    p.add_argument("--pdf", required=True, help="Ruta al PDF del estado de cuenta")
    p.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Transacciones por lote (default: {DEFAULT_BATCH_SIZE})",
    )
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
