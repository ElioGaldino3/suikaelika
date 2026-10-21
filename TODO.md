# TODO — Suika Elika

Atualizado em 20/10/2026. O jogo clássico está funcional e jogável localmente.
O histórico detalhado do MVP foi arquivado em [docs/archive/TODO-classic.md](docs/archive/TODO-classic.md).
Este arquivo concentra o novo modo BATALHA e os bloqueios reais de homologação.
A validação com drivers simulados não homologa controles físicos nem Batocera.

## Modo BATALHA 1x1

### SE-035 — Entrada simultânea por dois controles

- Status: `done`
- Scope: `battle`
- Priority: `P1`
- Depends: `none`
- Writes: `suika_elika/input/battle.py; suika_elika/app.py; tests/integration/test_battle_flow.py; tests/input/test_devices.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Implementado e revisado. 232 testes passaram; Ruff e mypy (46 fontes) aprovados; build Batocera gerado e cenário incluído. Critérios, pesquisa Context7, revisão visual e limitações em docs/validation/battle.md. Homologação física permanece em SE-038.
- Blocker: `none`

**Aceitação:**

- Dois instance IDs distintos, sem duplicar Controller/Joystick. Manter os lugares após remoção e reconexão; pausar ambos e consumir confirmação sem lançar.

### SE-036 — Corrida a 500 pontos em duas cestas

- Status: `done`
- Scope: `battle`
- Priority: `P1`
- Depends: `none`
- Writes: `suika_elika/game/battle.py; suika_elika/scenes/battle.py; suika_elika/scene_manager.py; tests/game/test_battle.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Implementado e revisado. 232 testes passaram; Ruff e mypy (46 fontes) aprovados; build Batocera gerado e cenário incluído. Critérios, pesquisa Context7, revisão visual e limitações em docs/validation/battle.md. Homologação física permanece em SE-038.
- Blocker: `none`

**Aceitação:**

- Duas sessões independentes, cestas físicas de 480×460, sequência igual. Vitória por >=500 ou transbordamento adversário; empate no mesmo passo. Pausa, resultado e revanche.

### SE-037 — Menu, tela dividida e cenário da batalha

- Status: `done`
- Scope: `battle`
- Priority: `P1`
- Depends: `none`
- Writes: `suika_elika/rendering/battle.py; suika_elika/rendering/assets.py; suika_elika/scenes/title.py; suika_elika/scenes/pause.py; tools/process_art_assets.py; assets/backgrounds/battle.png; tests/rendering/test_battle_rendering.py; tests/rendering/test_assets.py; tests/scenes/test_navigation.py; README.md; docs/PROJECT.md; docs/ARCHITECTURE.md; docs/validation/battle.md; TODO.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Implementado e revisado. 232 testes passaram; Ruff e mypy (46 fontes) aprovados; build Batocera gerado e cenário incluído. Critérios, pesquisa Context7, revisão visual e limitações em docs/validation/battle.md. Homologação física permanece em SE-038.
- Blocker: `none`

**Aceitação:**

- BATALHA visível e desabilitado com menos de dois controles, atualizado por hotplug. Cestas por jogador, placar/meta/próxima fruta e raw_assets/battle_background.png como fundo; incluir no pacote.

### SE-038 — Homologar batalha com dois controles no Batocera

- Status: `blocked`
- Scope: `battle`
- Priority: `P1`
- Depends: `SE-035, SE-036, SE-037`
- Writes: `docs/validation/battle-hardware.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Homologação não executada; histórico preservado no arquivo do MVP.
- Blocker: `Necessário acesso ao Batocera e a dois controles físicos.`

**Aceitação:**

- Testar dois controles físicos, modelos iguais/diferentes, hotplug, foco, pausa, áudio e desempenho no aparelho real.

### SE-039 — Concluir preparação e homologação da distribuição

- Status: `blocked`
- Scope: `battle`
- Priority: `P1`
- Depends: `none`
- Writes: `docs/validation/batocera-runtime.md; docs/validation/local-performance.md; docs/decisions/license.md; docs/RELEASE.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Homologação não executada; histórico preservado no arquivo do MVP.
- Blocker: `Aparelho indisponível e licença ainda não decidida pelo responsável; não declarar distribuição homologada.`

**Aceitação:**

- Pendências anteriores SE-004/024/026/027/028/029/030: coletar runtime, fixar dependências, revisar balanceamento, homologar controles/áudio/persistência, definir licença e fechar documentação da distribuição.
