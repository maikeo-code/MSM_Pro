"""
Janela de busca do sync_orders — autocura depois de pane.

Incidente de 25/09/2026: o Postgres lotou de 13/09 a 25/09 e o sync_orders olhava sempre os
ultimos 3 dias. Tudo o que caiu fora dessa janela virou buraco permanente (SC sem nenhum
pedido de 14/09 a 24/09; as duas contas sem pedidos de 31/08 a 07/09). A janela passa a
comecar no ultimo pedido GRAVADO daquela conta (menos 1 dia de folga), com teto de 60 dias.
"""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")

from app.jobs.tasks_orders import inicio_janela_pedidos  # noqa: E402

BRT = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 9, 25, 16, 0, tzinfo=BRT)


def test_sem_pedido_gravado_usa_3_dias():
    assert inicio_janela_pedidos(None, AGORA) == datetime(2026, 9, 22, 0, 0, tzinfo=BRT)


def test_pedido_recente_mantem_3_dias():
    ultimo = AGORA - timedelta(hours=5)
    assert inicio_janela_pedidos(ultimo, AGORA) == datetime(2026, 9, 22, 0, 0, tzinfo=BRT)


def test_pane_de_12_dias_volta_ate_o_ultimo_pedido():
    ultimo = datetime(2026, 9, 13, 20, 56, tzinfo=timezone.utc)  # SC em 25/09
    assert inicio_janela_pedidos(ultimo, AGORA) == datetime(2026, 9, 12, 0, 0, tzinfo=BRT)


def test_teto_de_60_dias():
    ultimo = AGORA - timedelta(days=200)
    assert inicio_janela_pedidos(ultimo, AGORA) == datetime(2026, 7, 27, 0, 0, tzinfo=BRT)


def test_sempre_meia_noite_brt():
    ultimo = datetime(2026, 9, 10, 2, 30, tzinfo=timezone.utc)  # 09/09 23:30 BRT
    r = inicio_janela_pedidos(ultimo, AGORA)
    assert (r.hour, r.minute, r.utcoffset()) == (0, 0, timedelta(hours=-3))
    assert r.date() == datetime(2026, 9, 8).date()
