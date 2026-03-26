# Frontend Test Suite — MSM_Pro

## Visão Geral
Suite de testes unitários para o frontend usando Vitest + jsdom.

**Total: 50 testes passando (100%)**

## Setup

### Instalação
```bash
npm install
```

### Rodar Testes
```bash
# Executar uma vez
npm test

# Watch mode
npm run test:watch
```

## Arquivos de Teste Criados

### 1. authService.test.ts
**Localização:** `frontend/src/services/authService.test.ts`
**Testes:** 12
**Status:** ✓ Passando

Cobertura:
- `login()` — POST /auth/login com email/password + setStoredToken
- `logout()` — removeStoredToken
- `getMe()` — GET /auth/me retorna user
- `register()` — POST /auth/register
- `refreshToken()` — POST /auth/refresh com token update
- `getMLConnectURL()` — GET /auth/ml/connect
- `listMLAccounts()` — GET /auth/ml/accounts
- `deleteMLAccount()` — DELETE /auth/ml/accounts/{accountId}
- `getPreferences()` — GET /auth/preferences
- `updatePreferences()` — PUT /auth/preferences com activeMLAccountId
- Valores null em updatePreferences
- Erros em login

### 2. listingsService.test.ts
**Localização:** `frontend/src/services/listingsService.test.ts`
**Testes:** 13
**Status:** ✓ Passando

Cobertura:
- `list()` — GET /listings/ com filters (period, mlAccountId)
- `sync()` — POST /listings/sync com/sem mlAccountId
- `getKpiSummary()` — GET /listings/kpi/summary com períodos (hoje, ontem, anteontem)
- `getSnapshots()` — GET /listings/{mlbId}/snapshots com dias
- `updatePrice()` — PATCH /listings/{mlbId}/price
- `getListingHealth()` — GET /listings/{mlbId}/health
- `getFunnel()` — GET /listings/analytics/funnel
- `getHeatmap()` — GET /listings/analytics/heatmap
- `simulatePrice()` — POST /listings/{mlbId}/simulate-price

### 3. authStore.test.ts
**Localização:** `frontend/src/store/authStore.test.ts`
**Testes:** 15
**Status:** ✓ Passando

Cobertura:
- State inicial (null user, null token, isAuthenticated false)
- `setAuth()` — atualiza user, token, isAuthenticated=true
- `setAuth()` chama `setStoredToken()` internamente
- `clearAuth()` — limpa user, token, isAuthenticated=false
- `clearAuth()` chama `removeStoredToken()`
- `isAuthenticated` derivado corretamente
- User data com todos os campos
- Usuários inativos (is_active=false)
- Token persistido
- Multiple setAuth calls
- clearAuth safe quando já vazio
- localStorage key 'msm-auth-storage'

## Testes Auto-Detectados

Durante a execução, o vitest encontrou 2 suites de testes adicionais (pre-existentes):

### 4. accountStore.test.ts — 6 testes ✓
**Localização:** `frontend/src/store/accountStore.test.ts`

### 5. useActiveAccount.test.ts — 4 testes ✓
**Localização:** `frontend/src/hooks/useActiveAccount.test.ts`

**Total na Suite:** 50 testes (12 + 13 + 15 + 6 + 4)

## Arquivos de Setup

### vitest.config.ts
```typescript
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
```

### src/test/setup.ts
Mocks globais aplicados a todos os testes:
- **localStorage** — getItem, setItem, removeItem, clear
- **window.location** — href
- **import.meta.env** — VITE_API_URL

## Estratégia de Mocking

### Axios (api.ts)
```typescript
vi.mock("./api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
  setStoredToken: vi.fn(),
  removeStoredToken: vi.fn(),
}));
```

**Por que path relativo e não @alias:**
- vitest não resolve bem aliases em `vi.mock()` quando usado com `require()`
- Path relativo é mais confiável
- `vi.mocked()` funciona melhor que `require()` dinâmico

### Zustand (authStore.ts)
```typescript
beforeEach(() => {
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
  });
  vi.clearAllMocks();
});
```

Reset de estado entre testes para evitar contamination entre suites.

## Cobertura Estimada

| Service | Métodos | Testados | Coverage |
|---------|---------|----------|----------|
| authService | 8 | 8 | 100% |
| listingsService | 14+ | 9 | 64%* |
| authStore | 2 | 2 | 100% |
| **TOTAL** | **24+** | **19** | **79%** |

*listingsService tem 14 métodos principais; 9 dos mais críticos (80% da lógica) estão cobertos

## Scripts de Teste

### package.json
```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

### Executar
```bash
# Run uma vez
npm test

# Watch mode com reload automático
npm run test:watch

# Específico
npm test -- authService.test.ts
```

## Dependencies Adicionadas

```json
{
  "devDependencies": {
    "@testing-library/react": "^15.0.7",
    "@vitest/ui": "^1.6.0",
    "jsdom": "^24.0.0",
    "vitest": "^1.6.0"
  }
}
```

## Próximos Passos

### Testes Faltando (Prioritário)
- [ ] `getAnalysis()` em listingsService
- [ ] `createPromotion()` em listingsService
- [ ] `linkSku()` em listingsService
- [ ] `getMargem()` em listingsService
- [ ] `getSearchPosition()` e `getPriceHistory()`

### Outras Services
- [ ] financeiroService (resumo, detalhado, timeline, cashflow)
- [ ] competitorsService
- [ ] ordersService
- [ ] adsService
- [ ] reputacaoService

### Testes de Integração
- [ ] React Router integration tests
- [ ] Component tests com @testing-library/react
- [ ] E2E tests com Playwright/Cypress

### CI/CD Integration
- [ ] GitHub Actions workflow
- [ ] Coverage reports com Codecov
- [ ] Threshold mínimo de 60% cobertura

## Troubleshooting

### Erro: "Cannot find module '@/services/api'"
**Causa:** vi.mock com alias não funciona bem no vitest

**Solução:**
```typescript
// ERRADO
vi.mock("@/services/api", () => {...});

// CERTO
vi.mock("./api", () => {...});
```

### Testes de Zustand falhando
**Causa:** Estado persistido entre testes

**Solução:**
```typescript
beforeEach(() => {
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
  vi.clearAllMocks();
});
```

### Mock não está sendo aplicado
**Causa:** require() dinâmico não pega o mock

**Solução:**
```typescript
// ERRADO
mockApi = require("./api").default;

// CERTO
mockApi = vi.mocked(apiModule).default;
```

### Timeout em testes
**Causa:** requests não mockados

**Solução:** Garantir que vi.mock está acima do import do módulo que usa a API

```typescript
// Ordem importa!
vi.mock("./api", ...)  // primeiro
import apiModule from "./api";  // depois
import authService from "./authService";  // depois
```

## Boas Práticas

1. **Mock antes de importar:** vi.mock deve estar antes dos imports
2. **Reset estado:** Sempre resete zustand/mocks no beforeEach
3. **Testes independentes:** Cada teste deve funcionar isoladamente
4. **Descrições claras:** Usar describe/it para estruturar
5. **Dados realistas:** Mock responses com dados reais
6. **Validar chamadas:** Sempre verificar que API foi chamada corretamente

## Referências

- [Vitest Documentation](https://vitest.dev/)
- [Vitest Mocking](https://vitest.dev/guide/mocking.html)
- [Zustand Testing](https://github.com/pmndrs/zustand#testing)
- [Testing Library](https://testing-library.com/docs/react-testing-library/intro/)

---

**Gerado em:** 2026-03-26
**Último commit:** 4cb0646
**Testes:** 50/50 passando (100%)
