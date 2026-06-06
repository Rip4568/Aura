# ADR-001: FormValidationError como AuraException, não HTTPException

**Status:** Aceito  
**Data:** 2026-05-28

## Contexto
O módulo aura/forms/ precisa sinalizar falhas de validação de forma que o
router converta automaticamente em resposta HTTP 422. A abordagem trivial seria
herdar de HTTPException(422).

## Decisão
FormValidationError herda de Exception diretamente (não de HTTPException).
O router captura FormValidationError explicitamente e converte para JSONResponse 422
usando exc.to_dict().

## Justificativa
1. Acoplamento: forms não deve conhecer a infraestrutura HTTP do framework
2. Testabilidade: FormValidationError pode ser testado sem infraestrutura HTTP
3. Reuso: forms podem ser usados fora de contexto HTTP (CLI, jobs async)
4. Consistência: erros de campo também não têm semântica HTTP

## Consequências
- router.py captura FormValidationError com import lazy (try/except ImportError)
- Código de aplicação pode fazer `except FormValidationError` separado de `except HTTPException`

## Trade-offs aceitos
Pequeno overhead de manutenção no router para o bloco adicional.
