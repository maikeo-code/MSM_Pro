# SWARM GENESIS v6.0 — RELATORIO COMPLETO
Gerado em: 17/03/2026 21:44

## SAUDE DO SISTEMA
  Ciclos completos: 97
  Regras: 10 ativas | 0 deprecadas
  Feedbacks: 8 | Sucessos: 5 | Falhas abertas: 0
  Agentes: 20 ativos | 0 elite | 0 aposentados
  Memoria: 2 episodios | 7 fatos | 3 padroes

## CHECKPOINT DA SESSAO (v6)

  Ultimo checkpoint: ID=13 | Ciclo=27 | Fase=correction
  Registrado em: 2026-03-17 19:22:30
  Sessao retomada de checkpoint: NAO

## MUDANCAS DE CODIGO (v6)

  Total de mudancas registradas: 0
  Revertidas (rollback):          0
  Aguardando teste:               0

## USO DE TOKENS (v6)

  Total de tokens consumidos: 0
  Por agente (top 5):
    : 0 tokens

## LOG DE ACOES — RESUMO POR AGENTE (v6)

  Total de acoes registradas: 6
  unknown                        ###### (6)

## SCORES POR AREA

  #######     75.0 | features
  #######     72.5 | deploy
  ######      67.0 | frontend
  ######      64.4 | architecture
  ######      63.9 | code_quality
  #####       57.7 | security
  #####       51.7 | error_handling
  ####        48.1 | testing

## EVOLUCAO ENTRE CICLOS

  Ciclo  93 | Score:  92 | Q:0 F:0 I:0 | Ciclo 93 - Verificacao testes - 172 passando, cobertura ~45%
  Ciclo  94 | Score:  92 | Q:0 F:0 I:0 | Ciclo 94 - Verificacao arquitetura - vendas 7 modulos, tasks
  Ciclo  95 | Score:  92 | Q:0 F:0 I:0 | Ciclo 95 - Verificacao deploy - supervisord 3 processos, Rai
  Ciclo  96 | Score:  92 | Q:0 F:0 I:0 | Ciclo 96 - Verificacao frontend - error states, empty states
  Ciclo  97 | Score:  92 | Q:0 F:0 I:0 | Ciclo 97 - Verificacao financeiro - P&L dedup, revenue fallb

## PERFORMANCE DOS AGENTES

  ACTIVE  | ########    80.0 | orquestrador-v5 (evolution)
  ACTIVE  | #######     70.0 | meta-agente (evolution)
  ACTIVE  | ######      65.0 | mediador (evolution)
  ACTIVE  | ######      65.0 | destilador (evolution)
  ACTIVE  | ######      65.0 | interrogador-hip (evolution)
  ACTIVE  | ######      60.0 | criador (evolution)
  ACTIVE  | #####       55.0 | cientista (evolution)
  ACTIVE  | #####       50.0 | curiosa (learning)
  ACTIVE  | #####       50.0 | respondedora (learning)
  ACTIVE  | #####       50.0 | confrontadora (learning)
  ACTIVE  | #####       50.0 | analista (learning)
  ACTIVE  | #####       50.0 | orchestrator (development)
  ACTIVE  | #####       50.0 | critic (development)
  ACTIVE  | #####       50.0 | developer (development)
  ACTIVE  | #####       50.0 | tester (development)

## PADROES DESCOBERTOS

  [ANTI-PADRAO] [1x] Comentario no codigo diz criptografado mas implementacao usa plaintext. Sempre v
  [SUCESSO] [1x] Custom SQLAlchemy TypeDecorator e a melhor forma de encriptar colunas transparen
  [SUCESSO] [1x] Testes devem evitar imports de modulos com dependencias pesadas (celery, bcrypt)

## TOP REGRAS APRENDIDAS

  [0.99] Usar PyJWT (nao python-jose) para JWT. python-jose tem CVEs conhecidas e nao e m
  [0.95] Sempre usar EncryptedString (Fernet) para armazenar tokens OAuth no banco. NUNCA
  [0.95] Sempre usar or 0 / or Decimal(0) em sum() de colunas nullable do banco. sum(s.fi
  [0.95] Sempre usar async with MLClient() as client para garantir cleanup de conexoes. N
  [0.95] Default de debug em producao deve ser False, nao True. A aplicacao deve ser segu
  [0.90] Todo app FastAPI deve ter @app.exception_handler(Exception) global que loga erro
  [0.90] ReactQueryDevtools deve ser lazy-loaded apenas em import.meta.env.DEV. Nunca inc

## CONHECIMENTO SOBRE O PROJETO

  [arquitetura]
    backend_overview: 10,643 linhas. 15 modelos SQLAlchemy. 9 routers com ~50 endp
    frontend_overview: React 18 + TS + Vite + Tailwind. 12 paginas, 6 componentes, 
    celery_tasks: 8 tasks: sync_all_snapshots (diario 06:00 BRT), sync_recent_
  [divida_tecnica]
    arquivos_grandes: vendas/service.py=2109, jobs/tasks.py=1366, client.py=700, f
  [pontos_fortes]
    coisas_boas: Auth JWT funciona. OAuth multi-conta funciona. 8 Celery task
  [riscos]
    security_critical: 3 CRITICOS: (1) Tokens OAuth em plaintext no PostgreSQL, (2)
  [verificacao]
    divisao_por_zero: Todas as 13 divisoes em service.py e financeiro/service.py t
