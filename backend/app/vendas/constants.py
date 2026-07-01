"""Constantes compartilhadas do domínio de vendas.

Fonte única da regra "o que conta como venda", para não espalhar literais.
"""

# Status de pagamento que NÃO contam como venda realizada no total.
#
# "refunded" foi REMOVIDO desta lista (2026-07-01): a venda aconteceu e o painel
# do Mercado Livre a mantém no total (o order.status segue "paid"); o reembolso é
# uma DEVOLUÇÃO, marcada à parte via ListingSnapshot.returns_count/returns_revenue
# e descontada em `vendas_concluidas`. Espelhar o ML é o princípio mestre.
#
# "cancelled"/"rejected" = venda que não se concretizou → continuam fora do total.
NON_SALE_PAYMENT_STATUSES = ["cancelled", "rejected"]

# Status usados para filtrar CANCELAMENTOS/estornos na visão do ML (order.status).
# Mantém "refunded"/"rejected" p/ compatibilidade de leitura de payloads do ML.
CANCEL_STATUSES = ["cancelled", "refunded", "rejected"]
