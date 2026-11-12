#!/usr/bin/env python3
"""
alias: detect-format
version: 1.0
purpose: Detecta el formato REAL de un fichero por su contenido (no por la extensión)
created: 2026-11-12
last_updated: 2026-11-12
plugin: p4cc-converter
skill: any-to-md (Step 3)
"""

"""
Detecta el formato real de uno o varios ficheros leyendo su contenido: firma de
archivo ("magic bytes") y, para contenedores, su estructura interna. La extensión del
nombre solo se usa para señalar discrepancias. Solo usa la librería estándar.

Uso:
    python3 detect-format.py <fichero> [<fichero> ...]

Salida (stdout): un array JSON con un objeto por fichero:
    {
      "path":      "/abs/ruta/informe.pdf",
      "ext":       "pdf",            # extensión del nombre, sin punto ("" si no tiene)
      "detected":  "docx",           # formato real (ver tabla)
      "mismatch":  true,             # la extensión no coincide con el formato real
      "supported": true,             # any-to-md sabe convertirlo
      "route":     "office-to-pdf",  # pdf | office-to-pdf | spreadsheet | null
      "note":      "..."             # explicación cuando no es soportado o hay duda
    }

Formatos detectados y ruta:
    pdf                              → route "pdf"
    doc, docx, ppt, pptx             → route "office-to-pdf"
    xls, xlsx, xlsm                  → route "spreadsheet"
    xlsb, ods, odt, odp, rtf, html,
    xml, csv, text, empty, unknown   → no soportados (route null)

Código de salida: 0 si se pudo analizar todo; 1 si algún fichero no existe o no se
puede leer (se informa igualmente en el JSON con detected "unreadable").
"""

import json
import sys
import zipfile
from pathlib import Path

SUPPORTED_ROUTES = {
    "pdf": "pdf",
    "doc": "office-to-pdf", "docx": "office-to-pdf",
    "ppt": "office-to-pdf", "pptx": "office-to-pdf",
    "xls": "spreadsheet", "xlsx": "spreadsheet", "xlsm": "spreadsheet",
}

OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
ODF_MIME = {
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.presentation": "odp",
}
MAX_OLE_SCAN = 200 * 1024 * 1024   # no leer en memoria ficheros OLE de más de 200 MB


def detect_zip(path: Path):
    """Distingue OOXML (docx/xlsx/xlsm/xlsb/pptx) y OpenDocument por su estructura interna."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "mimetype" in names:
                mime = z.read("mimetype").decode("ascii", "ignore").strip()
                if mime in ODF_MIME:
                    return ODF_MIME[mime], "OpenDocument no soportado: guárdalo como DOCX/XLSX/PPTX o PDF"
            if "xl/workbook.bin" in names:
                return "xlsb", "Excel binario (.xlsb) no soportado: guárdalo como .xlsx"
            if any(n.startswith("xl/") for n in names):
                macro = "xl/vbaProject.bin" in names
                if not macro and "[Content_Types].xml" in names:
                    macro = b"macroEnabled" in z.read("[Content_Types].xml")
                return ("xlsm" if macro else "xlsx"), ""
            if any(n.startswith("word/") for n in names):
                return "docx", ""
            if any(n.startswith("ppt/") for n in names):
                return "pptx", ""
    except (zipfile.BadZipFile, OSError):
        return "unknown", "ZIP dañado o ilegible"
    return "unknown", "ZIP que no es un documento Office/OpenDocument reconocible"


def detect_ole(path: Path):
    """Distingue doc/xls/ppt (formato binario antiguo) por los nombres de stream del contenedor OLE2."""
    if path.stat().st_size > MAX_OLE_SCAN:
        return None, "Contenedor OLE2 demasiado grande para inspeccionar"
    data = path.read_bytes()
    def has(name: str) -> bool:
        return name.encode("utf-16-le") in data
    if has("WordDocument"):
        return "doc", ""
    if has("PowerPoint Document"):
        return "ppt", ""
    if has("Workbook") or has("Book"):
        return "xls", ""
    return None, "Contenedor OLE2 que no parece doc, xls ni ppt"


def detect_text(head: bytes):
    """Clasifica contenido de texto. Muchos '.xls' exportados son HTML o CSV disfrazados."""
    if not head.strip():
        return "empty", "Fichero vacío"
    text = head.decode("utf-8-sig", "ignore").lstrip().lower()
    if text.startswith(("<!doctype html", "<html", "<table", "<head", "<body")) or "<table" in text[:2000]:
        return "html", "HTML con extensión de Office (típico de exportaciones web): ábrelo y guárdalo como .xlsx/.docx o PDF"
    if text.startswith("{\\rtf"):
        return "rtf", "RTF no soportado: guárdalo como .docx o PDF"
    if text.startswith("<?xml"):
        return "xml", "XML (p. ej. SpreadsheetML 2003) no soportado: guárdalo como .xlsx"
    lines = [l for l in text.splitlines()[:5] if l.strip()]
    if lines and all(("," in l or ";" in l or "\t" in l) for l in lines):
        return "csv", "CSV/TSV no soportado por any-to-md"
    return "text", "Texto plano no soportado por any-to-md"


def detect(path: Path) -> dict:
    ext = path.suffix.lstrip(".").lower()
    res = {"path": str(path), "ext": ext, "detected": "unknown", "mismatch": False,
           "supported": False, "route": None, "note": ""}
    try:
        with path.open("rb") as f:
            head = f.read(4096)
        if not head:
            fmt, note = "empty", "Fichero vacío"
        elif head.startswith(b"%PDF-") or b"%PDF-" in head[:1024]:
            fmt, note = "pdf", ""
        elif head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
            fmt, note = detect_zip(path)
        elif head.startswith(OLE_MAGIC):
            fmt, note = detect_ole(path)
            if fmt is None:
                fmt = "unknown"
        else:
            fmt, note = detect_text(head) if b"\x00" not in head else ("unknown", "Formato binario no reconocido")
    except OSError as exc:
        res.update(detected="unreadable", note=f"No se pudo leer: {exc}")
        return res

    res["detected"] = fmt
    res["note"] = note
    res["route"] = SUPPORTED_ROUTES.get(fmt)
    res["supported"] = res["route"] is not None
    # .xlsx ↔ .xlsm cuentan como el mismo tipo de extensión para evitar falsos avisos
    same = {"xlsx": {"xlsx", "xlsm"}, "xlsm": {"xlsx", "xlsm"}}
    res["mismatch"] = ext not in same.get(fmt, {fmt})
    if res["mismatch"] and res["supported"]:
        shown_ext = "." + ext if ext else "(ninguna)"
        res["note"] = (res["note"] + " " if res["note"] else "") + \
            f"La extensión {shown_ext} no coincide con el contenido real ({fmt}): se usa el formato real."
    return res


def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("Uso: detect-format.py <fichero> [<fichero> ...]", file=sys.stderr)
        sys.exit(1)
    results, bad = [], False
    for arg in sys.argv[1:]:
        p = Path(arg).expanduser().resolve()
        if not p.is_file():
            results.append({"path": str(p), "ext": p.suffix.lstrip(".").lower(), "detected": "unreadable",
                            "mismatch": False, "supported": False, "route": None,
                            "note": "El fichero no existe o no es un fichero regular"})
            bad = True
            continue
        r = detect(p)
        bad = bad or r["detected"] == "unreadable"
        results.append(r)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
