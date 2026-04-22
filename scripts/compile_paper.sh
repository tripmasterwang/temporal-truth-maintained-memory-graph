#!/bin/bash
set -e
cd "$(dirname "$0")/.."
cd paper
which pdflatex || { echo "pdflatex not found"; exit 1; }
pdflatex -interaction=nonstopmode main.tex > build.log 2>&1 || true
bibtex main > /dev/null 2>&1 || true
pdflatex -interaction=nonstopmode main.tex > build.log 2>&1 || true
pdflatex -interaction=nonstopmode main.tex > build.log 2>&1 || true
if [ -f main.pdf ]; then
  P=$(pdfinfo main.pdf 2>/dev/null | grep -E "^Pages" | awk '{print $2}')
  echo "[compile] OK: main.pdf pages=$P"
else
  echo "[compile] FAILED, tail of build.log:"
  tail -40 build.log
  exit 1
fi
