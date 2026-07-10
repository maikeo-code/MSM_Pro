#!/usr/bin/env bash
#
# install_hooks.sh — instala os git hooks versionados do MSM_Pro.
#
# Os hooks vivem em scripts/hooks/ (rastreados pelo git). O diretorio .git/hooks/
# NAO vai pro git, entao cada clone/maquina precisa rodar este instalador uma vez
# para ativar a rede de regressao (pre-commit que bloqueia quebra do nucleo de
# metricas). Ver Definition of Done em CLAUDE.md e docs/handoff/.
#
# Uso:
#   bash scripts/install_hooks.sh
#
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SRC="$ROOT/scripts/hooks"
DST="$ROOT/.git/hooks"

if [ ! -d "$SRC" ]; then
  echo "ERRO: $SRC nao existe." >&2
  exit 1
fi

mkdir -p "$DST"
count=0
for hook in "$SRC"/*; do
  name="$(basename "$hook")"
  cp "$hook" "$DST/$name"
  chmod +x "$DST/$name"
  echo "[install_hooks] instalado: .git/hooks/$name"
  count=$((count + 1))
done

echo "OK $count hook(s) instalado(s). A rede de regressao esta ativa."
