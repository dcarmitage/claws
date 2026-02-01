#!/bin/bash
# Portal1 Knowledge Search
# Usage: qmd-search.sh [search|vsearch|status] <query> [-n count] [-c collection]
export PATH="$HOME/.bun/bin:$PATH"
QMD_DIR="/tmp/qmd-install"

case "$1" in
  search)
    shift
    cd "$QMD_DIR" && bun src/qmd.ts search "$@"
    ;;
  vsearch)
    shift  
    cd "$QMD_DIR" && bun /home/clawd/tools/qmd-vsearch-lite.ts "$@"
    ;;
  reindex)
    cd "$QMD_DIR" && bun src/qmd.ts update
    ;;
  status)
    cd "$QMD_DIR" && bun src/qmd.ts status
    ;;
  *)
    echo "Usage: qmd-search.sh [search|vsearch|reindex|status] [query] [options]"
    echo "  search  <query>  - BM25 keyword search (~0.4s)"
    echo "  vsearch <query>  - Vector semantic search (~5s, no expansion model)"
    echo "  reindex          - Re-index all collections"
    echo "  status           - Show index status"
    ;;
esac
