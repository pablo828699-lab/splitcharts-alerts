"""
build_dashboard.py
==================

Empotra `docs/data.json` dentro de `docs/index.html` como copia de respaldo.

El tablero normalmente lee `data.json` por fetch. Ese fetch falla en dos casos
reales: abrir el archivo con doble clic (file:// bloquea CORS) y la primera
carga en Netlify si el monitor todavia no corrio. Con la copia empotrada la
pagina renderiza igual, y ademas queda como archivo unico compartible.

Se ejecuta despues de portfolio_monitor.py, en el mismo paso del workflow.
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "docs", "index.html")
DATA = os.path.join(HERE, "docs", "data.json")

PATTERN = re.compile(r"/\*DATA:START\*/.*?/\*DATA:END\*/", re.DOTALL)


def main():
    if not os.path.exists(DATA):
        print("no hay docs/data.json todavia; nada que empotrar")
        return 0

    data = json.load(open(DATA, encoding="utf-8"))  # valida el JSON antes de tocar el HTML
    html = open(HTML, encoding="utf-8").read()

    if not PATTERN.search(html):
        print("ERROR: faltan los marcadores DATA:START / DATA:END en docs/index.html",
              file=sys.stderr)
        return 1

    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    out = PATTERN.sub(lambda _: "/*DATA:START*/" + blob.replace("\\", "\\\\") + "/*DATA:END*/",
                      html, count=1)
    open(HTML, "w", encoding="utf-8").write(out)
    print(f"respaldo empotrado en docs/index.html ({len(blob)//1024} KB de datos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
