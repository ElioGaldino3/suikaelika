# TODO — Suika Elika

Atualizado em 20/10/2026. O jogo clássico está funcional e jogável localmente.
O histórico detalhado do MVP foi arquivado em [docs/archive/TODO-classic.md](docs/archive/TODO-classic.md).
Este arquivo concentra BATALHA, entrada/diagnóstico e os bloqueios reais de homologação.
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


### SE-040 — Diagnóstico de controles e teclado desktop explícito

- Status: `done`
- Scope: `input`
- Priority: `P1`
- Depends: `SE-035`
- Writes: `tools/check_controllers.py; suika_elika/config.py; suika_elika/app.py; suika_elika/input/battle.py; suika_elika/scene_manager.py; tests/tools/test_check_controllers.py; tests/integration/test_desktop_mode.py; README.md; docs/DEVELOPMENT.md; docs/BATOCERA.md; docs/ARCHITECTURE.md; docs/PROJECT.md; docs/validation/controller-desktop.md; TODO.md`
- Reads: `suika_elika/input/controller.py; docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Implementado e revisado. 251 testes passaram, Ruff e mypy (46 fontes) aprovados, build e smoke do pacote com código 0. Diagnóstico real retornou 0 joysticks e teclado fora da contagem. Pesquisa, comandos, critérios e limitações em docs/validation/controller-desktop.md. Homologação física continua em SE-038/039.
- Blocker: `none`

**Aceitação:**

- Script independente lista quantidade e metadados de joysticks no terminal; JSON, execução sem display e erros de leitura explícitos.
- Teclado comum fora da contagem. Entrada nativa por padrão; --desktop autoriza fallback no clássico/menu, sem substituir o segundo controle da batalha.
- Seleção explícita de P1/P2 por índices SDL distintos; não presumir que a ordem do EmulationStation seja transmitida pelo lançador Pygame.
- Regressões, lint, tipos, build e smoke local aprovados; limitações de hardware registradas.


### SE-041 — Aperto imediato e lançamento ao segurar a 400 BPM

- Status: `done`
- Scope: `input`
- Priority: `P1`
- Depends: `SE-035, SE-036, SE-040`
- Writes: `suika_elika/contracts/input.py; suika_elika/input/manager.py; suika_elika/input/controller.py; suika_elika/input/joystick.py; suika_elika/app.py; suika_elika/game/spawning.py; suika_elika/game/session.py; suika_elika/game/catalog.py; suika_elika/scenes/play.py; suika_elika/scenes/battle.py; suika_elika/scenes/help.py; data/rules/classic-v4.json; tests/game/test_catalog.py; tests/game/test_randomizer.py; tests/game/test_session.py; tests/game/test_spawning.py; tests/input/test_actions.py; tests/input/test_devices.py; tests/integration/test_drop_repeat.py; tests/packaging/test_layout.py; tests/scenes/test_navigation.py; README.md; docs/PROJECT.md; docs/ARCHITECTURE.md; docs/DEVELOPMENT.md; docs/BATOCERA.md; docs/validation/drop-repeat.md; TODO.md`
- Reads: `suika_elika/game/physics.py; suika_elika/scene_manager.py`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Implementado e revisado. 266 testes passaram; Ruff e mypy (46 fontes) aprovados; grafo válido, build e smoke do pacote com código 0. Física real confirmou intervalos de 150 ms a 30/60/120 FPS. Comandos, critérios e limites em docs/validation/drop-repeat.md; homologação física permanece em SE-038/039.
- Blocker: `none`

**Aceitação:**

- Cada novo aperto tenta lançar sem cooldown artificial; segurar repete a cada 150 ms de simulação, no teclado autorizado e nos dois controles.
- Repetição para ao soltar e desarma em pausa/retomada/reinício, sem repetir confirmação nem gerar rajada após bloqueio.
- Área de nascimento continua protegida; velocidade inicial permite a cadência sem sobreposição. Ruleset classic-v4 separa os recordes.
- Testes de física/entrada/cenas e regressões aprovados; lint, tipos, build e evidências registrados; homologação física permanece pendente.


## Correção de controles no menu — 21/10/2026

- Status: `done`
- Corrigida a leitura das constantes SDL no namespace do Pygame 2.6.1:
  confirmação/soltura, voltar, Start, direcional digital e ajuste fino.
- Evidência: `python -m pytest -q`: 267 testes passaram;
  `python -m ruff check .`: aprovado; `python -m mypy`: 46 fontes aprovadas.
  Regressão usa o módulo real Controller com dispositivo simulado.
- Limitação: teste físico do usuário e Batocera pendentes. Confirmação usa
  o botão sul/A SDL; o rótulo X depende do mapeamento do controle.


## Meta da batalha e hold a 180 BPM — 21/10/2026

- Status: `done`
- BATALHA abre uma tela com 1000, 2000 e 5000 pontos; seleção define a vitória,
  o HUD e o resultado. Revanche e retomada preservam a meta. Voltar cancela a
  seleção; hotplug desabilita o início sem dois controles.
- Hold reduzido para 180 BPM (1/3 s) no clássico e batalha, mantendo apertos
  imediatos, interrupção ao soltar/pausar e ausência de rajadas após bloqueio.
  Ruleset `classic-v5` separa os recordes; catálogo anterior preservado.
- Evidência: `python -m pytest -q`: 277 passaram; `python -m ruff check .`:
  aprovado; `python -m mypy`: 46 fontes aprovadas; `git diff --check`: aprovado.
  Tela de seleção renderizada a 1280x720 e inspecionada visualmente.
- Limitações: testes de entrada usam dispositivos simulados; controle físico,
  áudio HDMI e execução no Batocera continuam sem homologação neste lote.
