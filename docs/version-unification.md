# Unificação de Versão — Aura Framework

> **Data:** Jun 2026 · **Status:** Caótico · **Ação:** Imediata

---

## O Problema

O Aura Framework reporta **4 versões diferentes** em 4 fontes distintas:

| Fonte | Arquivo:Linha | Valor | Propósito |
|-------|--------------|-------|-----------|
| PyPI | `pyproject.toml:7` | `1.2.0` | O que `pip install aura-web` instala |
| Python | `aura/__init__.py:152` | `0.3.1` | `aura.__version__` em runtime |
| Docs | `CLAUDE.md` + README badge | `0.4.9` | Documentação e CI |
| Roadmap | `docs/roadmap.md` | `v0.2.0` | Planejamento |

Nenhuma combinação faz sentido:
- PyPI diz `1.2.0` → sugere projeto maduro, pós-1.0
- `__init__.py` diz `0.3.1` → sugere alpha inicial, 8 versões atrás do PyPI
- README mostra `0.4.9` → não corresponde a nenhuma das outras
- Roadmap fala em `v0.2.0` → completamente desatualizado

---

## Impacto

1. **Credibilidade:** Desenvolvedor vê `1.2.0` no PyPI, instala, lê README que diz "Alpha v0.4.9" — confusão total
2. **Debug:** `aura.__version__` retorna `0.3.1`, mas o código pode ter features de `1.2.0`. Impossível saber o que esperar
3. **CI/CD:** Badge mostra `0.4.9`, mas `pyproject.toml` builda como `1.2.0`
4. **Changelog:** Impossível manter sem versão canônica

---

## Versão Única (Single Source of Truth)

### Abordagem: `pyproject.toml` como fonte canônica

O `pyproject.toml` já é o que o PyPI usa. Todas as outras fontes devem derivar dele.

### Implementação

#### 1. `aura/__init__.py` — ler de `importlib.metadata`

```python
# Opção A: importlib.metadata (padrão Python 3.8+)
from importlib.metadata import version as _get_version

try:
    __version__ = _get_version("aura-web")
except Exception:
    __version__ = "0.0.0-dev"  # Fallback seguro para dev
```

#### 2. `CLAUDE.md` e `README.md` — usar badge dinâmico do PyPI

```markdown
<img src="https://img.shields.io/pypi/v/aura-web?style=flat-square" />
```

Isso puxa automaticamente do PyPI. Sempre correto.

#### 3. `docs/roadmap.md` — remover versão do título

Substituir "v0.2.0" por uma referência ao `pyproject.toml`.

#### 4. Template de layout admin — injetar versão em runtime

```python
# aura/admin/views.py
from aura import __version__

def render_admin(template, context=None):
    context = context or {}
    context.setdefault("aura_version", __version__)
    ...
```

```html
<!-- layout.html -->
<span>Aura Framework v{{ aura_version }}</span>
```

---

## Qual Versão Usar?

### Recomendação: `0.5.0`

Justificativa:
- O projeto está funcional e rico em features (589 testes, ORM, Admin, Jobs, Logging)
- Mas ainda é Alpha: sem docs website, sem exemplos, sem benchmarks, sem plugin system
- `0.5.0` marca o meio do caminho para `1.0.0`
- É maior que todas as versões atuais (evita confusão de "downgrade")
- É consistente com SemVer: `MAJOR.MINOR.PATCH` onde MAJOR=0 indica pré-1.0

### Cronograma de Versões

| Versão | Marco |
|--------|-------|
| `0.5.0` | Unificação + correções de segurança |
| `0.6.0` | Docs website + exemplos + benchmarks |
| `0.7.0` | WebSocket Gateway + OpenTelemetry |
| `0.8.0` | Plugin system + AuraTestCase |
| `1.0.0` | Production Ready |

---

## Script de Automação

Criar `scripts/bump_version.py`:

```python
"""Bump version in all files consistently."""
import sys
from pathlib import Path

def bump(new_version: str):
    root = Path(__file__).parent.parent

    # 1. pyproject.toml
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text()
    # Encontra e substitui a versão
    for line in content.split("\n"):
        if line.startswith("version ="):
            old = line.split('"')[1]
            break
    content = content.replace(f'version = "{old}"', f'version = "{new_version}"')
    pyproject.write_text(content)

    print(f"✅ Version bumped to {new_version}")

if __name__ == "__main__":
    bump(sys.argv[1])
```

---

## Checklist de Unificação

- [ ] Escolher versão alvo (`0.5.0` recomendado)
- [ ] Atualizar `pyproject.toml:7` para `0.5.0`
- [ ] Atualizar `aura/__init__.py:152` para usar `importlib.metadata.version("aura-web")`
- [ ] Atualizar `README.md` badge para badge dinâmico do PyPI
- [ ] Atualizar `CLAUDE.md` contagem de versão
- [ ] Atualizar `docs/roadmap.md` referência de versão
- [ ] Atualizar `aura/admin/templates/layout.html:70` para usar variável injetada
- [ ] Criar `scripts/bump_version.py`
- [ ] Publicar `0.5.0` no PyPI
- [ ] Verificar: `pip install aura-web==0.5.0` → `aura version` → `0.5.0`
