"""Utilitarios compartilhados do core."""

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(filepath: Path, data: dict | list) -> None:
    """
    Escreve JSON de forma atomica (temp + rename) para evitar corrupcao.

    Cria um arquivo temporario no mesmo diretorio e faz rename atomico.
    Se ocorrer erro durante a escrita, o arquivo original permanece intacto.

    Args:
        filepath: caminho do arquivo JSON destino.
        data: dados para serializar como JSON.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=filepath.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, str(filepath))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
