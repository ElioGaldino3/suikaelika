# Arquitetura de Suika Elika

**Revisão:** 0.1, 20/10/2026. **Estado:** contratos e limites propostos para implementação. Ainda não há runtime do jogo.

O produto e os parâmetros de gameplay estão em [PROJECT.md](PROJECT.md). Este documento organiza dependências e contratos para permitir implementação paralela. Não substitui nem duplica as tabelas de regras de `PROJECT.md`.

## 1. Decisões base

| Decisão | Motivo | Estado |
|---|---|---|
| Python + Pygame oficial | Requisito do produto e compatibilidade pesquisada | Definida como direção |
| Pymunk para física | Contatos circulares e empilhamento | Candidato; pacote no alvo pendente |
| Passo fixo de simulação, apresentação independente | Consistência e estabilidade | Contrato; parâmetros em PROJECT |
| Imagens procedurais inicialmente | Primeiro protótipo independente de assets externos | Definida |
| Uma sessão individual offline | Escopo do modo clássico | Definida |
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
| `InputFrame` | `move_x` e `move_y` normalizados, ajuste fino e bordas de `drop`, `confirm`, `cancel`, `pause`, `nav_up`, `nav_down`; sem referências SDL |
| `DomainEvent` | Tipo, passo de simulação, IDs relevantes, posição e payload tipado/copied; sem `Arbiter` |
| `FruitDefinition` | ID, nível, raio, massa, pontos de criação e chave visual |
| `FruitSnapshot` | ID, tipo, pose anterior/atual e estado visual de perigo; sem corpo mutável |
| `SessionSnapshot` | Pontos, recorde contextual, atual/próxima, frutas, estado de lançamento, perigo e estado da rodada |
| `PhysicsPort` | Criar/remover corpo (incluindo velocidade linear/angular inicial), avançar passo, consultar contatos, sobreposição e poses; exclusividade de mutação pelo mundo físico |
| `AudioPort` | Consumir eventos, ajustar ganhos, pausar e encerrar; implementação silenciosa equivalente |
| `PersistencePort` | Carregar/salvar modelos validados e comunicar falha de persistência |
| `SettingsData` / `ControllerProfileData` / `RecordData` / `StatisticsData` | Preferências de áudio, vídeo, acessibilidade e área segura; perfil por plataforma/GUID com bindings e calibração; recorde por modo e ruleset com duração; estatísticas acumuladas |
| `Scene` | Entrar/sair, receber ações, atualizar interface e desenhar; retorno de transição explícito |

`InputFrame` é um snapshot por quadro de entrada. Bordas para gameplay são enfileiradas com número de sequência e consumidas uma vez no primeiro passo elegível; nenhum subpasso repete uma soltura. Ações inválidas são descartadas segundo as regras do lançador, sem fila oculta para uma queda posterior. A navegação em menus usa `move_y` normalizado e gera `nav_up`/`nav_down` com limiar, histerese e repetição medidos pelo relógio da interface.

Eventos pertencem ao passo que os produziu. O `Renderer` recebe snapshots e eventos de apresentação; não modifica entidades. Uma UI que precisa de configuração envia um comando à aplicação. Não altera silenciosamente as regras da sessão ativa.

## 4. Propriedade de estado e ordem do loop

Somente `PhysicsWorld` altera corpos e formas. `MergeSystem` prepara transações aplicadas depois de `space.step()`. `GameSession` é dona do sorteio, da pontuação e das estatísticas; áudio e partículas nunca consomem seu RNG.

Ordem de cada passo: consumir comandos válidos → guardar poses anteriores → avançar física → confirmar fusões/remoções → atualizar lançador → avaliar perigo e escape → emitir snapshot/eventos. A decisão de derrota considera a coleção final de entidades daquele passo.

Pausa, foco perdido e desconexão congelam tempo de simulação, limpam entradas residuais e zeram o acumulador. Ao retomar, a confirmação é consumida pela UI e não vira soltura. O relógio visual de menus pode continuar.

Parâmetros de passo, sorteio, massa, pontos, raio e derrota pertencem ao ruleset. Perfis gráficos reduzem efeitos sem mudar a simulação. Alterações que impactem comparabilidade de recordes exigem revisar `ruleset_version`.

## 5. Fronteiras de módulos

| Caminho planejado | Responsabilidade |
|---|---|
| `suika_elika/contracts/` | Modelos imutáveis, enums e interfaces compartilhadas |
| `game/catalog.py`, `game/randomizer.py`, `data/rules/` | Catálogo e sequência |
| `game/physics.py` | Adaptação Pymunk e consultas |
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
| ADR-005 | Versões e recordes por ruleset | Ajustes de física não misturam silenciosamente resultados incomparáveis |

Atualize esta tabela com motivo e impactos quando uma decisão realmente mudar. Não registre uma arquitetura planejada como implementação já existente.
