# Painel Administrativo do Aura Framework — Aura Admin

O **Aura Admin** é um painel administrativo poderoso, async-first, gerado de forma declarativa e automática a partir dos seus modelos do banco de dados. Ele combina a robustez e simplicidade de configuração do Django Admin com a reatividade moderna de Single Page Applications (SPA) através de **HTMX**, estilizado com um tema escuro sofisticado em **Tailwind CSS** e renderizado no servidor usando **Jinja2**.

---

## 1. Princípios de Design e Arquitetura

1. **Declarativo e Simples:** Registre seus modelos de banco de dados com uma única linha de código.
2. **Reatividade Ultra Rápida com HTMX:** Paginação, buscas e filtros ocorrem sem recarregamento completo da página, utilizando troca de fragmentos HTML (Partial HTML Swapping) otimizados.
3. **Reflexão Dinâmica de Modelos:** O painel inspeciona os modelos SQLAlchemy em tempo real para inferir automaticamente os tipos de campos de formulário adequados (checkboxes para booleanos, selects para relacionamentos, inputs apropriados para inteiros/strings/datas, etc.) e aplica a coerção/validação correta no lado do servidor.
4. **Segurança e Isolamento por Contexto:** Utiliza gerenciamento seguro de sessões de banco de dados por requisição, evitando erros comuns como `DetachedInstanceError`.

---

## 2. Como Usar e Configurar

### Configurando o AdminModule no Aplicativo

O painel administrativo é empacotado como um módulo nativo do Aura (`AdminModule`). Para ativá-lo, importe-o no seu módulo principal:

```python
from aura.core.modules import Module
from aura.admin import AdminModule

@Module(
    imports=[
        AdminModule.for_root()
    ]
)
class AppModule:
    pass
```

Isso registrará automaticamente as rotas administrativas sob o prefixo `/admin` do seu aplicativo.

### Registrando Modelos

Você pode registrar seus modelos de duas maneiras: utilizando o decorator `@register` ou a função `register_model`.

#### Abordagem 1: Usando o Decorator `@register`

Crie uma subclasse de `ModelAdmin` para configurar a exibição do modelo e decore-a com `@register(SeuModelo)`:

```python
from aura.admin import ModelAdmin, register
from app.models import User

@register(User)
class UserAdmin(ModelAdmin):
    list_display = ["id", "name", "email", "is_active", "created_at"]
    search_fields = ["name", "email"]
    list_filter = ["is_active"]
```

#### Abordagem 2: Registro Manual com `register_model`

Se você preferir não utilizar decorators ou quiser registrar dinamicamente em tempo de execução:

```python
from aura.admin import ModelAdmin, register_model
from app.models import Product

class ProductAdmin(ModelAdmin):
    list_display = ["id", "title", "price", "stock_count"]
    search_fields = ["title", "description"]
    list_filter = ["in_stock"]

# Registro manual
register_model(Product, ProductAdmin)
```

---

## 3. Customização do `ModelAdmin`

A classe `ModelAdmin` oferece vários atributos de configuração:

* **`list_display` (list[str]):** Lista de campos ou colunas do modelo que serão exibidos na tabela de visualização em lista.
* **`search_fields` (list[str]):** Lista de campos do modelo nos quais a barra de busca fará consultas baseadas em texto (utilizando `LIKE`).
* **`list_filter` (list[str]):** Lista de campos para os quais filtros exatos de barra lateral/opções serão disponibilizados (ex: filtrar usuários ativos/inativos).
* **`ordering` (list[str]):** Ordenação padrão aplicada à listagem do painel (ex: `["-created_at"]`).
* **`per_page` (int):** Quantidade de registros por página na paginação do painel (padrão é `20`).

---

## 4. Reflexão e Coerção Dinâmica sob o Capô

O Aura Admin analisa a estrutura do seu modelo SQLAlchemy e realiza três etapas fundamentais:

### Geração de Formulários Dinâmicos
Ao abrir a tela de criação ou edição de um registro, o painel lê a definição de colunas do modelo SQLAlchemy e gera o HTML correspondente.
- Colunas do tipo `Boolean` geram elementos `checkbox`.
- Colunas do tipo `Integer`, `Float` geram campos numéricos correspondentes.
- Relacionamentos (como chaves estrangeiras) geram tags `select` dinâmicas preenchidas com as instâncias do modelo relacionado.
- Campos com restrição de nulidade (`nullable=False`) marcam o input do formulário como `required`.

### Validação e Coerção de Tipos
Ao submeter um formulário (requisições `POST` ou `PUT`), os dados são processados de forma assíncrona:
1. O painel coleta os dados brutos de string vindos da requisição HTTP.
2. Compara cada campo com o tipo de dado da coluna correspondente do banco.
3. Converte os valores brutos para tipos Python adequados (ex: `"true"` ou `"on"` $\rightarrow$ `True`, `"123"` $\rightarrow$ `123`, strings vazias para nulos se a coluna permitir).
4. Em caso de falha de validação ou restrição de banco (ex: campo obrigatório nulo ou e-mail já existente), a view captura o erro e renderiza novamente o formulário destacando visualmente as falhas sem recarregar toda a página.

---

## 5. Reatividade SPA com HTMX e Interações

O painel do Aura utiliza **HTMX** para fornecer uma experiência fluida de SPA diretamente gerada no servidor:

### Partial Swapping (Troca Parcial de Fragmentos HTML)
Quando você realiza uma busca ou clica para mudar de página na paginação da listagem de um modelo, o navegador envia uma requisição AJAX especial contendo o cabeçalho `HX-Request: true`.
O servidor detecta esse cabeçalho e, em vez de processar e enviar toda a estrutura da página `/admin`, renderiza apenas o fragmento HTML interno da tabela (`table_body.html`).
Isso reduz o tamanho da resposta HTTP e a latência de rendering, proporcionando atualizações de tela instantâneas.

### Feedback e Gatilhos (Headers de Resposta HTMX)
Ao salvar ou atualizar um registro com sucesso, o painel do Aura injeta cabeçalhos de resposta HTMX customizados (ex: `HX-Trigger: recordCreated`), instruindo o cliente HTMX a atualizar listas e exibir notificações de sucesso instantaneamente.

---

## 6. Telas e Visual Visualmente Rico

Estilizado com uma paleta de cores escura e design premium:
- **Tema Escuro Moderno:** Layout com tons grafite, bordas sutis e contraste otimizado.
- **Glassmorphism:** Efeitos de fundo desfocado translúcido (backdrop blur) nos cards e modais para sensação premium.
- **Micro-animações:** Transições suaves em hover nos botões de navegação, linhas da tabela e inputs de formulário.
- **Dashboard Central:** Visão geral contendo atalhos rápidos e número de registros por modelo cadastrado no sistema.
