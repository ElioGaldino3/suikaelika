# Validação funcional local

**Data:** 20/10/2026
**Estado:** verificações locais passaram nos cenários descritos; não é homologação Batocera.

## Ambiente

Relatório obtido em host Windows 11 (`win32`), AMD64 com processo de 64 bits,
CPython 3.13.16. O diagnóstico `tools/diagnostics.py` identificou Pygame
2.6.1, SDL 2.28.4 (mostrado no smoke de inicialização), Pymunk 7.3.1, pytest
9.1.1, Ruff 0.17.1 e mypy 1.20.2. O diagnóstico não sondou display, SDL, áudio
ou controle; o smoke usou SDL dummy e somente abriu a aplicação por um quadro.

O caminho do interpretador usado nesta execução foi
`C:\Users\elio\AppData\Local\Temp\suika-elika-py313\Scripts\python.exe`.
Ele é temporário desta estação e não deve ser tratado como requisito de
instalação.

## Verificações executadas

| Comando | Resultado |
|---|---|
| `python -m pytest tests/integration/test_classic_rules.py tests/integration/test_failure_recovery.py -q` | 6 passaram |
| `python -m pytest -q` | 189 passaram |
| `ruff check tests/integration/test_classic_rules.py tests/integration/test_failure_recovery.py` | passou |
| `mypy` (configuração do projeto) | passou, 40 arquivos fonte |
| `python skills/todo-orchestrator/scripts/todo_graph.py validate` | válido, 34 tarefas |
| `git diff --check` | passou |
| `python tools/diagnostics.py` | Windows 11/AMD64 e versões acima; probes de dispositivo não executados |

Durante a verificação conjunta, `ruff check .` encontrou `I001` em
`tests/packaging/test_layout.py`, arquivo da SE-023 sendo editado em paralelo.
Esse caminho não pertence a esta validação; Ruff passou nos dois arquivos
novos da SE-022. O orquestrador repetirá o lint global após integrar ambos os
lotes.

## Cenários cobertos

- Duas fusões de pares diferentes são resolvidas no mesmo passo, sua pontuação
  é agregada e a decisão de transbordamento considera a pilha já atualizada.
- Uma área de nascimento bloqueada rejeita a soltura sem consumir a fruta ou a
  sequência; após liberar a área, uma nova soltura funciona.
- A pausa não avança a física nem retém uma borda de soltura. Reinícios
  repetidos mantêm a prévia inicial para a mesma seed e limpam a rodada.
- JSON inválido é isolado pelo serviço de persistência; diretórios sem gravação
  não impedem iniciar uma partida e soltar uma fruta.
- O fluxo de partida continua quando `NullAudioManager` representa áudio
  indisponível.

Contatos concorrentes e a posição de perigo são controlados por um `PhysicsPort`
determinístico para testar a ordem das regras. O fluxo com armazenamento
corrompido/indisponível usa `JsonPersistence` e a simulação física do Pymunk.

## Não executado

- Inicialização pelo EmulationStation no Batocera 43 ou prova no notebook x86 do
  usuário. Batocera 43 e notebook x86 são informações relatadas, não medidas
  por este ambiente.
- Teste de controle físico, remoção/reconexão real ou seleção do controle no
  Batocera.
- Inicialização de display ou áudio real, incluindo HDMI, ou avaliação visual
  interativa prolongada.
- Teste prolongado de memória/desempenho ou validação de balanceamento.

Para coletar o runtime no destino, executar no Batocera, a partir da pasta do
projeto, `python3 tools/diagnostics.py --format json` e registrar a saída. Essa
coleta não substitui as provas de SDL, joystick, áudio e física no equipamento.
