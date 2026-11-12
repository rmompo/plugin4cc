#!/usr/bin/env python3
"""
alias: xlsx-to-md
version: 1.0
purpose: Convierte un libro Excel (.xlsx/.xlsm) en Markdown: una sección por hoja, cada hoja como tabla
created: 2026-11-12
last_updated: 2026-11-12
plugin: p4cc-converter
skill: any-to-md (Step 4c)
"""

"""
Convierte un libro de Excel a Markdown usando openpyxl. No pasa por PDF: las hojas de
cálculo se leen directamente, sin trocear ni extracción por LLM.

Los ficheros .xls (formato antiguo) NO los lee openpyxl: el skill los convierte antes a
.xlsx con LibreOffice (any-to-md Step 4c) y le pasa aquí el resultado.

Uso:
    python3 xlsx-to-md.py \\
      --source <ruta/libro.xlsx> \\
      --output <ruta/libro.md> \\
      [--original <ruta/libro.xls>] [--max-rows 1000] [--formulas]

Parámetros:
  --source    Libro .xlsx/.xlsm a leer
  --output    Ruta del .md final
  --original  Fichero origen real, solo para el frontmatter (p. ej. el .xls convertido)
  --max-rows  Máximo de filas por hoja (por defecto 1000; 0 = sin límite). Las filas
              sobrantes se omiten y se deja una nota con el total
  --formulas  Muestra la fórmula (=SUM(A1:A3)) en lugar del valor calculado

Reglas de conversión:
  - Una sección "## <hoja>" por hoja visible; las hojas ocultas se omiten (se listan en
    el frontmatter como hidden_sheets).
  - Se recorta el rango usado: filas y columnas vacías de los bordes no aparecen.
  - La primera fila del rango es la cabecera de la tabla.
  - Celdas combinadas: el valor se escribe en la celda superior izquierda y el resto del
    rango queda vacío.
  - Fechas en ISO (YYYY-MM-DD o YYYY-MM-DD HH:MM:SS); `|` y saltos de línea se escapan.
  - Por defecto se usan los valores calculados que Excel guardó en el fichero. Si el
    libro fue generado sin calcular (p. ej. por una librería), esas celdas salen vacías:
    el script lo avisa y se puede usar --formulas.
  - Gráficos, imágenes y tablas dinámicas no se extraen (se avisa de cuántos hay).

Dependencia: openpyxl (apt: python3-openpyxl · pip: openpyxl).
"""

import argparse
import datetime as dt
import sys
from datetime import datetime
from pathlib import Path

try:
    import openpyxl
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    print("ERROR: falta openpyxl. Instálalo con: sudo apt install python3-openpyxl "
          "(o: pip install openpyxl)", file=sys.stderr)
    sys.exit(2)


def fmt_cell(value) -> str:
    """Formatea un valor de celda para una tabla Markdown."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, dt.datetime):
        if value.hour == value.minute == value.second == 0 and value.microsecond == 0:
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dt.time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, float):
        # 3.0 -> 3, evita ruido de coma flotante (0.30000000000000004)
        return str(int(value)) if value.is_integer() else f"{value:.12g}"
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>").strip()


def used_bounds(rows):
    """Devuelve (primera_fila, ultima_fila, primera_col, ultima_col) 0-indexados sin vacíos de borde."""
    r_min = r_max = c_min = c_max = None
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            r_min = r if r_min is None else min(r_min, r)
            r_max = r if r_max is None else max(r_max, r)
            c_min = c if c_min is None else min(c_min, c)
            c_max = c if c_max is None else max(c_max, c)
    return r_min, r_max, c_min, c_max


def sheet_to_table(ws, max_rows: int):
    """Convierte una hoja en (líneas_markdown, filas_totales, filas_omitidas, celdas_sin_valor)."""
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    r_min, r_max, c_min, c_max = used_bounds(rows)
    if r_min is None:
        return [], 0, 0, 0

    block = [r[c_min:c_max + 1] + [None] * max(0, c_max + 1 - len(r)) for r in rows[r_min:r_max + 1]]
    total = len(block)

    # Celdas combinadas: solo conserva la esquina superior izquierda (openpyxl ya lo hace en
    # values_only; aquí nos aseguramos de que el resto del rango quede vacío)
    for mr in ws.merged_cells.ranges:
        for rr in range(mr.min_row, mr.max_row + 1):
            for cc in range(mr.min_col, mr.max_col + 1):
                if (rr, cc) == (mr.min_row, mr.min_col):
                    continue
                i, j = rr - 1 - r_min, cc - 1 - c_min
                if 0 <= i < len(block) and 0 <= j < len(block[0]):
                    block[i][j] = None

    omitted = 0
    if max_rows and total > max_rows + 1:   # +1: la cabecera no cuenta
        omitted = total - (max_rows + 1)
        block = block[:max_rows + 1]

    width = len(block[0])
    header = [fmt_cell(v) or get_column_letter(c_min + i + 1) for i, v in enumerate(block[0])]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * width) + "|"]
    for row in block[1:]:
        lines.append("| " + " | ".join(fmt_cell(v) for v in row) + " |")
    return lines, total, omitted, 0


def count_uncached_formulas(path: Path) -> int:
    """Celdas con fórmula pero sin valor calculado guardado (libro nunca calculado por Excel)."""
    wb_f = openpyxl.load_workbook(path, data_only=False)
    wb_v = openpyxl.load_workbook(path, data_only=True)
    missing = 0
    for ws_f in wb_f.worksheets:
        ws_v = wb_v[ws_f.title]
        for row in ws_f.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("=") \
                        and ws_v[cell.coordinate].value is None:
                    missing += 1
    wb_f.close()
    wb_v.close()
    return missing


def convert(source: Path, output: Path, original: Path, max_rows: int, formulas: bool) -> None:
    wb = openpyxl.load_workbook(source, data_only=not formulas)

    visible = [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
    hidden = [ws.title for ws in wb.worksheets if ws.sheet_state != "visible"]

    parts = []
    summary = []
    skipped_media = 0
    for ws in visible:
        skipped_media += len(getattr(ws, "_charts", [])) + len(getattr(ws, "_images", []))
        lines, total, omitted, _ = sheet_to_table(ws, max_rows)
        parts.append(f"## {ws.title}\n")
        if not lines:
            parts.append("_Empty sheet._\n")
            summary.append((ws.title, 0, 0))
            continue
        parts.append("\n".join(lines) + "\n")
        if omitted:
            parts.append(f"> **Note:** showing the first {max_rows} data rows of {total - 1}; "
                         f"{omitted} rows omitted.\n")
        summary.append((ws.title, total - 1, omitted))

    uncached = 0 if formulas else count_uncached_formulas(source)
    wb.close()

    fm = [
        "---",
        f"source: {original.name}",
        f"source_format: {original.suffix.lstrip('.').lower()}",
        f"converted: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}",
        "converted_via: openpyxl" + (" (xls → xlsx via libreoffice)" if original.suffix.lower() == ".xls" else ""),
        f"sheets: {len(visible)}",
    ]
    if hidden:
        fm.append("hidden_sheets: [" + ", ".join(hidden) + "]")
    fm.append(f"values: {'formulas' if formulas else 'calculated'}")
    fm.append(f"max_rows_per_sheet: {max_rows if max_rows else 'unlimited'}")
    fm.append("---\n")

    title = f"# {original.stem}\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(fm) + "\n" + title + "\n" + "\n".join(parts), encoding="utf-8")

    print("══════════════════════════════════════════")
    print("  XLSX CONVERSION COMPLETE")
    print("══════════════════════════════════════════")
    print(f"  Documento:    {output.name}")
    print(f"  Origen:       {original.name}")
    print(f"  Hojas:        {len(visible)} visibles" + (f", {len(hidden)} ocultas omitidas" if hidden else ""))
    for name, rows_, omitted in summary:
        extra = f" ({omitted} omitidas)" if omitted else ""
        print(f"    - {name}: {rows_} filas{extra}")
    if uncached:
        print(f"  ⚠️  {uncached} celdas con fórmula sin valor calculado guardado (salen vacías). "
              f"Reintenta con --formulas o abre y guarda el libro en Excel/LibreOffice.")
    if skipped_media:
        print(f"  ℹ️  {skipped_media} gráficos/imágenes no extraídos")
    print("══════════════════════════════════════════")


def main():
    parser = argparse.ArgumentParser(description="Convierte un libro Excel (.xlsx/.xlsm) en Markdown.")
    parser.add_argument("--source", required=True, type=Path, help="Libro .xlsx/.xlsm")
    parser.add_argument("--output", required=True, type=Path, help="Ruta del .md final")
    parser.add_argument("--original", type=Path, default=None,
                        help="Fichero origen real para el frontmatter (p. ej. el .xls convertido)")
    parser.add_argument("--max-rows", type=int, default=1000,
                        help="Máximo de filas de datos por hoja (0 = sin límite; por defecto 1000)")
    parser.add_argument("--formulas", action="store_true",
                        help="Escribe las fórmulas en lugar de los valores calculados")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.exists():
        print(f"ERROR: El fichero origen no existe: {source}", file=sys.stderr)
        sys.exit(1)
    if source.suffix.lower() not in {".xlsx", ".xlsm"}:
        print(f"ERROR: openpyxl solo lee .xlsx/.xlsm (recibido: {source.suffix}). "
              f"Convierte antes los .xls con LibreOffice.", file=sys.stderr)
        sys.exit(1)
    if args.max_rows < 0:
        print("ERROR: --max-rows no puede ser negativo", file=sys.stderr)
        sys.exit(1)

    original = (args.original or source).resolve()
    try:
        convert(source, args.output.resolve(), original, args.max_rows, args.formulas)
    except Exception as exc:  # fichero corrupto, protegido con contraseña, etc.
        print(f"ERROR: no se pudo leer '{source.name}': {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
