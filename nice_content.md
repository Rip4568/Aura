 📊 Radiografia Completa — O que a Pesquisa Revelou
  
  🔥 Os 10 Maiores Pain Points (com evidências reais)

  ┌─────┬─────────────────────────────────────┬───────────────┬────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  #  │              Problema               │   Framework   │                                          Impacto Real                                          │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 1   │ ORM Síncrono                        │ Django        │ Async views com sync_to_async() em todo lugar — falso async                                    │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 2   │ DRF Serializers                     │ Django        │ ModelSerializer 377x mais lento que Python puro em benchmark com 5.000 itens                   │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 3   │ N+1 Queries invisíveis              │ Django/DRF    │ 950 queries numa única página descoberto em produção (91% de load reduction ao corrigir)       │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 4   │ Type safety ilusória                │ Django        │ Metaclass magic quebra mypy — projeto de migração tipagem descrita como "unsuccessful journey" │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 5   │ Celery sem async                    │ Todos         │ Não suporta async def nativamente — workarounds em todo lugar                                  │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 6   │ DI amarrado ao HTTP                 │ FastAPI       │ Depends() não funciona em jobs, CLI ou workers                                                 │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 7   │ settings.py monolítico              │ Django        │ Conflitos de merge, if DEV espalhados, sem validação de startup                                │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 8   │ Sem estrutura de projeto            │ FastAPI/Flask │ 82+ boilerplates no StarterIndex = problema reconhecido                                        │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 9   │ Migrations e branch switching       │ Django        │ Precisa de 5 passos manuais para trocar de branch com migrations diferentes                    │
  ├─────┼─────────────────────────────────────┼───────────────┼────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 10  │ Celery prefetch + acknowledge early │ Todos         │ Tasks perdidas se worker crasha; usuários monopolizam workers                                  │
  └─────┴─────────────────────────────────────┴───────────────┴────────────────────────────────────────────────────────────────────────────────────────────────┘

  💡 O que o Aura vai entregar (baseado na pesquisa):
  
  Django problems:           FastAPI problems:        Celery problems:
  ✅ settings.py → aura.toml  ✅ Sem ORM → integrado  ✅ Sem async → async-native
  ✅ DRF hell → Pydantic v2   ✅ DI fraco → container  ✅ Acknowledge → pessimistic
  ✅ ORM sync → SA2 async     ✅ Sem CLI → aura gen    ✅ Monitoring → built-in
  ✅ Typing ruim → strict     ✅ Sem jobs → SAQ/Taskiq ✅ Setup complexo → @task()
  ✅ N+1 → Repository pattern ✅ Sem estrutura → módulos ✅ DLQ manual → nativo

  ---
  🔄 Status Atual dos Agentes

  ┌────────────────────────────────────────────┬─────────────────────────────────┐
  │                   Agente                   │             Status              │
  ├────────────────────────────────────────────┼─────────────────────────────────┤
  │ 🔍 Research-Django (pain points)           │ ✅ Concluído                    │
  ├────────────────────────────────────────────┼─────────────────────────────────┤
  │ 🔬 Research-Patterns (SDD + modern)        │ ✅ Concluído                    │
  ├────────────────────────────────────────────┼─────────────────────────────────┤
  │ 🏛️  Architect (design completo)             │ 🔄 Rodando                      │
  ├────────────────────────────────────────────┼─────────────────────────────────┤
  │ ⚙️  Core-Impl (app, di, routing, schema...) │ 🔄 Rodando — 9 arquivos criados │
  ├────────────────────────────────────────────┼─────────────────────────────────┤
  │ 🔧 Infra-Impl (jobs, orm, cli, testing)    │ 🔄 Rodando                      │
  └────────────────────────────────────────────┴─────────────────────────────────┘
