# Validação local — BATALHA 1x1

Data: 20/10/2026. Implementação local; homologação física pendente.

## Entrega e decisões

- TODO reduzido ao escopo BATALHA e aos bloqueios reais; histórico completo em
  `docs/archive/TODO-classic.md`, sem apagar as evidências anteriores.
- BATALHA no menu, visível em cinza com menos de dois controles. Hotplug atualiza
  o estado. A checagem também protege transições diretas e revanche.
- Duas cestas físicas de 480×460 em metades da tela lógica 1280×720. Mesmos raios,
  pontos, seed e sequência de frutas; física, mira, entradas e placares separados.
- Primeiro a alcançar >=500 vence. Transbordamento/escape mantém os temporizadores
  existentes e concede a vitória ao outro. Ambas as sessões avançam antes de
  resolver o passo; transbordamento precede meta, resultados simultâneos empatam.
- Pausa, foco e remoção de qualquer controle congelam ambos; confirmação de
  retomada não solta fruta. Jogador restante pode voltar ao menu ao desconectar.
- Ambos operam menus da batalha; resultado mostra vencedor/motivo/placares e
  oferece revanche. Batalha não grava recordes/estatísticas do clássico.
- `raw_assets/battle_background.png` é preservado. `assets/backgrounds/battle.png`
  é a cópia 1280×720, incluída no pacote. Prévia de tela dividida e menu conferidas.

## Pesquisa de múltiplos controles

Context7 consultado com `resolve-library-id` para Pygame e duas consultas em
`/pygame/pygame`: múltiplos joysticks/hotplug e SDL Controller/mapeamento.

A [documentação oficial de joystick](https://www.pygame.org/docs/ref/joystick.html)
permite múltiplos objetos, um por dispositivo. O índice de abertura é transitório;
`get_instance_id()` identifica a conexão. Eventos ADDED usam `device_index`,
REMOVED usam `instance_id`; a fila de eventos deve ser processada regularmente.
A [API SDL Controller](https://www.pygame.org/docs/ref/sdl2_controller.html)
padroniza eixos/botões dos dispositivos mapeados. A registry já existente prefere
essa API e evita abrir dois streams para os eventos Controller/Joystick do mesmo pad.

O novo `BattleControls` reutiliza esses adaptadores, com um InputManager por
jogador e um poll por dispositivo/quadro. GUID/nome serve somente para recuperar
slot removido. Dois pads iguais conectados têm instance IDs distintos. Se ambos
forem removidos, unidades do mesmo modelo são indistinguíveis pelo GUID e os slots
são recuperados na ordem de conexão. Joystick genérico requer bindings explícitos,
como no adaptador existente; o teste misto fornece esses bindings, sem presumir
um mapeamento universal de botões. Teclado não habilita batalha.

## Ambiente e comandos

Windows, Python 3.14.7, **pygame-ce 2.5.8 / SDL 2.32.10**, Pymunk 7.3.1.
O ambiente existente não usa o pacote Pygame oficial declarado no pyproject.
Não houve troca de dependências neste lote; testes nesse ambiente não homologam
o Pygame oficial nem o runtime Batocera.

Na raiz, PowerShell, com `SDL_VIDEODRIVER=dummy` e `SDL_AUDIODRIVER=dummy`:

| Comando | Resultado |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | 232 testes passaram |
| `.\.venv\Scripts\python.exe -m ruff check .` | Aprovado |
| `.\.venv\Scripts\python.exe -m mypy` | Aprovado, 46 fontes |
| `.\.venv\Scripts\python.exe tools/build_batocera.py` | Pacote gerado em `dist/SuikaElika.pygame/` |
| `.\.venv\Scripts\python.exe skills/todo-orchestrator/scripts/todo_graph.py validate --todo TODO.md` | Grafo revisado e validado com cinco tarefas |
| `git diff --check` | Sem erros após a revisão |

O jogo empacotado foi iniciado a partir de `dist/SuikaElika.pygame/` usando
`App(AppConfig(fullscreen=False)).run(frame_limit=3)`, com drivers dummy: importou
o código dessa pasta e encerrou com código 0. O SHA-256 do fundo no pacote é
igual ao arquivo preparado: `b3078b19730cd1b79421d87feeeca91b96aa2d125bdb33d7fb00a4724a9983ef`.

Os 26 testes novos cobrem isolamento das duas entradas e física, fusão real
atravessando 500 pontos, >=500 e congelamento do resultado, transbordamento real
dos dois lados, precedência/empate, pausa/reinício, gate/hotplug, dois controles
iguais/diferentes, remoção de P1/P2, consumo de confirmação, foco, menus por P2,
saída pelo sobrevivente, duas APIs nativas com eventos duplicados, fundo bruto e
preparado, viewport em três resoluções e o loop real de App/Pygame com pads
simulados e drivers dummy (entrar, jogar, desenhar, pausar, retomar e encerrar).

## Pendências externas

SE-038: dois controles físicos, desempenho com ambas as cestas cheias, reconexão
real, áudio HDMI e execução no Batocera. SE-039 mantém as pendências anteriores de
runtime/dependências, balanceamento, homologação e licença para distribuição.
Nenhum teste dummy comprova esses pontos. `raw_assets/jogo.png`, que já estava
sem rastreamento antes do lote, permanece fora do commit.
