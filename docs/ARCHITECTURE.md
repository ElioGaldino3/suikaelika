# Arquitetura de Suika Elika

**Revisão:** 0.2, 21/10/2026. **Estado:** contratos do runtime local e pacotes Batocera/Android TV; homologação de hardware continua pendente.

O produto e os parâmetros de gameplay estão em [PROJECT.md](PROJECT.md). Este documento organiza dependências e contratos para permitir implementação paralela. Não substitui nem duplica as tabelas de regras de `PROJECT.md`.

## 1. Decisões base

| Decisão | Motivo | Estado |
|---|---|---|
| Python + Pygame oficial | Requisito do produto e compatibilidade pesquisada | Definida como direção |
| Pymunk para física | Contatos circulares e empilhamento | Candidato; pacote no alvo pendente |
| Passo fixo de simulação, apresentação independente | Consistência e estabilidade | Contrato; parâmetros em PROJECT |
| Imagens procedurais inicialmente | Primeiro protótipo independente de assets externos | Definida |
| Clássico individual e batalha local 1x1 offline | Batalha autorizada em 20/10/2026 | Implementados localmente |
| Entrada por ações, com adaptadores de dispositivos | Joystick, remapeamento e prevenção de duplicidade | Definida |
| Configurações e recordes em JSON | Persistência simples e inspecionável | Proposta |

As versões citadas em PROJECT são candidatas, não uma matriz homologada. É permitido prototipar localmente enquanto o alvo estiver indisponível. Congelar dependências do pacote, balanceamento final e alegar compatibilidade com Batocera dependem dos gates de hardware do TODO.

## 2. Direção das dependências

```text
contratos e modelos imutáveis
    ├── catálogo / regras / RNG
    ├── adaptadores de entrada
    ├── persistência e plataforma
    ├── apresentação procedural / viewport
    └── áudio

catálogo + contratos → mundo físico
mundo físico → fusões / lançamento / perigo
esses sistemas → sessão → snapshot + eventos

entrada → ações → aplicação / cenas → sessão
snapshot + eventos → renderização / áudio / interface
aplicação → persistência / plataforma / encerramento
```

As setas indicam dependência de leitura/chamada; não permitem importações circulares. `game/` não importa cenas, renderer, mixer nem adaptadores concretos de joystick. O motor físico pode importar Pymunk; modelos públicos e regras puras devem continuar utilizáveis sem abrir janela ou dispositivo.

## 3. Contratos que serão materializados em SE-002

A tarefa SE-002 cria os modelos e interfaces em `suika_elika/contracts/`, com tipos e testes de contrato. Os consumidores dependem de sua conclusão. Assinaturas abaixo são semânticas e devem ser convertidas em tipos concretos nessa tarefa, antes da delegação dos consumidores.

| Contrato | Dados e operações mínimas |
|---|---|
| `InputFrame` | `move_x` e `move_y` normalizados, ajuste fino, estado contínuo `drop_held` e bordas de `drop`, `confirm`, `cancel`, `pause`, `nav_up`, `nav_down`; sem referências SDL |
| `DomainEvent` | Tipo, passo de simulação, IDs relevantes, posição e payload tipado/copied; sem `Arbiter` |
| `FruitDefinition` | ID, nível, raio, massa, pontos de criação e chave visual |
| `FruitSnapshot` | ID, tipo, pose anterior/atual e estado visual de perigo; sem corpo mutável |
| `SessionSnapshot` | Pontos, recorde contextual, atual/próxima, frutas, estado de lançamento, perigo e estado da rodada |
| `PhysicsPort` | Criar/remover corpo (incluindo velocidade linear/angular inicial), avançar passo, consultar contatos, sobreposição e poses; exclusividade de mutação pelo mundo físico |
| `AudioPort` | Consumir eventos, ajustar ganhos, pausar e encerrar; implementação silenciosa equivalente |
| `PersistencePort` | Carregar/salvar modelos validados e comunicar falha de persistência |
| `SettingsData` / `ControllerProfileData` / `RecordData` / `StatisticsData` | Preferências de áudio, vídeo, acessibilidade e área segura; perfil por plataforma/GUID com bindings e calibração; recorde por modo e ruleset com duração; estatísticas acumuladas |
| `Scene` | Entrar/sair, receber ações, atualizar interface e desenhar; retorno de transição explícito |

`InputFrame` é um snapshot por quadro de entrada. Bordas para gameplay são enfileiradas com número de sequência e consumidas uma vez no primeiro passo elegível; nenhum subpasso reaplica uma borda. O estado contínuo `drop_held` permite repetições separadas geradas pela sessão em tempo de simulação. Ações inválidas são descartadas segundo as regras do lançador, sem fila oculta para uma queda posterior. A navegação em menus usa `move_y` normalizado e gera `nav_up`/`nav_down` com limiar, histerese e repetição medidos pelo relógio da interface.

Eventos pertencem ao passo que os produziu. O `Renderer` recebe snapshots e eventos de apresentação; não modifica entidades. Uma UI que precisa de configuração envia um comando à aplicação. Não altera silenciosamente as regras da sessão ativa.

## 4. Propriedade de estado e ordem do loop

Somente `PhysicsWorld` altera corpos e formas. `MergeSystem` prepara transações aplicadas depois de `space.step()`. `GameSession` é dona do sorteio, da pontuação e das estatísticas; áudio e partículas nunca consomem seu RNG.

Ordem de cada passo: consumir comandos válidos → guardar poses anteriores → avançar física → confirmar fusões/remoções → atualizar lançador → avaliar perigo e escape → emitir snapshot/eventos. A decisão de derrota considera a coleção final de entidades daquele passo.

Pausa, foco perdido e desconexão congelam tempo de simulação, limpam entradas residuais e zeram o acumulador. Ao retomar, a confirmação é consumida pela UI e não vira soltura. O relógio visual de menus pode continuar.

Apertos físicos novos tentam lançar imediatamente, sem cooldown. `HeldDropRepeater`, pertencente a cada `GameSession`, arma somente a partir de uma borda DROP com `drop_held=True`, agenda tentativas a cada 333,33 ms de simulação (180 BPM) e desarma ao soltar, pausar, retomar ou reiniciar. Repetições não fabricam bordas nem alteram os números de sequência dos dispositivos. Não há rajada após atraso/bloqueio. `FruitLauncher` mantém somente READY/BLOCKED, consulta a área de nascimento a cada tentativa e cria frutas com velocidade vertical inicial de 520 unidades/s; contatos/fundo não são pré-requisitos para outro lançamento. Ruleset `classic-v5` separa os recordes pela mudança de ritmo e velocidade inicial.

Parâmetros de passo, sorteio, massa, pontos, raio e derrota pertencem ao ruleset. Perfis gráficos reduzem efeitos sem mudar a simulação. Alterações que impactem comparabilidade de recordes exigem revisar `ruleset_version`.

## 5. Fronteiras de módulos

| Caminho planejado | Responsabilidade |
|---|---|
| `suika_elika/contracts/` | Modelos imutáveis, enums e interfaces compartilhadas |
| `game/catalog.py`, `game/randomizer.py`, `data/rules/` | Catálogo e sequência |
| `game/physics.py` | Adaptação Pymunk e consultas |
| `container_geometry.py` | Contorno retangular compartilhado entre colisores e desenho da cesta |
| `game/merging.py` | Pares, reservas e transações de fusão |
| `game/spawning.py` | Fruta em espera, posição e bloqueio de soltura |
| `game/danger.py` | Proteção, herança, contagem e escape |
| `game/session.py` | Coordenação da rodada e publicação de snapshots/eventos |
| `input/actions.py`, `input/manager.py` | Estado semântico e seleção de backend |
| `input/controller.py`, `input/joystick.py` | Dispositivos concretos e ciclo de conexão |
| `input/profiles.py` | Mapeamento, calibração e configuração |
| `rendering/procedural.py`, `rendering/viewport.py` | Desenho sem assets e transformação de tela |
| `rendering/renderer.py`, `hud.py`, `effects.py` | Composição da partida e efeitos |
| `scenes/` | Navegação, pausa, opções e resultado |
| `audio.py`, `persistence.py`, `platform.py` | Serviços periféricos |
| `app.py`, `scene_manager.py`, `__main__.py`, `main.py` | Composição e entradas da aplicação |
| `packaging/batocera/`, `tools/` | Distribuição e diagnóstico, separados do gameplay |

Novos módulos pequenos dentro dessas fronteiras são permitidos quando melhorarem a clareza. Se a mudança ultrapassar o campo `Writes` de uma tarefa, o agente pede ajuste ao orquestrador antes de editar. Arquivos `__init__.py`, configurações de tooling e contratos compartilhados não são propriedade implícita de todas as tarefas.

## 6. Estratégia de verificação

Regras, RNG e temporizadores têm testes puros. Física tem cenários de integração sem tela quando possível. Entrada usa eventos simulados e testes de reconexão; estes não substituem o controle físico. Renderização recebe verificações de dimensão, viewport e testes visuais pertinentes. Audio usa implementação silenciosa para isolar testes de gameplay.

SE-001 configura comandos reais de testes, lint e tipos; os nomes/comandos não são declarados existentes antes da implementação. Até lá, cada mudança executa as verificações aplicáveis a seus arquivos. O verificador da skill é independente e usa apenas a biblioteca padrão do Python.

Homologação do Batocera registra versão, arquitetura, Python/ABI, Pygame/SDL/Pymunk, joystick, conexão, saída de áudio e resultados. Gates externos são tarefas explícitas e não podem ser aprovados com execução headless local.

## 7. Contratos e trabalho paralelo

O orquestrador é o único escritor de TODO e dos contratos arquiteturais durante uma rodada. Campos `Writes` reservam arquivos ou subárvores; `Reads` identifica entradas cuja alteração concorrente também exige serialização. Somente a conclusão verificada das dependências libera consumidores.

Mudança de contrato: interromper os consumidores afetados em um ponto seguro, revisar a proposta, atualizar arquitetura/contratos e backlog, verificar compatibilidade e só então retomar. Não deixar dois agentes resolverem o mesmo contrato de maneiras diferentes.

Em checkout compartilhado, revisar mudanças no local. Worktrees isolados só serão usados se o ambiente ou o escopo os exigir; nesse caso a integração é serial, por commit conhecido, sem misturar aplicação de patch e cherry-pick para o mesmo conteúdo.

## 8. Registro de decisões

| ID | Decisão | Consequência |
|---|---|---|
| ADR-001 | Contratos antes dos consumidores | Uma etapa curta antecede as frentes paralelas |
| ADR-002 | Pymunk candidato condicionado ao alvo | Desenvolvimento local pode continuar, distribuição fica bloqueada sem prova |
| ADR-003 | TODO com escritor único e evidências | Subagentes entregam para revisão; orquestrador conclui |
| ADR-004 | Arte procedural no MVP | Produção de imagens finais é tarefa futura separada |
| ADR-005 | Versões e recordes por ruleset | Ajustes de física, inclusive escalas individuais de hitbox configuráveis, não misturam resultados incomparáveis; cada combinação de raios tem um ruleset próprio. |
| ADR-006 | Batalha coordena duas GameSession independentes | Mesmo catálogo e seed, cestas 480×460, placares e física separados, sem persistência do clássico |
| ADR-007 | Slots de batalha por instance ID | GUID/nome apenas para reconquistar slot ausente; modelos iguais conectados continuam jogadores distintos |
| ADR-008 | Teclado somente com `--desktop` | Padrão nativo em todos os sistemas; teclado como fallback explícito, fora da contagem de joysticks |
| ADR-009 | Bordas imediatas e hold em tempo de simulação | 180 BPM por sessão; `drop_held` propagado pelas cenas, sem repetir confirmações nem depender do repeat do sistema |
| ADR-010 | Bootstrap de Pymunk no Batocera | O launcher instala `pymunk>=7.3,<8` via pip em `/userdata/system/configs/suika-elika`; cria pip por `ensurepip` e, se necessário, pelo bootstrap PyPA. Só grava no espaço do usuário; a primeira instalação exige internet e pode depender de wheel/compilador compatível. |
| ADR-011 | X e sul como confirmação/soltura | SDL Controller reconhece A e X; joysticks genéricos usam apenas índice 0 como posição sul comum. Não presumir índice 2 como X, pois varia por dispositivo. |
| ADR-012 | Confirmação geométrica de fusão e superfícies rotacionadas em cache | A fusão combina contatos do Pymunk com uma busca local de círculos iguais dentro de 1,5 unidade, pois `post_solve` não é emitido para contatos adormecidos. A grade espacial restringe comparações a vizinhos. A silhueta opaca das frutas é ajustada ao raio circular do catálogo para alinhar contato visual e físico. O renderer evita ordenar a pilha para prever a mira, quantiza rotações filtradas em 24 passos e mantém até 128 superfícies em cache LRU limitado para reduzir transformações por quadro sem crescimento ilimitado de memória. |
| ADR-013 | APK Android TV baseado em SDL2 com receitas locais | Buildozer/python-for-android empacotam o mesmo jogo Pygame; receitas locais fixam CPython, Pygame CE 2.5.8 e Pymunk 7.3.1, desativando depuração remota opcional para manter API mínima 23. O manifesto oferece Leanback, não exige toque e inicia em paisagem. Dados usam `ANDROID_PRIVATE`; o APK inclui ARM64 e ARMv7. Construir não homologa joystick, áudio ou desempenho na TV física. |

## 9. Contratos implementados para BATALHA

`game/battle.py` coordena duas sessões e publica `BattleSnapshot` imutável com
dois snapshots, meta, estado final, vencedor (1/2 ou `None` em empate) e motivo.
Cada passo avança ambos antes de resolver: transbordamento/escape primeiro,
meta selecionada (1000, 2000 ou 5000) depois, empate quando ambos cumprem a mesma condição nesse passo.
Reutiliza os temporizadores de perigo do clássico. Pausa/conclusão congela ambos.

`input/battle.py` mantém dois `InputManager`, um por slot, sobre os adaptadores
de `NativeInputRegistry`. Não altera o dispositivo ativo para fazer cada poll:
consulta cada adaptador uma vez por quadro. A registry continua abrindo cada
conexão uma vez, preferindo SDL Controller e eliminando duplicidade de eventos
Controller/Joystick. A atribuição fica fixa durante batalha, pausa e resultado;
remover P1 nunca transforma P2 em P1. Na reconexão, um ID novo de mesma identidade
ocupa somente um slot ausente. Dois controles de mesmo GUID continuam separados.
Se ambos forem removidos e forem do mesmo modelo, não é possível distinguir as
unidades pelo GUID: os slots são recuperados na ordem de conexão.

`scenes/battle.py` enfileira bordas separadamente por jogador e consome cada uma
uma vez no passo elegível. `SceneManager` mantém o modo ativo ao abrir pausa e
opções, escolhe o destino correto de retomada/reinício e protege o início/revanche
com disponibilidade de dois controles. `MenuItem.enabled` e
`MenuSnapshot.disabled_indices` expõem opções desabilitadas ao renderer.

`App` mantém o acumulador fixo compartilhado, suspende ambos em desconexão/foco,
consome confirmação sem repassá-la ao gameplay e permite menus da batalha pelos
dois controles, selecionando uma fonte por quadro e renumerando as bordas da UI.
O teclado permanece apenas no fluxo de desenvolvimento do clássico.
`BattleRenderer` usa snapshots, geometria e viewport existentes; mundo e desenho
usam as mesmas dimensões. O fundo bruto tem prioridade na árvore de fontes;
o pacote usa a cópia preparada em `assets/backgrounds/battle.png`.

Atualize esta tabela com motivo e impactos quando uma decisão realmente mudar. Não registre uma arquitetura planejada como implementação já existente.

## 10. Entrada de desktop e diagnóstico de dispositivos

`AppConfig.allow_keyboard_fallback` é falso por padrão. Todos os launchers
compartilham `app.main(argv)`, que aceita `--desktop`. A opção registra o adaptador
de teclado em backend separado; um controle nativo conectado continua prioritário.
Ao remover o controle no clássico, o fallback desktop só retoma após confirmar,
consumindo esse aperto sem lançar. A batalha continua exclusivamente nativa.

`--p1-index` e `--p2-index` são fornecidos juntos. `App` resolve os índices de
abertura para instance IDs, seleciona P1 no clássico/menu e entrega a ordem
preferida a `BattleControls`. Índices indisponíveis impedem a inicialização com
erro visível. Depois de iniciar, os slots continuam usando IDs e identidades de
reconexão; não reinterpretar índices que mudaram durante a partida. Este é um
contrato explícito do jogo, sem alegação de herdar a ordem do EmulationStation.

`--debug` configura `AppConfig.debug_colliders`; os renderers desenham o círculo
físico e o retângulo envolvente das frutas ativas sem alterar a simulação.

`tools/check_controllers.py` é independente dos módulos de gameplay. Inicializa
apenas vídeo/eventos/joystick e a API Controller opcional, enumera via joystick,
coleta metadados e libera os dispositivos. Não cria janela nem inicia mixer.
`--headless` usa vídeo dummy sem substituir o backend nativo de joystick.


## 11. Seleção de meta e cadência de soltura

O menu BATALHA abre `battle_setup`, com exatamente 1000, 2000 e 5000 pontos.
A confirmação envia `target` à transição `battle`; `BattleSession.restart(target=...)`
valida e define a meta. Reiniciar, revanche e retomar preservam a escolha quando
não recebem uma nova meta. Snapshot, HUD e resultado usam a meta da sessão.
A seleção permite voltar ao título e acompanha hotplug, impedindo início sem dois
controles. A confirmação é consumida pelo menu, sem soltar fruta na nova rodada.

Hold usa 180 BPM (1/3 s de simulação) no clássico e na batalha. Apertos novos
continuam imediatos. `classic-v5` separa recordes devido à alteração de cadência;
o catálogo `classic-v4` permanece disponível como arquivo histórico.

## 12. Pacote Android TV

`buildozer.spec` define o app fullscreen em paisagem, o SDL2 bootstrap e ABIs
ARM64/ARMv7. `packaging/android/p4a-recipes/` fornece versões Android dos
componentes nativos; a compilação via Buildozer não instala as dependências de
desktop declaradas no `pyproject.toml`. O script `packaging/android/build.ps1`
executa o build Linux no container oficial do Buildozer e grava o APK em
`dist/android/`.

O manifesto declara as funcionalidades Leanback e touchscreen como opcionais e
acrescenta `LEANBACK_LAUNCHER` à atividade SDL. O ícone de loja, as camadas
adaptativas e o banner 16:9 vêm de `raw_assets/icons/android/`. Em runtime,
`ANDROID_PRIVATE` determina as pastas internas de configuração e dados; o app
não grava em armazenamento compartilhado.

O suporte de joystick depende de como o controle da TV é exposto pelo SDL do
Android. Testes de build e controles simulados não substituem a instalação e a
partida em um aparelho Android TV real.
