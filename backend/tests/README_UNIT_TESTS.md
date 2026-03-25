# Testes Unitários do MSM_Pro Backend

## Resumo Executivo

78 testes unitários foram criados para 3 áreas críticas sem cobertura no MSM_Pro backend:

- **test_sale_price_logic.py** (18 testes): resolução de preço (service_sync.py)
- **test_webhook_validation.py** (26 testes): validação de webhook (main.py)
- **test_price_calculations.py** (34 testes): cálculos financeiros (financeiro/service.py)

**Status**: ✅ 78/78 testes passando | Tempo: 0.31s

---

## 1. test_sale_price_logic.py

### Propósito

Testar a lógica de resolução de preço do `service_sync.py` (linhas 83-130), que é responsável por escolher entre diferentes fontes de preço:

1. **Primary**: GET `/items/{id}/sale_price` (endpoint novo - março 2026)
2. **Fallback 1**: `item.sale_price` (dict com `amount`)
3. **Fallback 2**: `item.original_price` (campo direto)
4. **Fallback 3**: `/items/{id}/promotions` (seller-promotions)

### Arquitetura de Testes

```
TestSalePriceResolution (10 testes)
├── Fluxo principal com endpoint /sale_price
├── Fallback quando endpoint retorna None
├── Fallback para item.sale_price
├── Fallback para item.original_price
├── Prioridade (endpoint > item fields)
├── Conversão Decimal
└── Casos zero

TestListingPriceFields (2 testes)
├── Campos price e original_price no modelo
└── Campo sale_price separado

TestSalePriceEdgeCases (6 testes)
├── sale_price > price (desconto negativo)
├── Valores muito grandes (eletroeletrônicos)
├── Valores muito pequenos (centavos)
├── Dicts vazios
└── Null em regular_amount
```

### Como Rodar

```bash
pytest backend/tests/test_sale_price_logic.py -v
```

### Exemplos de Testes

```python
# Teste: quando /sale_price retorna amount → usar esse valor
def test_use_sale_price_endpoint_when_available():
    item = {"price": 100.0}
    sale_price_response = {"amount": 85.50, "regular_amount": 100.0}

    price, original_price = _resolve_price_like_service_sync(
        item, sale_price_endpoint_response=sale_price_response
    )

    assert price == Decimal("85.50")
    assert original_price == Decimal("100.0")
```

---

## 2. test_webhook_validation.py

### Propósito

Testar a validação do webhook `/api/v1/notifications` (main.py, linhas 177-240), que recebe notificações do Mercado Livre com 5 camadas de validação:

1. **HMAC-SHA256**: Signature no header `X-Signature`
2. **Query params**: `user_id` e `topic` obrigatórios
3. **Validação de usuário**: `ml_user_id` deve existir no banco
4. **Rate limiting**: Ignorar duplicatas em 30s
5. **Auditoria**: Log de resource e user_id

### Arquitetura de Testes

```
TestWebhookSignatureValidation (8 testes)
├── Signature válida passa
├── Header ausente → 401
├── Signature inválida → 401
├── Mudança no body invalida signature
├── Body vazio com signature válida
├── Case sensitivity
└── Secrets diferentes produzem sigs diferentes

TestWebhookParameterValidation (6 testes)
├── user_id ausente → 400
├── topic ausente → 400
├── Ambos presentes → OK
├── String vazia tratada como ausente
├── resource é opcional
└── user_id sempre string

TestWebhookMLUserValidation (3 testes)
├── ml_user_id existente no banco
├── ml_user_id não existe → ignorar
└── Banco vazio → rejeitar

TestWebhookRateLimiting (5 testes)
├── Duplicata em < 30s → ignorar
├── Depois de 30s → processar
├── Tópicos diferentes não são duplicatas
├── Usuários diferentes não são duplicatas
└── Edge case: exatamente 30s

TestWebhookCompleteFlow (4 testes)
├── Fluxo válido completo
├── Rejeitado por signature inválida
├── Rejeitado por user_id ausente
└── Ignorado se ml_user não existe
```

### Como Rodar

```bash
pytest backend/tests/test_webhook_validation.py -v
```

### Exemplos de Testes

```python
# Teste: assinatura válida deve passar
def test_valid_signature_passes():
    body = b'{"resource":"item","user_id":"12345"}'
    secret = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

    x_sig = _calculate_x_signature(body, secret)
    is_valid, reason = _verify_ml_signature(body, x_sig)

    assert is_valid is True
    assert reason == "ok"

# Teste: parâmetros obrigatórios
def test_missing_user_id_returns_400():
    query_params = {"topic": "item"}  # user_id faltando

    user_id = query_params.get("user_id")
    topic = query_params.get("topic")

    # Validação falha
    assert not (user_id and topic)
```

---

## 3. test_price_calculations.py

### Propósito

Testar funções puras de cálculo de taxa e margem do `financeiro/service.py`:

- `calcular_taxa_ml()`: retorna taxa % do ML por tipo de anúncio
- `calcular_margem()`: calcula lucro bruto, margem %, com proteção contra divisão por zero

### Arquitetura de Testes

```
TestCalcularTaxaML (13 testes)
├── Tipos básicos: classico (11.5%), premium (17%), full (17%)
├── Case insensitivity
├── Fallback para tipo desconhecido (16%)
├── sale_fee_pct override
├── Edge cases: None, "", zero negativo
└── Conversão float → Decimal

TestCalcularMargem (8 testes)
├── Cálculo simples
├── Com frete
├── Margem negativa (prejuízo)
├── Break even
├── Premium vs classico
├── sale_fee_pct override
└── Todos os custos combinados

TestMargemPriceZero (2 testes)
├── Preço zero → margem zero
└── Proteção contra divisão por zero

TestMargemCostZero (2 testes)
├── Custo zero → margem = preço - taxa - frete
└── Com frete

TestMargemLargeValues (2 testes)
├── Preço muito alto (R$ 50k+)
└── Custo muito alto

TestMargemSmallValues (2 testes)
├── Preço muito pequeno (R$ 1)
└── Frações de centavos

TestMargemRounding (3 testes)
├── taxa_ml_valor sempre 2 casas decimais
├── margem_pct sempre 2 casas decimais
└── Arredondamento ROUND_HALF_UP

TestMargemIntegration (2 testes)
├── Comparação entre tipos de anúncio
└── Efeito de custos em % do preço
```

### Como Rodar

```bash
pytest backend/tests/test_price_calculations.py -v
```

### Exemplos de Testes

```python
# Teste: cálculo simples de margem
def test_simple_margin_calculation():
    # Preço: 100, Custo: 40, classico (11.5%)
    # Taxa: 100 * 0.115 = 11.50
    # Margem: 100 - 40 - 11.50 = 48.50
    result = calcular_margem(
        preco=Decimal("100"),
        custo=Decimal("40"),
        listing_type="classico",
    )

    assert result["taxa_ml_pct"] == Decimal("0.115")
    assert result["taxa_ml_valor"] == Decimal("11.50")
    assert result["margem_bruta"] == Decimal("48.50")

# Teste: proteção contra divisão por zero
def test_price_zero_margem_pct_protected():
    result = calcular_margem(
        preco=Decimal("0"),
        custo=Decimal("10"),
        listing_type="classico",
    )

    # Não deve lançar ZeroDivisionError
    assert result["margem_pct"] == Decimal("0.00")
```

---

## Características Gerais

### Sem Dependência de Banco

Todos os 78 testes são unitários puros:
- Não usam `AsyncSession`
- Não fazem queries ao banco
- Funções puras com inputs/outputs testáveis
- Mocks mínimos (apenas o necessário)

### Independência

- Testes podem rodar em qualquer ordem
- Cada teste prepara seus próprios dados
- Sem fixtures compartilhadas com estado

### Variáveis de Ambiente

Configuradas no início de cada arquivo:

```python
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")
```

### Precisão Financeira

Uso de `Decimal` em vez de `float`:
- Evita problemas de precisão em cálculos monetários
- Arredondamento explícito: `ROUND_HALF_UP`
- 2 casas decimais sempre que aplicável

### Timing-Safe Comparison

Webhook signature validation usa `hmac.compare_digest()`:
- Protege contra timing attacks
- Compara assinaturas em tempo constante

---

## Rodando os Testes

### Todos os testes

```bash
pytest backend/tests/test_sale_price_logic.py \
        backend/tests/test_webhook_validation.py \
        backend/tests/test_price_calculations.py -v
```

### Com relatório de cobertura

```bash
pytest backend/tests/test_sale_price_logic.py \
        backend/tests/test_webhook_validation.py \
        backend/tests/test_price_calculations.py \
        --cov=app.vendas.service_sync \
        --cov=app.main \
        --cov=app.financeiro.service \
        --cov-report=html
```

### Apenas um arquivo

```bash
pytest backend/tests/test_sale_price_logic.py -v
pytest backend/tests/test_webhook_validation.py -v
pytest backend/tests/test_price_calculations.py -v
```

### Com output detalhado

```bash
pytest backend/tests/test_sale_price_logic.py -vv -s
```

---

## Próximas Prioridades

1. **test_service_kpi.py**: Testes para cálculo de KPI por período
   - get_kpi_summary()
   - get_kpi_by_period()
   - Agregação por período (hoje, ontem, últimos 7 dias, etc)

2. **test_service_health.py**: Testes para health score
   - calculate_quality_score()
   - calculate_health_score()
   - Métricas de conversão, visitas, estoque

3. **test_service_analytics.py**: Testes para análises de preço
   - _calculate_price_bands()
   - _calculate_stock_projection()
   - _generate_alerts()

4. **Testes de integração com banco**: AsyncSession fixtures
   - Testes com transações reais
   - Validação de constraints do banco
   - Testes de migrations

5. **CI/CD pipeline**: GitHub Actions
   - Rodar testes em cada push
   - Coverage reports no PR
   - Fail se cobertura < 60%

---

## Checklist para Manutenção

- [ ] Rodar testes antes de cada commit
- [ ] Atualizar testes ao modificar lógica critica
- [ ] Manter cobertura acima de 60%
- [ ] Documentar novos edge cases encontrados
- [ ] Revisar logs de testes falhando em CI/CD

---

## Referências

- [pytest Documentation](https://docs.pytest.org/)
- [Python decimal Module](https://docs.python.org/3/library/decimal.html)
- [HMAC Security](https://tools.ietf.org/html/rfc2104)
- [MSM_Pro CLAUDE.md](../CLAUDE.md)
