"""Interruptor da resposta automática de perguntas (AUTO_ANSWER_MODE).

Decisão do Maikeo (25/09 e 29/09/2026): nada é enviado ao comprador sem aprovação.
  - "rascunho" (padrão): a IA gera a sugestão, NADA é enviado; o Maikeo aprova em /perguntas
  - "off": nem envia nem pré-gera sugestão
  - "auto": comportamento antigo (envia confidence=high)
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

MOD = "app.jobs.tasks_auto_answer"


def _db_com_perguntas(n: int):
    """Sessão falsa cujo SELECT devolve n pares (pergunta, conta)."""
    rows = []
    for i in range(n):
        q = MagicMock()
        q.id = f"q-{i}"
        q.ai_suggestion_text = f"resposta {i}"
        acc = MagicMock()
        acc.id = "acc-1"
        acc.access_token = "tok"
        rows.append((q, acc))
    result = MagicMock()
    result.all.return_value = rows
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, db


class TestConfigPadrao:
    def test_padrao_e_rascunho(self):
        from app.core.config import Settings

        assert Settings().auto_answer_mode == "rascunho"


class TestAutoAnswerMode:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("modo", ["rascunho", "off"])
    async def test_nao_envia_fora_do_modo_auto(self, modo):
        from app.jobs.tasks_auto_answer import _auto_answer_high_confidence_async

        ctx, _ = _db_com_perguntas(3)
        with patch(f"{MOD}.settings") as s, \
             patch(f"{MOD}.AsyncSessionLocal", return_value=ctx), \
             patch(f"{MOD}.answer_question_and_track", new_callable=AsyncMock) as enviar:
            s.auto_answer_mode = modo
            result = await _auto_answer_high_confidence_async()

        enviar.assert_not_called()
        assert result["sent"] == 0
        assert result["mode"] == modo
        assert result["pending_high"] == 3

    @pytest.mark.asyncio
    async def test_modo_auto_envia(self):
        from app.jobs.tasks_auto_answer import _auto_answer_high_confidence_async

        ctx, _ = _db_com_perguntas(2)
        with patch(f"{MOD}.settings") as s, \
             patch(f"{MOD}.AsyncSessionLocal", return_value=ctx), \
             patch(f"{MOD}.answer_question_and_track", new_callable=AsyncMock) as enviar:
            s.auto_answer_mode = "auto"
            result = await _auto_answer_high_confidence_async()

        assert enviar.await_count == 2
        assert all(c.kwargs["source"] == "ai_auto" for c in enviar.await_args_list)
        assert result["sent"] == 2
        assert result["mode"] == "auto"

    @pytest.mark.asyncio
    async def test_valor_desconhecido_nao_envia(self):
        """Erro de digitação na variável (ex.: 'Auto ') nunca pode ligar o envio por engano."""
        from app.jobs.tasks_auto_answer import _auto_answer_high_confidence_async

        ctx, _ = _db_com_perguntas(1)
        with patch(f"{MOD}.settings") as s, \
             patch(f"{MOD}.AsyncSessionLocal", return_value=ctx), \
             patch(f"{MOD}.answer_question_and_track", new_callable=AsyncMock) as enviar:
            s.auto_answer_mode = "automatico"
            result = await _auto_answer_high_confidence_async()

        enviar.assert_not_called()
        assert result["sent"] == 0

    @pytest.mark.asyncio
    async def test_off_nao_pre_gera_sugestao(self):
        from app.jobs.tasks_auto_answer import _pre_generate_suggestions_async

        with patch(f"{MOD}.settings") as s, \
             patch(f"{MOD}.AsyncSessionLocal") as sessao, \
             patch(f"{MOD}.generate_suggestion", new_callable=AsyncMock) as gerar:
            s.auto_answer_mode = "off"
            result = await _pre_generate_suggestions_async()

        sessao.assert_not_called()
        gerar.assert_not_called()
        assert result["generated"] == 0

    @pytest.mark.asyncio
    async def test_rascunho_continua_pre_gerando(self):
        from app.jobs.tasks_auto_answer import _pre_generate_suggestions_async

        ctx, _ = _db_com_perguntas(2)
        with patch(f"{MOD}.settings") as s, \
             patch(f"{MOD}.AsyncSessionLocal", return_value=ctx), \
             patch(f"{MOD}.generate_suggestion", new_callable=AsyncMock) as gerar:
            s.auto_answer_mode = "rascunho"
            result = await _pre_generate_suggestions_async()

        assert gerar.await_count == 2
        assert result["generated"] == 2
