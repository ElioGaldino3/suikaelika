# TODO — Suika Elika

Backlog de implementação derivado de `docs/PROJECT.md` e `docs/ARCHITECTURE.md`.
Atualizado em 20/10/2026. O jogo ainda não foi implementado. Esta revisão cria a governança e a skill; não inicia as tarefas do jogo.

## Operação do backlog

- Um único orquestrador atualiza metadados, reservas e evidências; trabalhadores devolvem entregas para revisão.
- Estados: `pending`, `in_progress`, `in_review`, `done`, `blocked`, `deferred`.
- `Depends` só libera a tarefa quando todos os IDs estiverem `done`. `blocked` exige remover o bloqueio com evidência, mesmo se as dependências terminarem.
- `Writes` reserva arquivos ou subárvores `/**`; `Reads` identifica contratos/entradas estáveis. Caminhos usam `/` e são relativos à raiz.
- Apenas o orquestrador altera TODO, contratos compartilhados e Git. Uma reserva de documentação arquitetural é trabalho de integração serial.
- `Owner` identifica o agente ativo ou `root`; volta a `unassigned` ao concluir/bloquear. `Attempts` conta despachos e não deve ser zerado para esconder tentativas.
- Antes de `done`, registrar critérios atendidos e comandos/resultados reais em `Evidence`. Testes simulados não homologam o aparelho.
- Lotes aceitos terminam em commit revisado; hashes ficam no relatório/log de lote, evitando gravar o hash de um commit dentro dele mesmo.
- Escopo `mvp` é o padrão de execução. `future` e `deferred` não entram por iniciativa do orquestrador.

Validador: `python skills/todo-orchestrator/scripts/todo_graph.py validate --todo TODO.md`.
Planejamento: `python skills/todo-orchestrator/scripts/todo_graph.py plan --todo TODO.md --scope mvp --team-slots 4 --max-workers 4`.
Quatro posições totais significam até três trabalhadores além do orquestrador; em um ambiente com cinco posições ou mais, o limite continua sendo quatro subagentes.

## Frentes paralelas sugeridas

As frentes indicam candidatos; somente o grafo e as reservas reais autorizam execução.

| Momento | Frentes possíveis |
|---|---|
| Preparação | SE-001; depois SE-002 e SE-003 em paralelo |
| Contratos concluídos | Catálogo SE-005, entrada SE-006, persistência SE-009, áudio SE-012 e viewport SE-017; selecionar até a capacidade |
| Catálogo pronto | Física SE-007 e desenhos SE-008, enquanto outras frentes independentes continuam |
| Física pronta | Fusões SE-013, perigo SE-014 e lançamento SE-015, com escritas distintas |
| Sistemas prontos | Sessão SE-016, menus SE-018 e apresentação SE-019 respeitam seus pré-requisitos |
| Integração | SE-020/021 são serializadas onde há arquivos compartilhados |
| Candidato local | Regressões SE-022, embalagem SE-023 e medições SE-025 conforme dependências |
| Equipamento disponível | SE-004 → SE-024 → SE-027/028; nenhuma alegação de Batocera homologado antes disso |
| Entrega | SE-029 depende também da decisão de licença SE-030 |

SE-004, SE-027, SE-028 e SE-030 têm bloqueios externos explícitos. Enquanto isso, o protótipo e as verificações locais independentes podem avançar. Não congelar uma matriz de distribuição não comprovada.

## Tarefas

### SE-000 — Preparar governança, arquitetura e orquestrador

- Status: `done`
- Scope: `mvp`
- Priority: `P0`
- Depends: `none`
- Writes: `AGENTS.md; TODO.md; .gitattributes; docs/ARCHITECTURE.md; docs/validation/orchestrator.md; skills/todo-orchestrator/**; README.md; docs/PROJECT.md`
- Reads: `docs/PROJECT.md`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: AGENTS, arquitetura, backlog e skill entregues; 23 testes aprovados, Ruff e mypy strict sem erros, skill-creator válido, grafo com 34 tarefas e revisão independente de regressões aprovados. Skill instalada com os 6 arquivos conferidos. Evidências em docs/validation/orchestrator.md; commit do lote no relatório final.
- Blocker: `none`

**Objetivo:** Entregar as instruções pedidas, o backlog paralelo e uma skill reutilizável com validador e instalação local.

**Aceitação:**
- AGENTS preserva o ciclo planejar/agir/avaliar, a conclusão verificável e o commit obrigatório.
- Backlog tem grafo acíclico, arquivos reserváveis, dependências e critérios de aceitação.
- Skill limita concorrência real, trata revisão, recuperação e gates externos, sem iniciar o jogo por este pedido.
- Validador, testes comportamentais, lint/tipos aplicáveis e revisão independente aprovados; commit do lote informado no relatório final.

### SE-001 — Criar base Python e ferramentas de qualidade

- Status: `done`
- Scope: `mvp`
- Priority: `P0`
- Depends: `SE-000`
- Writes: `pyproject.toml; suika_elika/__init__.py; suika_elika/game/__init__.py; suika_elika/input/__init__.py; suika_elika/rendering/__init__.py; suika_elika/scenes/__init__.py; tests/conftest.py; tests/test_imports.py; docs/DEVELOPMENT.md; .gitignore`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Pacote Python >=3.10, dependências runtime separadas do extra dev, namespaces sem inicialização e guia de desenvolvimento entregues. Na venv local Python 3.14.7, `python -m pytest` passou (1 teste), `python -m ruff check .` passou e `python -m mypy` passou (5 arquivos); a importação em subprocess limpo não carrega Pygame nem implementações. A instalação completa `.[dev]` não terminou porque não havia wheel Pygame 2.6.1 para Python 3.14 e a compilação foi interrompida; `pip check` confirma que Pygame/Pymunk não estão instalados no ambiente parcial. Context7 consultado para pygame, packaging, pytest, Ruff e mypy. Compatibilidade do Batocera não alegada.
- Blocker: `none`

**Objetivo:** Preparar pacote importável e comandos reais de testes, lint e tipos em ambiente de desenvolvimento isolado.

**Aceitação:**
- Declarar Python compatível com a proposta e separar dependências de execução/desenvolvimento, sem alegar lock homologado do Batocera.
- Importar o pacote não abre janela, áudio nem joystick; inicializadores de subpacotes não importam implementações futuras.
- Documentar e executar os comandos configurados de testes, lint e tipos; não criar implementação fictícia para fazer um smoke passar.

### SE-002 — Materializar contratos estáveis entre componentes

- Status: `done`
- Scope: `mvp`
- Priority: `P0`
- Depends: `SE-001`
- Writes: `suika_elika/contracts/**; tests/contracts/**`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; pyproject.toml; suika_elika/__init__.py; suika_elika/game/__init__.py; suika_elika/input/__init__.py; suika_elika/rendering/__init__.py; suika_elika/scenes/__init__.py; tests/conftest.py; tests/test_imports.py; docs/DEVELOPMENT.md; .gitignore`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Modelos e protocolos imutáveis para ações, eventos, snapshots, física, áudio, persistência e cenas entregues; bordas de entrada usam fila de consumo único e eventos/snapshots carregam apenas valores copiados. Na revisão, o orquestrador completou o contrato com navegação vertical (`move_y`, `NAV_UP/DOWN`), protocolos de perfil/estatísticas e modelos de configurações/recordes alinhados ao PROJECT. Na venv Python 3.14.7, `python -m pytest` passou (42 testes), `python -m ruff check .` passou e `python -m mypy` passou (14 arquivos). Testes confirmam invariantes, imutabilidade e importação sem Pygame/Pymunk. Ruff inclui `tools/**/*.py`.
- Blocker: `none`

**Objetivo:** Definir modelos tipados e interfaces de ações, snapshot, eventos, física, áudio, persistência e cenas.

**Aceitação:**
- Contratos seguem ARCHITECTURE e são importáveis sem Pygame/Pymunk inicializados.
- Snapshots não expõem corpos, dispositivos ou referências mutáveis do motor; bordas de ação e consumo único têm semântica explícita.
- Testes demonstram invariantes relevantes e tipos; orquestrador revisa os contratos antes de liberar consumidores.

### SE-003 — Criar diagnóstico portável e roteiro de coleta do alvo

- Status: `done`
- Scope: `mvp`
- Priority: `P0`
- Depends: `SE-001`
- Writes: `tools/diagnostics.py; tests/tools/test_diagnostics.py; docs/BATOCERA-ENVIRONMENT.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; pyproject.toml; suika_elika/__init__.py; suika_elika/game/__init__.py; suika_elika/input/__init__.py; suika_elika/rendering/__init__.py; suika_elika/scenes/__init__.py; tests/conftest.py; tests/test_imports.py; docs/DEVELOPMENT.md; .gitignore`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Coletor stdlib apresenta runtime/arquitetura, disponibilidade e versões de pacotes e estados de probes sem importar Pygame ou ler ambiente; guia mantém dados do Batocera como pendentes. Na venv Python 3.14.7, `python -m pytest` passou na suíte (14 testes), `python -m ruff check .` passou com `tools/**/*.py` incluído, `python -m mypy` passou (10 arquivos), e `python -m mypy --strict tools/diagnostics.py` passou. `python tools/diagnostics.py --format json` produziu relatório funcional, com Pygame/Pymunk ausentes e probes não executados. Nenhum dado do aparelho foi inferido.
- Blocker: `none`

**Objetivo:** Coletar versões, arquitetura e capacidades sem exigir que todas as dependências estejam instaladas.

**Aceitação:**
- Relatório identifica runtime, bibliotecas disponíveis e falhas parciais sem despejar variáveis de ambiente ou tokens.
- Separar coleta sem display de verificações gráficas/controladas; não abrir janela por importação.
- Documentar coleta no Batocera e registrar execução local como local, sem preencher dados desconhecidos do aparelho.

### SE-004 — Comprovar runtime e dependências no Batocera real

- Status: `blocked`
- Scope: `mvp`
- Priority: `P0`
- Depends: `SE-003`
- Writes: `docs/validation/batocera-runtime.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; tools/diagnostics.py; docs/BATOCERA-ENVIRONMENT.md; tests/tools/test_diagnostics.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Relato do usuário (20/10/2026): Batocera 43 em notebook x86, com `python3` disponível. Registro parcial em `docs/validation/batocera-runtime.md`; ainda sem saída do diagnóstico no equipamento nem versões confirmadas de runtime, bibliotecas ou probes.
- Blocker: `O usuário informa Batocera 43, notebook x86 e python3; falta executar tools/diagnostics.py no equipamento para confirmar arquitetura, runtime e dependências. Joystick físico continua necessário para a etapa de homologação.`

**Objetivo:** Executar a prova de Pygame, joystick e Pymunk no destino e identificar a matriz efetiva do equipamento.

**Aceitação:**
- Registrar Batocera, modelo, arquitetura, Python/ABI, libc, Pygame/SDL/Pymunk e controle/conexão.
- Iniciar pelo EmulationStation uma prova gráfica e de entrada; importar e avançar um mundo físico no alvo.
- Registrar resultados e falhas reais, inclusive estratégia de pacote nativo; simulação local não satisfaz esta tarefa.

### SE-005 — Implementar catálogo e sorteio isolado

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-002`
- Writes: `suika_elika/game/catalog.py; suika_elika/game/randomizer.py; data/rules/classic-v1.json; tests/game/test_catalog.py; tests/game/test_randomizer.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/contracts/**`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Catálogo versionado de 11 frutas valida IDs, ordem, raios, massas, pontos, cores e pesos; RNG privado com seed mantém sequência estável e só avança após soltura aceita. Na venv Python 3.14.7, `python -m pytest tests/game/test_catalog.py tests/game/test_randomizer.py` passou (17 testes), `python -m ruff check` nos quatro arquivos da tarefa passou e `python -m mypy` nos dois módulos passou. Não foi afirmada validação de balanceamento em hardware.
- Blocker: `none`

**Objetivo:** Representar as onze frutas e a sequência de lançamento do modo clássico.

**Aceitação:**
- Catálogo reproduz a proposta de IDs, raios e pontuação, com validação de dados e versão de regras.
- Somente níveis 1–5 são sorteados com os pesos definidos; atual/próxima avançam apenas em soltura aceita.
- Mesma seed produz mesma sequência, independentemente de RNG visual; testes cobrem consumo e rejeição de sorteios.

### SE-006 — Implementar ações e normalização de entrada

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-002`
- Writes: `suika_elika/input/actions.py; suika_elika/input/manager.py; tests/input/test_actions.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/contracts/**`
- Owner: `unassigned`
- Attempts: `2`
- Evidence: Normalização conforme PROJECT (deadzone 0,20, curva 1,3 e velocidades 520/420/100), prioridade/cancelamento digital, bordas sem repetição, backend exclusivo e navegação com limiar/histerese/repetição. Python 3.13.16: `python -m pytest tests/input/test_actions.py` (13 passed) e combinado com física (24 passed); Ruff direcionado e mypy strict direcionado passaram. Suíte global durante SE-008 em andamento: 71 passaram e 3 falharam apenas em `tests/rendering/test_procedural.py`; Ruff global reportou 17 E501 apenas em `suika_elika/rendering/procedural.py`.
- Blocker: `none`

**Objetivo:** Converter fontes de entrada em ações semânticas com bordas únicas e movimento normalizado.

**Aceitação:**
- Deadzone, curva, direções opostas, prioridade digital e ajuste fino seguem PROJECT.
- Uma borda de soltar não se repete entre subpassos nem fica guardada quando inválida.
- Manager expõe seleção exclusiva de backend e API estável para adaptadores, sem assumir botão 0 universal.

### SE-007 — Implementar mundo físico circular

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-002, SE-005`
- Writes: `suika_elika/game/physics.py; tests/game/test_physics.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/contracts/**; suika_elika/game/catalog.py; suika_elika/game/randomizer.py; data/rules/classic-v1.json; tests/game/test_catalog.py; tests/game/test_randomizer.py`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Pymunk 7.3.1; passo fixo 1/120 s, recipiente aberto 800×460, corpos circulares com massa/momento do catálogo, limites de velocidade, contatos copiados e mutações post-step. Na venv Python 3.13.16, `python -m pytest tests/game/test_physics.py tests/game/test_catalog.py tests/game/test_randomizer.py -q` (28 passed), Ruff e mypy passaram; `git diff --check` passou. Homologação Batocera continua em SE-004.
- Blocker: `none`

**Objetivo:** Criar o adaptador Pymunk e o recipiente com passo fixo e consultas de contatos.

**Aceitação:**
- Corpos, massas, inércias, paredes internas e boca aberta correspondem às regras propostas.
- Contatos retornam IDs e dados copiados; remoções e inserções são aplicadas fora do passo do motor.
- Cenários de queda, parede, repouso e limite de velocidade passam localmente; a homologação do runtime continua em SE-004.

### SE-008 — Desenhar frutas e cenário sem imagens externas

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-002, SE-005`
- Writes: `suika_elika/rendering/procedural.py; tests/rendering/test_procedural.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/contracts/**; suika_elika/game/catalog.py; suika_elika/game/randomizer.py; data/rules/classic-v1.json; tests/game/test_catalog.py; tests/game/test_randomizer.py`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Sprites cacheados das 11 frutas, recipiente e cenário em superfícies Pygame, com detalhes dentro dos bounds; importação lazy não inicializa Pygame. Python 3.13.16 + Pygame 2.6.1: `python -m pytest` (80 passed), testes direcionados (8 passed), Ruff e mypy direcionados passaram. Ruff/mypy globais, naquele estado do checkout, apontaram somente erros nos arquivos SE-010 ainda em edição.
- Blocker: `none`

**Objetivo:** Gerar superfícies das onze frutas, recipiente e cenário com primitivas do Pygame.

**Aceitação:**
- Cada fruta é reconhecível por cor e detalhes, com pivô/envelope coerentes com o raio físico.
- Sem PNG/JPEG obrigatório, sem biblioteca de IA ou processamento de imagens no runtime.
- Superfícies são reutilizáveis e não redesenhadas por pixel a cada quadro; dimensões e leitura têm evidências adequadas.

### SE-009 — Implementar persistência e diretórios da plataforma

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-002`
- Writes: `suika_elika/persistence.py; suika_elika/platform.py; tests/services/test_persistence.py; tests/services/test_platform.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/contracts/**`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Persistência JSON com schema v2 guarda opções de áudio/vídeo/acessibilidade/área segura, perfis com plataforma/GUID/eixos/inversões/calibração, recordes por modo + ruleset com duração e estatísticas. Escritas usam arquivo temporário/substituição atômica; JSON inválido fica preservado em cópia de recuperação; falhas ficam em `last_error` e valores permanecem acessíveis em memória. Caminhos Windows/Linux/Batocera e overrides cobertos. Na venv Python 3.14.7, `python -m pytest` passou (42 testes), `python -m ruff check .` passou, `python -m mypy` passou (14 arquivos) e `git diff --check` passou. Sem save de sessão física ou rede.
- Blocker: `none`

**Objetivo:** Salvar configurações, perfis, recordes por ruleset e estatísticas de forma recuperável.

**Aceitação:**
- JSON validado e versionado, substituição atômica e recuperação de arquivo inválido com preservação do original.
- Caminhos Windows/Linux/Batocera e overrides funcionam com testes em diretórios temporários.
- Falha de escrita permite continuar em memória; nenhum save de partida física ou rede é acrescentado.

### SE-010 — Implementar adaptadores SDL e joystick genérico

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-006`
- Writes: `suika_elika/input/controller.py; suika_elika/input/joystick.py; tests/input/test_devices.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/input/actions.py; suika_elika/input/manager.py; tests/input/test_actions.py`
- Owner: `unassigned`
- Attempts: `2`
- Evidence: Adaptadores SDL Controller e Joystick usam índices apenas na abertura, `instance_id` no ciclo de conexão, preferem caminho Controller e não adivinham botões genéricos; eixo Controller int16 e Joystick float normalizados separadamente; fallback sem `_sdl2.controller`/rumble. Testes simulados. Python 3.13.16: `pytest tests/input -q` (26 passed), Ruff e mypy estrito direcionados passaram; suíte global `python -m pytest` (100 passed). Joystick físico ainda não homologado.
- Blocker: `none`

**Objetivo:** Ler controles reconhecidos e genéricos com identidade de instância e ciclo de conexão.

**Aceitação:**
- Normalizar o formato correto de cada API de eixo; não confundir índice de abertura com instance_id.
- Descoberta, remoção e remapeamento não duplicam dispositivo ou ação entre Controller e Joystick.
- Ausência de _sdl2.controller ou rumble permite fallback; testes simulados são rotulados como simulados.

### SE-011 — Implementar perfis e assistente de remapeamento

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-006, SE-009`
- Writes: `suika_elika/input/profiles.py; tests/input/test_profiles.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/input/actions.py; suika_elika/input/manager.py; tests/input/test_actions.py; suika_elika/persistence.py; suika_elika/platform.py; tests/services/test_persistence.py; tests/services/test_platform.py`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: IDs estáveis baseados em plataforma/GUID/nome/backend, sem instance_id; assistente aguarda neutro, rejeita amostras ambíguas, permite cancelar/restaurar e pular ajuste fino; repositório mantém perfil anterior em falha. Python 3.13.16: suíte global `python -m pytest` (80 passed), direcionados (6 testes de perfis e 8 de renderização), Ruff direcionado e mypy estrito direcionado passaram. Ruff/mypy globais, naquele estado do checkout, apontaram somente erros nos arquivos SE-010 ainda em edição.
- Blocker: `none`

**Objetivo:** Configurar e persistir ações de controles sem depender de teclado.

**Aceitação:**
- Perfis distinguem plataforma/GUID e não persistem instance_id como identidade estável.
- Fluxo passo a passo exige retorno ao neutro, permite cancelar/restaurar/pular ajuste fino e preserva perfil anterior em falha.
- Modelo do assistente é independente de cenas concretas e pode ser usado pela tela de opções.

### SE-012 — Implementar serviço de áudio e fallback silencioso

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-002`
- Writes: `suika_elika/audio.py; tests/services/test_audio.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/contracts/**`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Efeitos PCM sintetizados originais, canais por prioridade, limites de queda/aviso, ganhos, pausa/retomada/encerramento e fallback nulo quando o mixer falha; importação não abre áudio. Python 3.13.16: teste direcionado (11 passed), suíte global (107 passed), Ruff global e mypy global passaram. Testes de mixer são simulados; áudio físico/HDMI ainda não homologado.
- Blocker: `none`

**Objetivo:** Consumir eventos com efeitos curtos, ganhos separados e operação silenciosa quando não houver mixer.

**Aceitação:**
- Queda, fusão, aviso e resultado têm política de prioridade e limite de repetição; repouso não gera ruído contínuo.
- Ausência de áudio não quebra a sessão; pausa e encerramento liberam recursos.
- Protótipo usa tons próprios/PCM ou silêncio, sem extração dos vídeos; música final não é exigida neste lote.

### SE-013 — Implementar fusões transacionais e cadeias

- Status: `done`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-005, SE-007`
- Writes: `suika_elika/game/merging.py; tests/game/test_merging.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/game/catalog.py; suika_elika/game/randomizer.py; data/rules/classic-v1.json; tests/game/test_catalog.py; tests/game/test_randomizer.py; suika_elika/game/physics.py; tests/game/test_physics.py`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: Resolução pós-step determinística reserva pares sem sobreposição, gera filho com pose corrigida, velocidade linear/angular amortecida via PhysicsPort, herda risco/proteção e registra score/eventos; pares de melancia removem ambas e valem 100. Python 3.13.16: 7 testes direcionados e suíte global (107 passed), Ruff global e mypy global passaram. Contatos de domínio são valores copiados; testes transacionais usam fake PhysicsPort.
- Blocker: `none`

**Objetivo:** Resolver pares iguais de forma estável, sem consumo ou pontuação duplicados.

**Aceitação:**
- Três iguais, dois pares simultâneos, contato persistente e filhos em passos seguintes seguem as invariantes de PROJECT.
- Filho usa catálogo, posição/correção local, velocidade amortecida e herança de perigo; duas melancias removem ambas e valem 100 pontos.
- Eventos representam fusões confirmadas e nenhuma transação guarda Arbiter ou altera mundo bloqueado.

### SE-014 — Implementar proteção, transbordamento e escape

- Status: `in_progress`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-007`
- Writes: `suika_elika/game/danger.py; tests/game/test_danger.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/game/physics.py; tests/game/test_physics.py`
- Owner: `se014`
- Attempts: `1`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Aplicar a regra de perigo por entidade e produzir um motivo de derrota compreensível.

**Aceitação:**
- Proteção de entrada tem prazo finito e não é renovada por fusão.
- Contagem, faixa de histerese, recuperação e escape usam tempo de simulação e maior risco individual.
- Testes incluem pilha na boca, fusão perto da linha, pausa e corpo fora do recipiente; não confundir erro de solver com sucesso.

### SE-015 — Implementar lançamento e previsão estática da mira

- Status: `in_progress`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-005, SE-007`
- Writes: `suika_elika/game/spawning.py; tests/game/test_spawning.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/game/catalog.py; suika_elika/game/randomizer.py; data/rules/classic-v1.json; tests/game/test_catalog.py; tests/game/test_randomizer.py; suika_elika/game/physics.py; tests/game/test_physics.py`
- Owner: `se015`
- Attempts: `1`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Gerenciar fruta em espera, limites horizontais, contato/cooldown e bloqueio de nascimento.

**Aceitação:**
- Fruta em espera não tem corpo; soltura aceita cria um corpo e rejeitada não consome sequência.
- WAIT_CONTACT/COOLDOWN/BLOCKED/READY e timeout seguem PROJECT, sem repetir botão segurado.
- Mira considera soma dos raios e primeiro contato estático, sem prometer a posição final.

### SE-016 — Coordenar sessão e snapshots da partida

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-005, SE-013, SE-014, SE-015`
- Writes: `suika_elika/game/session.py; tests/game/test_session.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/game/catalog.py; suika_elika/game/randomizer.py; data/rules/classic-v1.json; tests/game/test_catalog.py; tests/game/test_randomizer.py; suika_elika/game/merging.py; tests/game/test_merging.py; suika_elika/game/danger.py; tests/game/test_danger.py; suika_elika/game/spawning.py; tests/game/test_spawning.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Unir os sistemas de gameplay na ordem fixa sem dependência de renderização.

**Aceitação:**
- A ordem resolve fusões antes de derrota e pontua uma única vez por evento confirmado.
- Pausa/reinício limpam entradas e preservam/zeram a sessão conforme ação, sem entidades antigas.
- Snapshots e eventos satisfazem os contratos; recordes por ruleset e estatísticas ficam disponíveis para a aplicação.

### SE-017 — Implementar viewport e escala de apresentação

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-002`
- Writes: `suika_elika/rendering/viewport.py; tests/rendering/test_viewport.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/contracts/**`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Preservar a tela lógica 1280x720 em diferentes resoluções, com margem segura.

**Aceitação:**
- Escala uniforme e centralização mantêm círculos e coordenadas de gameplay.
- Conversões entre viewport e tela são consistentes em 720p, 1080p, 4K e 4:3.
- Não exigir vsync garantido ou driver específico; limitações de leitura em baixa resolução são documentadas.

### SE-018 — Implementar menus, opções e ajuda por ações

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-006, SE-009, SE-011, SE-017`
- Writes: `suika_elika/scenes/title.py; suika_elika/scenes/options.py; suika_elika/scenes/help.py; suika_elika/scenes/pause.py; suika_elika/scenes/results.py; tests/scenes/test_navigation.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/input/actions.py; suika_elika/input/manager.py; tests/input/test_actions.py; suika_elika/persistence.py; suika_elika/platform.py; tests/services/test_persistence.py; tests/services/test_platform.py; suika_elika/input/profiles.py; tests/input/test_profiles.py; suika_elika/rendering/viewport.py; tests/rendering/test_viewport.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Criar navegação completa com foco visível e retorno ao contexto de origem.

**Aceitação:**
- Jogar, ajuda, pausa, opções, resultado e saída operam por ações sem campo de texto obrigatório.
- Opções retornam ao contexto correto; abandonar/reiniciar exigem confirmação sem usar o mesmo aperto duas vezes.
- Tela usa idioma português, controle por posição física e configuração do assistente de perfis.

### SE-019 — Compor partida, HUD e efeitos visuais

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-008, SE-016, SE-017`
- Writes: `suika_elika/rendering/renderer.py; suika_elika/rendering/hud.py; suika_elika/rendering/effects.py; suika_elika/scenes/play.py; tests/rendering/test_composition.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/rendering/procedural.py; tests/rendering/test_procedural.py; suika_elika/game/session.py; tests/game/test_session.py; suika_elika/rendering/viewport.py; tests/rendering/test_viewport.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Renderizar snapshot e eventos com frutas, mira, placar, prévia, evolução e perigo.

**Aceitação:**
- Ordem de desenho e recorte deixam boca/frutas em risco visíveis; pose anterior/atual interpolada sem teletransporte visual.
- Atual/próxima e pontos correspondem à sessão; partículas não alteram física ou RNG de frutas.
- Efeitos reduzidos, textos legíveis e limites de partículas/cache são respeitados sem imagens externas.

### SE-020 — Integrar aplicação e fluxo jogável local

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-010, SE-011, SE-012, SE-016, SE-018, SE-019`
- Writes: `suika_elika/app.py; suika_elika/scene_manager.py; suika_elika/config.py; suika_elika/__main__.py; main.py; tests/integration/test_app_flow.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/input/controller.py; suika_elika/input/joystick.py; tests/input/test_devices.py; suika_elika/input/profiles.py; tests/input/test_profiles.py; suika_elika/audio.py; tests/services/test_audio.py; suika_elika/game/session.py; tests/game/test_session.py; suika_elika/scenes/title.py; suika_elika/scenes/options.py; suika_elika/scenes/help.py; suika_elika/scenes/pause.py; suika_elika/scenes/results.py; tests/scenes/test_navigation.py; suika_elika/rendering/renderer.py; suika_elika/rendering/hud.py; suika_elika/rendering/effects.py; suika_elika/scenes/play.py; tests/rendering/test_composition.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Entregar uma partida local que inicia, pausa, termina, reinicia e sai.

**Aceitação:**
- Composição usa contratos, loop fixo com limite de recuperação, cenas e serviços sem importações circulares.
- Áudio indisponível e foco perdido são tratados; QUIT libera recursos e retorna código de saída apropriado.
- Teste de integração e observação local comprovam fluxo real; não declarar validação do Batocera nesta tarefa.

### SE-021 — Fechar reconexão e duplicidade de entrada ponta a ponta

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-020`
- Writes: `suika_elika/input/manager.py; suika_elika/app.py; tests/integration/test_controller_lifecycle.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/app.py; suika_elika/scene_manager.py; suika_elika/config.py; suika_elika/__main__.py; main.py; tests/integration/test_app_flow.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Integrar escolha de jogador, perda de controle e modos exclusivos nativo/teclado emulado.

**Aceitação:**
- Controle ativo removido pausa e limpa estados; reconectar exige confirmação sem queda residual.
- Segundo controle não comanda a partida sem fluxo explícito de substituição.
- Simular Controller+Joystick+tecla traduzida prova uma ação por aperto; documentar seleção do modo Batocera.

### SE-022 — Cobrir regressões integradas do modo clássico

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-020, SE-021`
- Writes: `tests/integration/test_classic_rules.py; tests/integration/test_failure_recovery.py; docs/validation/local-functional.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/app.py; suika_elika/scene_manager.py; suika_elika/config.py; suika_elika/__main__.py; main.py; tests/integration/test_app_flow.py; suika_elika/input/manager.py; tests/integration/test_controller_lifecycle.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Verificar cenários de aceitação de PROJECT e registrar limites do teste local.

**Aceitação:**
- Cobrir fusões concorrentes, bloqueio de spawn, derrota e fusão no mesmo passo, pausa, RNG e reinícios repetidos.
- Persistência inválida/indisponível e áudio ausente não impedem o fluxo permitido.
- Comandos, versões, resultados e checks não executados constam no relatório; erros encontrados geram correção reservada pelo orquestrador.

### SE-023 — Preparar launchers e instruções de distribuição

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-003, SE-020`
- Writes: `packaging/batocera/**; tests/packaging/test_layout.py; docs/BATOCERA.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tools/diagnostics.py; tests/tools/test_diagnostics.py; docs/BATOCERA-ENVIRONMENT.md; suika_elika/app.py; suika_elika/scene_manager.py; suika_elika/config.py; suika_elika/__main__.py; main.py; tests/integration/test_app_flow.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Preparar a categoria Pygame e a alternativa Ports, sem alegar pacote universal.

**Aceitação:**
- .pygame contém entrada Python; .sh usa LF, aspas e exec; recursos são resolvidos a partir da instalação.
- Dados graváveis ficam em userdata separado e variáveis SDL existentes são preservadas.
- Layout e bootstrap são verificáveis localmente; dependências finais e execução real continuam dependentes de SE-024/027.

### SE-024 — Fixar e construir dependências para o alvo identificado

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-004, SE-023`
- Writes: `packaging/targets/**; packaging/locks/**; tools/build_target.py; tests/packaging/test_target_manifest.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; docs/validation/batocera-runtime.md; packaging/batocera/**; tests/packaging/test_layout.py; docs/BATOCERA.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Produzir dependências nativas e manifesto de um destino comprovado.

**Aceitação:**
- Manifesto registra arquitetura, ABI, libc e versões/hash das dependências; separar pacote do jogo e tooling.
- Pymunk/CFFI importam no runtime do destino; não copiar wheel Windows para Linux nem instalar globalmente ao iniciar.
- Build reproduzível e suas evidências são documentados sem substituir Pygame/SDL do sistema sem justificativa.

### SE-025 — Medir e ajustar desempenho do protótipo

- Status: `pending`
- Scope: `mvp`
- Priority: `P2`
- Depends: `SE-020, SE-022`
- Writes: `tools/performance.py; suika_elika/rendering/procedural.py; suika_elika/rendering/renderer.py; suika_elika/rendering/effects.py; docs/validation/local-performance.md; tests/rendering/test_resource_limits.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; suika_elika/app.py; suika_elika/scene_manager.py; suika_elika/config.py; suika_elika/__main__.py; main.py; tests/integration/test_app_flow.py; tests/integration/test_classic_rules.py; tests/integration/test_failure_recovery.py; docs/validation/local-functional.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Medir custo de quadros, física, partículas e cache; melhorar gargalos demonstrados.

**Aceitação:**
- Cenários normais e de estresse produzem relatório com ambiente, percentis/picos e memória quando medível.
- Otimizações não mudam sorteio, física ou pontuação silenciosamente; perfil leve só altera apresentação.
- Execução prolongada local investiga crescimento de memória; resultados locais não são atribuídos ao Batocera.

### SE-026 — Revisar balanceamento e congelar regras candidatas

- Status: `pending`
- Scope: `mvp`
- Priority: `P2`
- Depends: `SE-022, SE-025`
- Writes: `data/rules/classic-v1.json; docs/validation/balance.md; tests/game/test_ruleset_version.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; tests/integration/test_classic_rules.py; tests/integration/test_failure_recovery.py; docs/validation/local-functional.md; tools/performance.py; suika_elika/rendering/procedural.py; suika_elika/rendering/renderer.py; suika_elika/rendering/effects.py; docs/validation/local-performance.md; tests/rendering/test_resource_limits.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Avaliar sensação do recipiente largo e consistência das regras propostas antes da homologação.

**Aceitação:**
- Registrar observação real do protótipo e justificar alterações em raios, sorteio, pontuação ou tolerâncias.
- Mudança com impacto em comparabilidade atualiza ruleset e recordes de forma explícita.
- Nenhum ajuste favorece o jogador alterando a prévia oculta; verificar invariantes após tuning.

### SE-027 — Homologar instalação e controles no Batocera

- Status: `blocked`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-021, SE-024, SE-025, SE-026`
- Writes: `docs/validation/batocera-gameplay.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; docs/validation/batocera-runtime.md; packaging/targets/**; packaging/locks/**; docs/BATOCERA.md; suika_elika/input/manager.py; suika_elika/app.py; tests/integration/test_controller_lifecycle.py; tools/build_target.py; tests/packaging/test_target_manifest.py; tools/performance.py; suika_elika/rendering/procedural.py; suika_elika/rendering/renderer.py; suika_elika/rendering/effects.py; docs/validation/local-performance.md; tests/rendering/test_resource_limits.py; data/rules/classic-v1.json; docs/validation/balance.md; tests/game/test_ruleset_version.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `Requer acesso ao Batocera e joystick físico após concluir o pacote alvo. Desbloquear somente com ambiente e dependências disponíveis; testes locais não substituem a sessão real.`

**Objetivo:** Executar a versão candidata no frontend do equipamento e com joystick real.

**Aceitação:**
- Iniciar, jogar, pausar, configurar, reiniciar e sair pelo controle; registrar hotkey e modo de entrada.
- USB/Bluetooth disponíveis, reconexão, controle genérico e duplicidade são avaliados nos dispositivos realmente usados.
- Registrar versão/pacote, resoluções, desempenho e falhas reais; cenários sem dispositivo ficam pendentes identificados.

### SE-028 — Homologar áudio, persistência e recuperação no alvo

- Status: `blocked`
- Scope: `mvp`
- Priority: `P1`
- Depends: `SE-024, SE-027`
- Writes: `docs/validation/batocera-services.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; docs/validation/batocera-gameplay.md; docs/BATOCERA.md; packaging/targets/**; packaging/locks/**; tools/build_target.py; tests/packaging/test_target_manifest.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `Requer pacote homologável, acesso ao Batocera, controle e saída de áudio real. Desbloquear após SE-027 e disponibilidade desses recursos.`

**Objetivo:** Verificar serviços periféricos e retorno ao frontend na distribuição candidata.

**Aceitação:**
- Comprovar recordes/opções após fechar e reabrir; registrar permissões e caminhos efetivos.
- Avaliar HDMI, volumes, mute/falha de áudio e encerramento com retorno de controle ao EmulationStation.
- Documentar casos testados, não testados e erros com condição de correção; sem marcar check físico por simulação.

### SE-029 — Publicar documentação local e fechar MVP homologado

- Status: `pending`
- Scope: `mvp`
- Priority: `P2`
- Depends: `SE-022, SE-027, SE-028, SE-030`
- Writes: `README.md; docs/RELEASE.md; THIRD_PARTY_NOTICES.md; LICENSE; docs/ARCHITECTURE.md; docs/PROJECT.md`
- Reads: `docs/validation/**; docs/BATOCERA.md; packaging/targets/**; packaging/locks/**; tests/integration/test_classic_rules.py; tests/integration/test_failure_recovery.py; docs/validation/local-functional.md; docs/validation/batocera-gameplay.md; docs/validation/batocera-services.md; docs/decisions/license.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Preparar entrega local do MVP com escopo, licença definida pelo responsável e matriz comprovada.

**Aceitação:**
- README contém comandos existentes, instalação, controles e limitações reais; documentação reflete a implementação.
- Licença do código precisa de decisão do responsável e avisos de dependências/assets são completos; não escolher licença em nome dele sem autorização.
- Critérios de aceitação do MVP revisados, artefato/manifests registrados e commit final criado; publicação externa só com pedido explícito.

### SE-030 — Definir licença e condições da distribuição

- Status: `blocked`
- Scope: `mvp`
- Priority: `P2`
- Depends: `SE-000`
- Writes: `docs/decisions/license.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `Licença do código ainda não escolhida pelo responsável. Desbloquear com decisão explícita antes da entrega de distribuição.`

**Objetivo:** Registrar a decisão do responsável sobre licença antes de distribuir o projeto.

**Aceitação:**
- Apresentar opções e dependências relevantes quando essa decisão for solicitada.
- Registrar uma escolha explícita do responsável, sem inferir uma licença a partir de exemplos.

### SE-031 — Produzir arte própria e mascote Elika

- Status: `deferred`
- Scope: `future`
- Priority: `P3`
- Depends: `SE-029`
- Writes: `assets/fruits/**; assets/backgrounds/**; assets/mascot/**; docs/art/**`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; README.md; docs/RELEASE.md; THIRD_PARTY_NOTICES.md; LICENSE`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Criar guia visual e imagens próprias depois de aprovar o protótipo.

**Aceitação:**
- Aprovar fruta piloto e identidade do mascote antes da produção completa.
- Arte mantém pivôs, envelopes, legibilidade e orçamento; não copia assets dos vídeos.

### SE-032 — Especificar estágios e temas adicionais

- Status: `deferred`
- Scope: `future`
- Priority: `P3`
- Depends: `SE-029`
- Writes: `docs/modes/stages.md; assets/themes/**`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; README.md; docs/RELEASE.md; THIRD_PARTY_NOTICES.md; LICENSE`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Planejar progressão por estágios e cenários sem alterar o modo clássico.

**Aceitação:**
- Requisitos e regras são aprovados em escopo próprio.
- Recordes e configurações distinguem modos quando houver impacto em gameplay.

### SE-033 — Especificar itens e economia opcional

- Status: `deferred`
- Scope: `future`
- Priority: `P3`
- Depends: `SE-029`
- Writes: `docs/modes/items.md`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/**; README.md; docs/RELEASE.md; THIRD_PARTY_NOTICES.md; LICENSE`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** Avaliar itens/recompensas vistos na referência apenas mediante novo escopo.

**Aceitação:**
- Especificar efeito, disponibilidade e limites de cada item.
- Não adicionar compras, serviços externos ou economia ao clássico por inferência da referência.
