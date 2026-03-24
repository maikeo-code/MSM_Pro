# Fix: Race Conditions no Auto-Refresh de JWT

## Commit
`3ca839f` — fix: corrigir race conditions no auto-refresh de JWT no frontend

## Problemas Corrigidos

### 1. Race Condition: `isRefreshing` boolean → `refreshPromise` Promise-based queue
**Antes:**
```typescript
let isRefreshing = false;

async function tryRefreshJwt(): Promise<boolean> {
  if (isRefreshing) return false; // ← Bug: não aguarda, retorna false
  isRefreshing = true;
  // ... fazer refresh ...
  isRefreshing = false;
}
```

**Cenário do bug:**
- Request 1 com 401 chama `tryRefreshJwt()`
- Request 2 com 401 chama `tryRefreshJwt()` simultâneamente
- Request 2 vê `isRefreshing = true`, retorna `false` sem aguardar
- 2 refreshes são feitos em paralelo (ineficiente e perigoso)

**Solução:**
```typescript
let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshJwt(): Promise<boolean> {
  if (refreshPromise) return refreshPromise; // ← Aguarda a promise anterior

  refreshPromise = (async () => {
    // ... fazer refresh ...
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null; // Limpar para próximas tentativas
  }
}
```

**Resultado:**
- Request 1 inicia refresh, armazena promise em `refreshPromise`
- Request 2 vê `refreshPromise !== null`, retorna a mesma promise
- Ambas aguardam o MESMO refresh (eficiente)

---

### 2. Fire-and-Forget no Request Interceptor
**Antes:**
```typescript
api.interceptors.request.use(async (config) => {
  if (shouldRefreshJwt()) {
    tryRefreshJwt(); // ← Fire-and-forget: não awaita
  }
  config.headers.Authorization = `Bearer ${token}`; // ← token ainda é velho!
  return config;
});
```

**Bug:** A request é enviada com token antigo enquanto refresh está em andamento.

**Solução:**
```typescript
api.interceptors.request.use(async (config) => {
  if (shouldRefreshJwt()) {
    await tryRefreshJwt(); // ← Aguardar antes de continuar
    token = getStoredToken(); // ← Pegar token atualizado
  }
  config.headers.Authorization = `Bearer ${token}`; // ← token fresco!
  return config;
});
```

---

### 3. Retry do 401 Usando `axios()` em Vez de `api.request()`
**Antes:**
```typescript
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      const refreshed = await tryRefreshJwt();
      if (refreshed) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return axios(originalRequest); // ← Pula interceptors!
      }
    }
  }
);
```

**Bug:** Retry usa `axios` (sem interceptors) em vez de `api` (com interceptors). Se refresh expirar novamente, não entra no loop de retry.

**Solução:**
```typescript
return api.request(originalRequest); // ← Usa interceptors
```

---

### 4. Dupla Chamada de `setStoredToken()`
**Antes:**
```typescript
const newToken = response.data.access_token;
if (newToken) {
  setStoredToken(newToken); // ← 1ª chamada
  const store = useAuthStore.getState();
  if (store.user) {
    store.setAuth(store.user, newToken); // ← setAuth chama setStoredToken novamente!
  }
}
```

**Bug:** localStorage é escrito 2x, e timestamps se desincronizam.

**Solução:**
```typescript
const newToken = response.data.access_token;
if (newToken) {
  const store = useAuthStore.getState();
  if (store.user) {
    store.setAuth(store.user, newToken); // ← Uma única chamada
  } else {
    setStoredToken(newToken); // ← Fallback apenas se user não existe
  }
}
```

---

## Verificação no Navegador (DevTools)

### Teste 1: Verificar que Promise é reutilizada

**Chrome DevTools Console:**
```javascript
// Abrir 2 abas do dashboard simultâneamente
// Observar na aba "Network":
// - Esperado: 1 chamada POST /auth/refresh
// - Antes: 2 chamadas POST /auth/refresh
```

### Teste 2: Verificar que token é enviado fresco

**Chrome DevTools > Application > Storage > Local Storage:**
```
msm_access_token: "eyJ..."
msm_token_refreshed_at: "1679....."
```

Fazer login, aguardar 5s, fazer uma request ao dashboard:
- Esperado: `Authorization: Bearer eyJ...` (novo token na request)
- Antes: `Authorization: Bearer old_token` (token antigo, depois 401 + retry)

### Teste 3: Verificar que setStoredToken é chamado 1x

**Chrome DevTools > Aplicação > Storage > Local Storage, monitore mudanças:**
```
setInterval(() => {
  console.log("Timestamp:", localStorage.getItem("msm_token_refreshed_at"));
}, 1000);

// Chamar /auth/refresh manualmente
// Esperado: timestamp atualiza 1x
// Antes: timestamp atualiza 2x (setStoredToken chamado 2x)
```

---

## Cenários de Teste

### Cenário 1: Token expirado durante navegação
1. Fazer login
2. Deixar 6+ horas (ou simular com DevTools)
3. Navegar para nova página
4. Esperado: refresh automático sem o usuário notar
5. Validar: console não mostra errors, página carrega normal

### Cenário 2: Múltiplos 401 simultâneos
1. Fazer login e pegar token válido
2. Abrir DevTools > Network
3. Chamar 5 endpoints rapidamente (cliques em abas diferentes)
4. Forçar 401 alterando token no localStorage para "invalid"
5. Clicar "refresh manualmente" 5x rapidamente
6. Esperado: apenas 1 POST /auth/refresh
7. Antes: 5 POST /auth/refresh

### Cenário 3: Logout durante refresh
1. Fazer login
2. Abrir DevTools > Network
3. Forçar token inválido no localStorage
4. Chamar um endpoint
5. Durante o 401 + refresh, clicar "Logout" manualmente
6. Esperado: redireciona para /login sem errors
7. localStorage limpo (msm_access_token removido)

### Cenário 4: Retry com novo token funciona
1. Fazer login
2. Usar rede lenta (DevTools > Network > throttle)
3. Fazer uma request normal
4. Durante a request, abrir console e alterar token para "invalid"
5. Quando 401 chegar, token será refrescado automaticamente
6. Esperado: request é retentada com novo token e sucede
7. Response retorna status 200 (não 401)

---

## Arquivo Modificado
- `frontend/src/services/api.ts` (44 linhas adicionadas, 29 removidas)

## Deploy
Railway deploy automático acionado via `git push origin main`
- URL: https://msmprofrontend-production.up.railway.app
- Aguardar 2-3 minutos para build completar

---

## Referências
- `frontend/src/store/authStore.ts` — setAuth() deve chamar setStoredToken()
- `frontend/src/services/api.ts` — arquivo corrigido
- CLAUDE.md — Regra #4: Tokens sincronizados

