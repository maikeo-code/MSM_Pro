# Kit de Auto-Aprendizado — Como Usar

## O que e?

Um sistema de **13 IAs** que analisam, desenvolvem e aprendem sobre seu projeto:

### Grupo: Auto-Aprendizado (4 IAs) — loop infinito
| Agente | Nivel | Funcao |
|--------|:-----:|--------|
| **Curiosa** | L1 | Gera perguntas sem parar |
| **Respondedora** | L1 | Pesquisa respostas no codigo e docs |
| **Confrontadora** | L2 | Valida cada resposta com 3 testes |
| **Analista** | L3 | Sintetiza tudo, gera planos e regras |

### Grupo: Desenvolvimento (9 IAs) — do sistema original
| Agente | Nivel | Funcao |
|--------|:-----:|--------|
| **Orchestrator** | L3 | Coordenador central, distribui tarefas |
| **Critic** | L2 | Revisa todo codigo e decisoes |
| **Developer** | L1 | Implementa features e fixes |
| **Tester** | L1 | Roda testes, valida implementacoes |
| **Researcher** | L1 | Pesquisa solucoes e boas praticas |
| **Documenter** | L1 | Escreve e mantem documentacao |
| **Founder** | L2 | Valida APIs com fontes oficiais |
| **API Specialist** | L1 | Integracoes com APIs externas |
| **Security Agent** | L2 | Auditoria de seguranca e vulnerabilidades |

Tudo fica salvo em banco SQLite: o que deu certo (sucessos) e o que nao deu (falhas).

## Regra de ouro

**O sistema NAO modifica o codigo do projeto.**
Ele apenas LE para analisar e gera saidas na pasta `_auto_learning/`.

## Instalacao (1 comando)

```bash
# Copie esta pasta para qualquer lugar acessivel
# Depois rode apontando para o projeto alvo:

python instalar.py C:\caminho\do\seu\projeto

# Ou no Linux/Mac:
python instalar.py /home/user/meu-projeto

# Ou para o projeto atual:
python instalar.py .
```

## O que acontece na instalacao

1. Cria a pasta `_auto_learning/` dentro do projeto
2. Se o projeto ja tem CLAUDE.md -> **preserva** e apenas adiciona uma secao no final
3. Se nao tem CLAUDE.md -> cria um minimo
4. Faz backup automatico: `CLAUDE_backup_DATA.md`
5. Inicializa o banco SQLite com 7 tabelas
6. Cria os **13 agentes** + instrucoes + prompt de ativacao

## Estrutura criada no projeto

```
seu-projeto/
+-- CLAUDE.md                    <- Preservado! Secao adicionada no final
+-- _auto_learning/
    +-- engine.py                <- Motor do banco de dados
    +-- loop_runner.py           <- CLI para operacoes
    +-- INSTRUCOES_IA.md         <- A IA le isso para saber o que fazer
    +-- ATIVAR.md                <- Prompt para copiar/colar
    +-- db/
    |   +-- schema.sql           <- Estrutura das tabelas
    |   +-- learning.db          <- Banco SQLite
    +-- agents/                  <- 13 agentes
    |   +-- curiosa.md           <- [Learning] Gera perguntas
    |   +-- respondedora.md      <- [Learning] Responde
    |   +-- confrontadora.md     <- [Learning] Valida
    |   +-- analista.md          <- [Learning] Sintetiza
    |   +-- orchestrator.md      <- [Dev] Coordena
    |   +-- critic.md            <- [Dev] Revisa
    |   +-- developer.md         <- [Dev] Implementa
    |   +-- tester.md            <- [Dev] Testa
    |   +-- researcher.md        <- [Dev] Pesquisa
    |   +-- documenter.md        <- [Dev] Documenta
    |   +-- founder.md           <- [Dev] Valida APIs
    |   +-- api-specialist.md    <- [Dev] APIs externas
    |   +-- security-agent.md    <- [Dev] Seguranca
    +-- planos/                  <- Planos de melhoria gerados
    |   +-- aprovados/
    |   +-- rejeitados/
    +-- docs/
    |   +-- analises/            <- Analises periodicas
    +-- regras/                  <- Regras aprendidas
    |   +-- deprecadas/
    +-- logs/
    +-- exports/
```

## Como ativar

1. Abra o terminal no projeto
2. Execute `claude`
3. Cole o prompt de `_auto_learning/ATIVAR.md`
4. O loop comeca e roda infinitamente ate voce dizer "pare"

## Como funciona o ciclo

```
Curiosa gera perguntas
       |
Respondedora busca respostas (com ajuda de Researcher)
       |
Confrontadora valida (aprova/rejeita)
       |
  +---------+
  |         |
Sucesso   Falha
(banco)   (banco)
       |
Analista sintetiza (a cada 5 ciclos)
       |
  +---------+
  |         |
Regras    Planos  <-- Critic revisa, Security audita
       |
Novas direcoes -> Curiosa (volta ao topo)
```

Os agentes de desenvolvimento (Orchestrator, Developer, Tester, etc.)
sao ativados quando o loop identifica tarefas que precisam de implementacao.

## Niveis de autoridade

- **L3** (Orchestrator, Analista): Decisao final, coordena todos
- **L2** (Critic, Confrontadora, Founder, Security): Podem BLOQUEAR tarefas
- **L1** (Developer, Tester, Researcher, Documenter, Curiosa, Respondedora, API Specialist): Executam

## Banco de dados (7 tabelas)

| Tabela | Proposito |
|--------|-----------|
| `feedbacks` | Toda interacao (pergunta + resposta + feedback) |
| `sucessos` | O que deu certo (score crescente) |
| `falhas` | O que nao deu certo (tracking de nao-resolvidos) |
| `cycles` | Ciclos do loop |
| `generated_questions` | Perguntas da Curiosa |
| `consensus` | Acordo entre IAs |
| `learned_rules` | Regras aprendidas (ativas ou deprecadas) |

## Comandos uteis

```bash
# Ver status
python _auto_learning/loop_runner.py status

# Ver contexto completo
python _auto_learning/loop_runner.py get-context

# Exportar tudo em JSON
python _auto_learning/loop_runner.py export
```

## Perguntas frequentes

**P: E se meu projeto ja tem CLAUDE.md?**
R: O instalador FAZ BACKUP e apenas ADICIONA uma secao no final. Nada e perdido.

**P: O sistema modifica meu codigo?**
R: NAO. Tudo fica dentro de `_auto_learning/`. O codigo e read-only.

**P: Posso instalar em varios projetos?**
R: Sim. Cada instalacao e independente com seu proprio banco.

**P: Como desinstalar?**
R: Delete a pasta `_auto_learning/` e remova a secao do CLAUDE.md.

**P: Os agentes de dev sao os mesmos do sistema antigo?**
R: Sim, todos os 9 originais (orchestrator, critic, developer, tester, researcher,
documenter, founder, api-specialist, security-agent) foram incorporados + 4 novos
de auto-aprendizado (curiosa, respondedora, confrontadora, analista).
