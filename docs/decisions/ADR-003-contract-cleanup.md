# ADR-003: Contract cleanup (Wave 5)

**Status:** Aceito  
**Data:** 2026-06-17  
**Contexto:** Wave 5 — `fix/wave5-contract-cleanup`

---

## Contexto

Auditoria pós-wave 4 identificou código morto (`RequestPipeline`), binding incompleto de `FormData`, interceptors não aplicados uniformemente no roteamento, e inconsistências na API pública de middleware/interceptors. A wave 5 alinha contratos sem redesenhar a arquitetura ASGI.

---

## Decisões

### 1. Remover `RequestPipeline` (`aura/core/pipeline.py`)

**Decisão:** O módulo foi removido. O `Router` já envolve handlers com guards, interceptors e middleware por rota.

**Motivo:** `RequestPipeline` nunca era instanciado pela aplicação — duplicava lógica e confundia a documentação.

**Breaking:** Não para usuários finais (não estava em `__all__`). Código interno que importava `aura.core.pipeline` deve migrar para os wrappers do `Router`.

---

### 2. `FormDataMarker` no plano de binding

**Decisão:** `FormDataMarker` é tratado explicitamente em `_compute_binding_plan`, no mesmo nível que `BodyMarker`, `QueryMarker`, etc.

**Motivo:** Uploads multipart e campos de formulário falhavam silenciosamente ou geravam 500 em vez de 422.

**Breaking:** Não.

---

### 3. Interceptors e middleware por rota no `Router`

**Decisão:** `Router.as_routes()` aceita `global_interceptors` e aplica `route_middleware` de cada handler em JSON, HTML, SSE e WebSocket.

**Motivo:** Interceptors documentados (logging, timing) não eram executados em todos os tipos de resposta.

**Breaking:** Não — comportamento novo, opt-in via registro de interceptors.

---

### 4. `UnprocessableEntityException` (422) estruturada

**Decisão:** Erros de validação de parâmetros/body retornam corpo JSON com `detail` tipado, via `UnprocessableEntityException`.

**Motivo:** Alinhar com wave 1 (422 em vez de 500) e dar payload previsível para clientes.

**Breaking:** Não — apenas melhora o formato de respostas já em 422.

---

## Consequências

- Menos superfície morta no core.
- Interceptors e middleware seguem o mesmo caminho de execução para todos os `response_type`.
- Testes em `tests/test_routing.py`, `tests/test_middleware.py` e `tests/test_modules.py` cobrem os novos contratos.

## Referências

- Commit: `d996f34` — `fix(wave5): contract cleanup`
- `CHANGELOG.md` — seção Wave 5 em `[1.4.0]`
