# UX/Design Recommendations — MSM_Pro
**Focus:** Simplify. Make decisions 10x faster.

---

## Problem Statement

User opens dashboard. Sees:
- 16 anúncios (tabela)
- 10 KPI cards (diferentes)
- 4 gráficos
- 70+ números

**Result:** Paralysis. "Qual métrica olho primeiro?"

**Time to decision:** 20+ minutos (ou fecha app e volta depois)

---

## Solution: Hierarchy of Information

### Layer 1: URGENT (Red Zone)
**Show ONLY if something broke.** 1-3 cards max.

```
┌─────────────────────────────────────┐
│ 🔴 AÇÃO URGENTE (red background)    │
├─────────────────────────────────────┤
│ 2 anúncios sem vendas há 3 dias      │
│ → Ação: Reduzir preço 10-15%        │
│ → Estimado: +R$ 200/dia             │
├─────────────────────────────────────┤
│ Estoque crítico: 5 unidades         │
│ → Ação: Encomendar agora            │
│ → Falta em: 8 dias                  │
└─────────────────────────────────────┘
```

### Layer 2: OPPORTUNITIES (Yellow Zone)
**Show if good things can happen.** 2-3 cards.

```
┌─────────────────────────────────────┐
│ 🟡 OPORTUNIDADES (yellow background) │
├─────────────────────────────────────┤
│ MLB-ABC tem conversão 4.2%           │
│ → Sugestão: Aumentar preço 5%       │
│ → Estimado: +R$ 150 margem/semana   │
│ → Confiança: 82%                    │
└─────────────────────────────────────┘
```

### Layer 3: METRICS (Green Zone)
**Show if everything OK.** 5 KPI cards.

```
┌──────────────────────────────────────────┐
│ 🟢 RESUMO (green/neutral background)     │
├──────────────────────────────────────────┤
│  Receita: R$ 850  ↑ 12% vs ontem        │
│  Conversão: 2.3%  ↓ 0.2pp vs ontem      │
│  Estoque: 145     ↓ 8 unidades          │
│  Margem: 38%      ↔ vs ontem            │
│  Visitas: 320     ↑ 25 visitas          │
└──────────────────────────────────────────┘
```

### Layer 4: DETAILED (Below the fold)
**Show if user scrolls or clicks.** Table + graphs.

```
Tabela de anúncios (expandable)
↓ (scroll down)
Gráficos históricos
↓ (click tabs)
Outras análises (Financeiro, Pareto, etc.)
```

---

## Morning Routine Card (Proposed Design)

### Flow 1: RED ALERT
```
╔════════════════════════════════════════╗
║  🔴 AÇÃO URGENTE — 2 itens            ║
║                                         ║
║  MLB-XYZ "Suporte Celular"             ║
║  └─ Sem vendas há 3 dias               ║
║  └─ Estoque: 45 unid                   ║
║  └─ Último preço: R$ 189               ║
║                                         ║
║  ► SUGESTÃO: Reduzir 10% → R$ 170     ║
║    • Razão: Conversão caiu 1.5pp       ║
║    • Estimado: +3 vendas/dia (+R$ 450) ║
║    • Confiança: 78%                    ║
║                                         ║
║  [ Aplicar Agora ]  [ Ignorar ]        ║
║                                         ║
║  ─────────────────────────────────────  ║
║                                         ║
║  Estoque Crítico                        ║
║  └─ "Chaveiro Automotivo": 5 unid      ║
║  └─ Falta em: 8 dias                   ║
║  └─ Encomendar agora                   ║
║                                         ║
║  [ Adicionar à Lista ]                 ║
║                                         ║
╚════════════════════════════════════════╝
```

### Flow 2: GOOD NEWS (Yellow)
```
╔════════════════════════════════════════╗
║  🟡 OPORTUNIDADE — 1 item             ║
║                                         ║
║  MLB-ABC "Pedal Shift"                 ║
║  └─ Conversão alta: 4.2%               ║
║  └─ Preço atual: R$ 249                ║
║                                         ║
║  ► SUGESTÃO: Aumentar 5% → R$ 262     ║
║    • Razão: Demanda alta, estoque OK   ║
║    • Estimado: +R$ 180 margem/semana   ║
║    • Confiança: 85%                    ║
║                                         ║
║  [ Aplicar Agora ]  [ A/B Test ]       ║
║                                         ║
╚════════════════════════════════════════╝
```

### Flow 3: ALL GOOD (Green)
```
╔════════════════════════════════════════╗
║  🟢 RESUMO DO DIA — Tudo bem           ║
║                                         ║
║  Receita:     R$ 850  ↑ 12% vs ontem  ║
║  Conversão:   2.3%    (normal)        ║
║  Estoque:     145 un  (saudável)      ║
║  Margem:      38%     ↔ vs ontem      ║
║  Visitas:     320     ↑ 25 vs ontem   ║
║                                         ║
║  Nenhuma ação recomendada no momento. ║
║                                         ║
╚════════════════════════════════════════╝
```

---

## Dashboard Layout (Proposed)

```
┌─────────────────────────────────────────────────────┐
│ MSM_Pro — Maikeo (Conta: MSM_PRIME)   [≡ Menu] [👤] │
├─────────────────────────────────────────────────────┤
│                                                     │
│ [Morning Routine Card — Sticky at top]            │
│ ╔═════════════════════════════════════════════╗    │
│ ║ 🔴 AÇÃO URGENTE | 🟡 OPORTUNIDADES | 🟢 OK ║    │
│ ║ [Card content above]                       ║    │
│ ╚═════════════════════════════════════════════╝    │
│                                                     │
│ [5 KPI Cards — In horizontal row]                 │
│ ┌──────────────────────────────────────────────┐   │
│ │ Receita  │ Conversão │ Estoque │ Margem │ ... │   │
│ │ R$ 850   │ 2.3%      │ 145 un  │ 38%    │    │   │
│ │ ↑ 12%    │ ↓ 0.2pp   │ ↓ 8 un  │ ↔     │    │   │
│ └──────────────────────────────────────────────┘   │
│                                                     │
│ [Anúncios Table — expandable by period]           │
│ ┌──────────────────────────────────────────────┐   │
│ │ 📊 Anúncios (Hoje | 7d | 15d | 30d | 60d)  │   │
│ │                                              │   │
│ │ ┌────┬─────────────┬────────┬────────┬────┐ │   │
│ │ │MLB │ Título      │ Preço  │ Vendas │ ... │ │   │
│ │ │XYZ │ Suporte...  │ R$ 189 │ 5      │    │ │   │
│ │ │ABC │ Pedal...    │ R$ 249 │ 8      │    │ │   │
│ │ │... │ ...         │ ...    │ ...    │ ..│ │   │
│ │ └────┴─────────────┴────────┴────────┴────┘ │   │
│ └──────────────────────────────────────────────┘   │
│                                                     │
│ [Expandable Tabs — below]                         │
│ ├─ 📈 Gráficos Históricos (preço x conversão)    │
│ ├─ 💰 Financeiro (receita, taxa, margem)         │
│ ├─ 🧠 Intel (Pareto, Forecast)                   │
│ └─ ⚙️ Configurações                              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Mobile Version

```
┌─────────────────────────┐
│ MSM_Pro [≡]             │ <- Compact header
├─────────────────────────┤
│ 🔴 AÇÃO URGENTE         │ <- Card
│                         │
│ Suporte sem vendas      │
│ → Reduzir preço 10%     │
│ [ Aplicar ] [ Ignorar ] │
│                         │
├─────────────────────────┤
│ Receita     R$ 850      │ <- Compact KPI
│ Conversão   2.3%        │
│ Estoque     145 un      │
│ Margem      38%         │
├─────────────────────────┤
│ Anúncios (16)           │ <- List, swipeable
│ > Suporte Celular       │
│   5 vendas • R$ 189     │
│ > Pedal Shift           │
│   8 vendas • R$ 249     │
│ > ...                   │
├─────────────────────────┤
│ [Gráficos] [Intel] [⚙️] │ <- Bottom tabs
└─────────────────────────┘
```

---

## Color Scheme

```
RED ZONE (Urgent):
├─ Background: #FEE2E2 (light red)
├─ Border: #DC2626 (dark red)
├─ Icon: 🔴 or ⚠️
└─ Text: #7F1D1D (dark red text)

YELLOW ZONE (Opportunity):
├─ Background: #FEF3C7 (light yellow)
├─ Border: #F59E0B (amber)
├─ Icon: 🟡 or 💡
└─ Text: #78350F (dark amber text)

GREEN ZONE (OK):
├─ Background: #F0FDF4 (light green)
├─ Border: #22C55E (green)
├─ Icon: 🟢 or ✓
└─ Text: #15803D (dark green text)

NEUTRAL:
├─ Background: #F8FAFC (slate)
├─ Border: #CBD5E1 (slate)
├─ Icon: 📊 or 📈
└─ Text: #1E293B (slate-900)
```

---

## Information Hierarchy (What to Hide)

### HIDE by Default (Move to Tabs/Drawer)
- ❌ Modules: Perguntas, Reputação, Atendimento
- ❌ Historical graphs (heatmap de vendas por hora)
- ❌ Detailed competitor analysis
- ❌ Advanced settings

### SHOW Always
- ✅ Morning Routine Card (sticky)
- ✅ 5 KPI Cards (at glance)
- ✅ Anúncios Table (filterable)
- ✅ Call to action buttons (Aplicar Preço, Alertar)

### SHOW on Click
- ✅ Histórico de preços (click anúncio)
- ✅ Gráficos de conversão (click anúncio)
- ✅ Detalhes financeiros (tab)
- ✅ Intel/Pareto (tab)

---

## Interaction Design

### Action Flow 1: Apply Price Suggestion
```
User sees: "MLB-XYZ: Sugestão aumentar para R$ 262"
  ↓
Click: "Aplicar Agora"
  ↓
Modal: "Confirmar? Aumentar R$ 249 → R$ 262 (5%)"
  ↓
[ Aplicar ]  [ Cancelar ]
  ↓
Backend: Apply via ML API
  ↓
Toast: "✓ Preço atualizado em R$ 262"
  ↓
Listing table: Mostra novo preço
  ↓
Log: Rastreia mudança (audit trail)
```

### Action Flow 2: Ignore Alert & Snooze
```
User sees: Alert "Sem vendas há 3 dias"
  ↓
Click: "Ignorar"
  ↓
Modal: "Ignorar até quando?"
  [ 6 horas ]  [ 24 horas ]  [ 1 semana ]
  ↓
Dismisses card, reaparece no tempo escolhido
```

### Action Flow 3: A/B Test Price
```
User sees: Opportunity "Aumentar preço"
  ↓
Click: "A/B Test"
  ↓
Modal:
  Preço A: R$ 249 (50% das vendas)
  Preço B: R$ 262 (50% das vendas)
  Duração: 7 dias
  ↓
[ Confirmar ]  [ Voltar ]
  ↓
Backend: Randomly assigns 50% of visitors to each price
  ↓
Report: Após 7 dias, mostra qual preço teve melhor conversão
```

---

## Copy & Tone

### Bad (Confusing)
- "Conversion rate delta: -0.2pp vs 24h baseline"
- "Revenue trajectory exhibits positive slope"

### Good (Clear)
- "Conversão caiu 0.2% desde ontem — anúncio perdendo posição?"
- "Receita subiu 12% — dia bom!"
- "Reduzir preço 10% deve recuperar vendas perdidas"

---

## Accessibility

### For Non-Tech Users (like Maikeo)
- Use emojis (not just colors)
- Use Portuguese, not English
- Avoid jargon (say "Reduza preço" not "Implement price elasticity algorithm")
- Tooltips for every number (why this metric matters)

### Colors & Contrast
- WCAG AA compliant
- Red/Green colorblind safe (use symbols too)
- Font: 16px minimum on mobile
- Touch targets: 48x48px minimum

---

## Performance

- Morning Routine card: Load in <500ms
- Full dashboard: <2 seconds
- Table sorting: <200ms
- Modal opening: instant

---

## Metrics to Track (Analytics)

```
├─ Time to first decision (goal: <5 min)
├─ % users applying price suggestions
├─ % users dismissing alerts
├─ % users using A/B testing
├─ % users scrolling to see anúncios table
└─ % users jumping to other tabs
```

If >50% users scroll past Morning Routine card without acting:
→ Card design is not compelling enough. Redesign.

---

## Next Steps

1. **Design System:** Create Figma component library
2. **Prototype:** Morning Routine card high-fidelity mockup
3. **Test:** Show to 3-5 importadores, get feedback
4. **Iterate:** Adjust based on feedback
5. **Dev:** Frontend implement, backend support
6. **Launch:** A/B test old vs new dashboard design

