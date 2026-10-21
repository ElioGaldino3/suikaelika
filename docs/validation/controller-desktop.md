# Diagnóstico de controles e desktop explícito

Data: 20/10/2026. Lote SE-040, após a implementação local da batalha.

## Pesquisa e decisão

Context7: `resolve-library-id` para Pygame e Batocera, seguido de consultas em
`/pygame/pygame`, `/websites/wiki_batocera` e `/batocera-linux/batocera.linux`.
Foram consultadas também as fontes oficiais abaixo:

- [Pygame joystick](https://www.pygame.org/docs/ref/joystick.html): enumeração de
  joysticks separada do teclado, abertura por índice e conexão por instance ID.
- [Batocera — teclado](https://wiki.batocera.org/supported_controllers#keyboard):
  teclado comum não é tratado como controle pelo gerador de configurações.
- [Batocera — menu de controles](https://wiki.batocera.org/menu_tree#controller_and_bluetooth_settings):
  permite definir ordem de jogadores na interface.
- [PygameGenerator no Batocera 42](https://github.com/batocera-linux/batocera.linux/blob/batocera-42/package/batocera/core/batocera-configgen/configgen/configgen/generators/pygame/pygameGenerator.py)
  e [lançador atual](https://github.com/batocera-linux/batocera.linux/blob/master/python-src/batocera-launch/batocera_launch/emulators/pygame.py):
  chamam `pygame <rom>` sem argumentos P1/P2 específicos do jogo. A integração
  automática da ordem do EmulationStation não é presumida.
- [keyboardToPads](https://wiki.batocera.org/diy-arcade-controls#using_keyboardtopads_to_convert_keyboard_controllers_to_gamepads_controllers):
  encoders de teclado podem virar joysticks virtuais legítimos. Não rejeitar
  dispositivos pelo nome nem confundir esses pads com eventos de teclado comum.

O jogo já contava apenas dispositivos nativos para habilitar BATALHA. A mudança
torna explícita a autorização do teclado: desabilitado por padrão, fallback
somente com `--desktop`, inclusive em Windows. Controles nativos têm prioridade.
No clássico, remover o controle permite confirmar a retomada pelo teclado apenas
quando o fallback foi autorizado. Batalha continua exigindo dois dispositivos
de joystick e usa exclusivamente suas entradas.

`--p1-index` e `--p2-index` permitem ordenar os dispositivos nativos usando o
diagnóstico, inclusive se houver um terceiro controle conectado. Erros de seleção
são visíveis no terminal. A resolução para instance IDs acontece na inicialização;
reconexão da batalha mantém slots, e não reinterpreta índices transitórios.

## Verificações executadas

Ambiente local existente: Windows, Python 3.14.7, pygame-ce 2.5.8 / SDL 2.32.10,
Pymunk 7.3.1. Não foi instalado/trocado nenhum pacote neste lote.

| Comando/verificação | Resultado |
|---|---|
| `.\.venv\Scripts\python.exe tools/check_controllers.py` | Quantidade 0; teclado não contado; sem erros |
| Mesmo diagnóstico com `--format json` | JSON válido: `joystick_count=0`, `opened_count=0`, `keyboard_counted=false`, `errors=[]` |
| Mesmo diagnóstico com `--headless` | Executado com vídeo dummy, quantidade 0; sem janela de jogo/áudio |
| `.\.venv\Scripts\python.exe -m pytest -q` | 251 testes passaram |
| `.\.venv\Scripts\python.exe -m ruff check .` | Aprovado |
| `.\.venv\Scripts\python.exe -m mypy` | Aprovado, 46 fontes de runtime |
| `main.py --help`, `python -m suika_elika --help` e help do pacote | Flags documentadas e reconhecidas |
| `.\.venv\Scripts\python.exe tools/build_batocera.py` | Pacote atualizado em `dist/SuikaElika.pygame/` |
| App do pacote com desktop e `frame_limit=2`, drivers dummy | Encerrou com código 0 |
| Validador TODO e `git diff --check` | Aprovados |

Os 19 testes novos cobrem enumeração de dois pads iguais, metadados, API SDL
opcional, falha parcial e liberação dos dispositivos; CLI e argumentos inválidos;
0/1/2 controles com/sem desktop; evento de teclado real ignorado sem autorização
e aceito com desktop; contagem/gate da batalha; ordenação explícita com três pads;
índice ausente; reconexão e fallback sem soltura residual. Os testes de runtime
usam drivers dummy e pads simulados.

## Limitações preservadas

Não foram homologados controles físicos, Pygame oficial, integração de ordem na
versão instalada do EmulationStation, áudio HDMI ou execução no Batocera.
Índices do Windows não identificam dispositivos no Batocera. Eles podem mudar
entre enumerações e reinícios. O diagnóstico mostra pads físicos e virtuais que
SDL expõe, sem alegar distinguir sua origem elétrica.

O script é independente e pode ser copiado para o aparelho; `tools/` não faz
parte do pacote de jogo padrão. O arquivo preexistente `raw_assets/jogo.png`
permanece fora do commit.
