# Security Advisory — Aura Framework Admin Panel

> **Data:** Jun 2026 · **Severidade:** Alta · **Status:** Não corrigido

---

## Resumo

O Admin Panel do Aura (`AdminModule`) possui 4 vulnerabilidades de segurança que permitem acesso não autorizado em ambientes de desenvolvimento e potencialmente em produção. Os achados são:

1. **Ausência de proteção CSRF** em todos os formulários do admin
2. **Senha comparada em plaintext** (sem hashing)
3. **Admin exposto por padrão** quando `AURA__DEBUG` não é explicitamente `false`
4. **Segredo de sessão hardcoded** no scaffold gerado pelo `aura new`

---

## 1. CSRF Ausente nos Formulários Admin

### Severidade: 🔴 Alta

### Descrição

Nenhum formulário HTML do admin panel inclui token CSRF. Como a autenticação usa cookies de sessão (`SessionMiddleware`), um atacante pode hospedar um formulário malicioso em outro domínio que faz POST para o admin da vítima, executando ações autenticadas sem consentimento.

### Localização

- `aura/admin/templates/login.html:61` — formulário de login
- `aura/admin/templates/form.html:28` — formulários de create/edit

### Prova de Conceito

```html
<!-- Hospedado em attacker.com -->
<form action="https://vitima.com/admin/login" method="POST">
    <input type="hidden" name="password" value="senha_roubada">
</form>
<script>document.forms[0].submit();</script>
```

O navegador da vítima enviará o cookie de sessão automaticamente (same-site lax default), e o atacante pode tentar brute-force ou simplesmente causar logout/login indesejado.

### Risco em Produção

Se `SessionMiddleware` usa `samesite="lax"` (padrão do itsdangerous/Starlette), POST de formulários cross-site são bloqueados em navegadores modernos. Porém:
- Navegadores antigos não suportam SameSite
- `samesite="none"` (necessário para alguns cenários cross-origin) remove essa proteção
- O admin não deve depender exclusivamente de SameSite cookies

### Solução Recomendada

1. Adicionar `csrf_token` ao contexto de renderização do admin
2. Incluir `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">` em todos os forms
3. Validar o token no handler POST antes de processar

```python
import secrets

def generate_csrf_token(session):
    token = secrets.token_hex(32)
    session["_csrf_token"] = token
    return token

def validate_csrf_token(session, submitted):
    expected = session.pop("_csrf_token", None)
    if not expected or not secrets.compare_digest(expected, submitted):
        raise ForbiddenException("CSRF token inválido")
```

---

## 2. Senha Admin em Plaintext

### Severidade: 🔴 Alta

### Descrição

A senha do admin (`AURA_ADMIN_PASSWORD`) é comparada diretamente, sem hashing:

```python
# aura/admin/views.py:142
if submitted == password:
    sess["admin_authenticated"] = True
```

Se a variável de ambiente vazar (log, crash report, `env` em processo filho), o atacante tem a senha em plaintext. Com hashing, mesmo com acesso à env var, seria necessário quebrar o hash.

### Localização

`aura/admin/views.py:142`

### Risco

- `.env` pode ser exposto em backups, logs de deploy, ou CI/CD
- Variáveis de ambiente são herdadas por processos filhos
- `os.environ` é acessível por qualquer biblioteca Python no processo

### Solução Recomendada

```python
import hashlib
import secrets

# Na configuração: armazenar hash, não senha
# export AURA_ADMIN_PASSWORD_HASH=sha256:abc123...

# Na verificação:
def verify_password(submitted: str, stored_hash: str) -> bool:
    algo, _, hash_value = stored_hash.partition(":")
    if algo == "sha256":
        return secrets.compare_digest(
            hashlib.sha256(submitted.encode()).hexdigest(),
            hash_value
        )
    return False
```

**Alternativa mais simples (curto prazo):** Adicionar rate-limit no endpoint de login para mitigar brute-force, mantendo a senha em env var como primeiro passo. Migrar para hash no médio prazo.

---

## 3. Admin Aberto por Padrão (Debug Default Inseguro)

### Severidade: 🟠 Média-Alta

### Descrição

```python
# aura/admin/views.py:87
is_debug = os.getenv("AURA__DEBUG", "true").lower() in ("true", "1")
if not is_debug:
    raise RuntimeError(...)
return None  # Sem senha = admin aberto!
```

O valor padrão de `AURA__DEBUG` é `"true"`. Se o usuário não define `AURA__DEBUG=false` explicitamente, o admin fica completamente aberto — qualquer pessoa acessa `/admin` sem autenticação.

Combinado com a falta de `AURA_ADMIN_PASSWORD`, não há absolutamente nenhuma barreira de acesso.

### Localização

`aura/admin/views.py:87`

### Cenário de Risco

1. Desenvolvedor faz deploy em um VPS
2. Não configura `AURA__DEBUG` (assume que o padrão é produção-safe)
3. Admin fica acessível publicamente em `/admin`
4. Atacante descobre via scan de paths comuns

### Solução Recomendada

**Opção 1 (Preferida):** Inverter o default
```python
is_debug = os.getenv("AURA__DEBUG", "false").lower() in ("true", "1")
```

**Opção 2 (Defensiva):** Exigir senha mesmo em debug se `AURA_ADMIN_PASSWORD` estiver definido
```python
if password:
    # Sempre requer autenticação se senha foi configurada
    ...
elif not is_debug:
    raise RuntimeError("AURA_ADMIN_PASSWORD required in production")
```

---

## 4. Segredo de Sessão Hardcoded no Scaffold

### Severidade: 🟡 Média

### Descrição

O comando `aura new` gera `main.py` com:

```python
# aura/cli/commands/new.py:53
SessionMiddleware(secret_key="change-me-in-production-32chars!!")
```

Este segredo é commitado no repositório git do projeto gerado. Se o projeto for open-source ou o repositório vazar, atacantes podem forjar cookies de sessão (inclusive a sessão admin).

### Localização

`aura/cli/commands/new.py:53` (template de scaffold)

### Solução

```python
# Usar secrets.token_urlsafe() como já é feito para .env
secret_key = secrets.token_urlsafe(32)
# Gerar: SessionMiddleware(secret_key="a3f8b2c1...")
```

---

## Plano de Remediação

| # | Ação | Prioridade | Esforço |
|---|------|-----------|---------|
| 1 | Adicionar CSRF tokens nos forms admin | 🔴 Imediata | 2-3h |
| 2 | Implementar hash de senha admin | 🔴 Imediata | 2-3h |
| 3 | Inverter default de `AURA__DEBUG` para `"false"` | 🟠 Esta semana | 15 min |
| 4 | Rate-limit no endpoint `/admin/login` | 🟠 Esta semana | 1h |
| 5 | `secrets.token_urlsafe()` no scaffold | 🟡 Próximo release | 30 min |

---

## Verificação Pós-Correção

```bash
# 1. Admin não deve ser acessível sem senha com debug=false
AURA__DEBUG=false aura run &
curl -s http://localhost:8000/admin | grep -c "login"  # Deve redirecionar para login

# 2. CSRF token deve estar presente nos forms
curl -s http://localhost:8000/admin/login | grep -c "csrf_token"

# 3. Senha não deve estar em plaintext no código
grep -r "== password" aura/admin/  # Não deve encontrar

# 4. Scaffold não deve ter segredo fixo
aura new test-proj && grep -c "change-me" test_proj/main.py  # Deve ser 0
```
