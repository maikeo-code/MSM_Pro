"""
conftest.py — Setup global para testes do MSM_Pro.

Injeta variáveis de ambiente ANTES de qualquer import do app para que
o database.py use SQLite in-memory em vez de PostgreSQL.

Também importa todos os modelos para que o SQLAlchemy resolva os
relacionamentos antes de criar as tabelas.
"""
import os

# Variáveis ANTES de qualquer import do app — o conftest é carregado primeiro.
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-32chars!"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Importa todos os modelos para que o SQLAlchemy registre os mappers
# e resolva relacionamentos entre tabelas antes de criar o schema.
import app.auth.models  # noqa: F401, E402
import app.produtos.models  # noqa: F401, E402
import app.vendas.models  # noqa: F401, E402
import app.concorrencia.models  # noqa: F401, E402
import app.alertas.models  # noqa: F401, E402
import app.reputacao.models  # noqa: F401, E402
import app.ads.models  # noqa: F401, E402
import app.intel.models  # noqa: F401, E402
import app.financeiro.models  # noqa: F401, E402
import app.atendimento.models  # noqa: F401, E402
import app.notifications.models  # noqa: F401, E402
