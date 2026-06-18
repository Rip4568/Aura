# ADR-004: Admin ModelForm (Wave 6)

**Status:** Aceito  
**Data:** 2026-06-17  
**Contexto:** Wave 6 — `fix/wave6-admin-consolidation`

---

## Contexto

O módulo Admin (`aura/admin/views.py`) duplicava parsing manual de campos POST para cada modelo — lógica repetida, difícil de manter e desalinhada do sistema de formulários (`AuraForm`). A wave 6 centraliza CRUD de modelos em `ModelForm`.

---

## Decisões

### 1. Introduzir `ModelForm` em `aura/forms/modelform.py`

**Decisão:** `ModelForm` estende `AuraForm` e:

- Mapeia colunas SQLAlchemy → campos (`CharField`, `IntField`, `BoolField`, etc.) via `sqlalchemy_column_to_field()`.
- Exclui colunas de auditoria (`created_at`, `updated_at`) e chaves primárias auto-geradas.
- Implementa `save()` para criar ou atualizar instâncias com sessão ORM opcional.

**Motivo:** DRY — uma única fonte de verdade para validação e persistência no admin e em apps customizados.

**Breaking:** Não — API nova; admin migra internamente.

---

### 2. Admin views delegam a `ModelForm`

**Decisão:** `aura/admin/views.py` remove ~250 linhas de parsing duplicado e usa `ModelForm` para create/update.

**Motivo:** Menos bugs de tipo, labels e required inconsistentes entre modelos.

**Breaking:** Não para consumidores HTTP — contrato de formulário HTML permanece.

---

### 3. CSRF em templates de mutação

**Decisão:** Template `form.html` inclui token CSRF; views validam via `SessionMiddleware` (wave 2).

**Motivo:** Completar hardening do admin iniciado na wave 2.

**Breaking:** Não — já exigido desde wave 2 para mutações.

---

## Consequências

- Admin CRUD extensível: apps podem subclassar `ModelForm` para campos customizados.
- `tests/test_admin.py` cobre fluxo create/update com `ModelForm`.
- Item de roadmap “Admin: reutilizar AuraForm/ModelForm” fechado.

## Referências

- Commit: `ac6791a` — `fix(wave6): admin CSRF, ModelForm, remove duplicate parsing`
- `CHANGELOG.md` — seção Wave 6 em `[1.4.0]`
