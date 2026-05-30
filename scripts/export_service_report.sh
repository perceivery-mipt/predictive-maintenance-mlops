#!/usr/bin/env bash
set -euo pipefail

jupyter nbconvert --to markdown notebooks/service_up_report.ipynb \
  --output-dir reports/final \
  --output service_up_report.md

python - <<'PY'
from pathlib import Path

path = Path("reports/final/service_up_report.md")
text = path.read_text(encoding="utf-8")

# В ноутбуке путь считается от notebooks/.
# В Markdown-отчёте путь считается от reports/final/.
text = text.replace('src="../screenshots/', 'src="../../screenshots/')
text = text.replace('](../screenshots/', '](../../screenshots/')

path.write_text(text, encoding="utf-8")
print("Rendered GitHub-friendly report:", path)
PY
