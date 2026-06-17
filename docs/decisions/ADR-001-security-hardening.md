# ADR-001: Hardening de segurança e contratos (Waves 1–2)

**Status:** Aceito (Wave 1 mergeada; Wave 2 em progresso)  
**Data:** 2026-06-17  
**Contexto:** Análise consolidada em `.omo/aura_analysis_final.md` e `analysis_2026-06-16.md`

---

## Contexto

Auditoria de segurança identificou falhas de contrato e superfícies de ataque em routing, ORM, JWT, redirects, logs de startup, SAQ, migrations e admin. As waves 1–2 endereçam os itens de maior impacto sem redesenhar a arquitetura.

---

## Decisões

### 1. `QuerySet.delete()` exige opt-in para delete sem filtro

**Decisão:** `delete(*, allow_unfiltered: bool = False)` — sem filtros, levanta `ValueError` a menos que `allow_unfiltered=True`.

**Motivo:** `DELETE FROM tabela` acidental é risco alto em frameworks com API fluente.

**Breaking:** Sim. Código que chamava `.delete()` em queryset vazio deve passar `allow_unfiltered=True` ou adicionar `.filter()`.

```python
# Antes (apagava tudo)
await Model.objects.delete()

# Depois
await Model.objects.filter(active=False).delete()
# ou, com intenção explícita:
await Model.objects.delete(allow_unfiltered=True)
```

---

### 2. Extra `[jwt]` migra de `python-jose` para PyJWT

**Decisão:** `pyproject.toml` define `jwt = ["PyJWT[crypto]>=2.13.0"]`. `JWTGuard` usa `jwt.decode` do PyJWT com opções de segurança (`verify_exp`, algoritmos permitidos, etc.).

**Motivo:** `python-jose` está depreciada, com CVEs conhecidas (confusão de algoritmo RSA, parsing inseguro).

**Breaking:** Sim para quem instalava `[jwt]` esperando `python-jose` como dependência transitiva. API pública do `JWTGuard` permanece estável; apenas a lib subjacente mudou.

```bash
pip install "aura-web[jwt]"   # instala PyJWT[crypto]
```

---

### 3. `redirect()` aceita apenas paths relativos

**Decisão:** `_is_safe_redirect_url` exige prefixo `/`, rejeita `//` e `\`. URLs absolutas ou esquemas externos lançam `BadRequestException`.

**Motivo:** Open redirect em `Location` habilita phishing.

**Breaking:** Parcial. Handlers que redirecionavam para URLs externas devem usar `starlette.responses.RedirectResponse` diretamente ou outro mecanismo explícito.

---

### 4. Logs de startup redactam valores sensíveis

**Decisão:** `_redact_sensitive_values` em `aura/core/app.py` substitui chaves como `secret`, `password`, `token`, `url` (database) por `***` antes de logar `AuraConfig`.

**Breaking:** Não.

---

### 5. Coerção inválida de parâmetros HTTP → 422

**Decisão:** Falhas de binding/coerção e bodies inválidos retornam `422 Unprocessable Entity` com detalhes estruturados, não `500`.

**Breaking:** Não (correção de contrato HTTP).

---

### 6. Migrations: sem auto-discovery de models

**Decisão:** `generate_env_py` não faz mais `os.walk` + `importlib.import_module`. Exige `model_import` explícito (`app.models:Base`) ou placeholder comentado.

**Motivo:** Import arbitrário durante `alembic upgrade` é vetor de execução de código não confiável.

**Breaking:** Projetos que dependiam do walk automático devem passar `--model-import` no `aura migrate init` ou editar `env.py` manualmente.

---

### 7. Admin: PBKDF2, CSRF e logout POST

**Decisão (Wave 2):**

- Senhas de admin armazenadas com PBKDF2-HMAC-SHA256 (`aura/admin/security.py`)
- Mutações validam token CSRF da sessão
- Logout via `POST /admin/logout` (form em `layout.html`)

**Breaking:** Admin com senha plaintext em env continua funcionando via `verify_password` legacy; novos hashes usam PBKDF2.

---

## Consequências

- Documentar breaking changes no README e `docs/pending.md`
- Testes: `tests/test_querybuilder.py` (`allow_unfiltered`), `tests/test_guards_auth.py` (PyJWT), `tests/test_migrate.py` (`generate_env_py`), `tests/test_admin.py` (PBKDF2/CSRF)
- Changelog/release notes devem destacar `delete()` e `[jwt]` na próxima publicação PyPI

## Alternativas rejeitadas

- **Manter `python-jose`:** risco de segurança inaceitável
- **Confirmar delete sem filtro com prompt CLI:** não aplicável a runtime HTTP/ORM
- **Auto-discovery de models com whitelist:** complexidade maior que import explícito no `env.py`
