# Flujo de Caja Demo

> Sistema de conciliación bancaria automatizada con IA — **Build #001** de [Sintetix Data](mailto:negocios@sintetixdata.com)

Pipeline que recibe un PDF de estado de cuenta bancario, lo categoriza con Claude (vía [Claude Code](https://www.anthropic.com/claude-code) en modo headless) según NIF mexicanas, almacena el resultado como JSON con git como audit trail, y lo visualiza en Power BI Desktop.

## Stack

- **Python 3.11+** — pipeline core
- **pdfplumber** — extracción de tablas del PDF
- **Claude Code** — categorización (modo `claude -p`, sin API key)
- **Git + GitHub** — storage del JSON y audit trail nativo
- **Windows Task Scheduler** — disparo automático cuando aparece un PDF
- **Power BI Desktop** — visualización conectada al raw URL del JSON

## Cómo correr

```bash
# Setup inicial
python -m venv .venv
.venv\Scripts\activate         # Windows (bash en Git Bash)
pip install -r requirements.txt

# Procesar un estado de cuenta
python -m src.main --pdf data/estado_marzo_2026.pdf
```

## Estructura del JSON

Toda la "base de datos" vive en [`data/transactions.json`](data/transactions.json):

```json
{
  "metadata": {
    "last_updated": "2026-04-29T00:00:00Z",
    "total_transactions": 0,
    "version": "0.1.0"
  },
  "transactions": [
    {
      "id": "tx_2026_03_001",
      "fecha": "2026-03-01",
      "descripcion_cruda": "CARGO SPEI X1234 DESPACHO MORALES Y ASOC SC",
      "monto": -45000.00,
      "categoria": "Gastos operativos",
      "subcategoria": "Honorarios profesionales",
      "cuenta_nif": "601-001",
      "confianza": 92,
      "revision_humana": false,
      "categorizado_por": "claude-sonnet-4-6",
      "categorizado_en": "2026-04-29T00:00:00Z"
    }
  ]
}
```

## Categorías principales (NIF mexicanas)

Las 6 categorías están en [`data/categories.json`](data/categories.json):

1. Ingresos
2. Costo de ventas
3. Gastos operativos
4. Gastos financieros
5. Inversiones
6. Otros

Si Claude regresa una `confianza < 70`, la transacción se marca con `revision_humana: true` para que un humano la categorice a mano.

## Auditoría y correcciones

Cada cambio al JSON queda firmado por commit en git:

```bash
git log --oneline data/transactions.json
git blame data/transactions.json
```

Para corregir una categorización: editar el JSON, commit con mensaje descriptivo (`fix: recategorize tx_xxx to marketing`), push. Power BI Desktop refresca al manualmente cuando abres el archivo.

## Estado del proyecto

🚧 **En construcción.** Build #001 del canal de YouTube de Sintetix Data — el video documenta paso a paso cómo se construyó este sistema.

## License

[MIT](LICENSE) — uso libre, sin garantías.

## Contacto

**Sintetix Data** · Mérida, Yucatán, México
[negocios@sintetixdata.com](mailto:negocios@sintetixdata.com) · [sintetixdata.com](https://sintetixdata.com)
