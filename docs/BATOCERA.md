# Executar no Batocera

Este pacote contém dois launchers de origem: a categoria **Pygame** do
EmulationStation e a alternativa **Ports**. Eles iniciam o mesmo código Python
instalado em `userdata`. Não há build de dependências ou pacote universal nesta
etapa. A instalação final depende de confirmar Python, Pygame, SDL, Pymunk,
arquitetura e ABI no Batocera do aparelho (SE-004/SE-024); ainda não foi
homologada no Batocera 43 nem em joystick físico.

Batocera documenta `.pygame` em `/userdata/roms/pygame` e `.sh` em
`/userdata/roms/ports`. A documentação de Ports orienta deixar dados do jogo em
`roms/ports/.data` e manter o shell script visível na pasta `ports`.
[Sistema Pygame](https://wiki.batocera.org/systems:pygame), [sistema Ports e
formato `.sh`](https://wiki.batocera.org/systems:ports). O launcher Pygame
observado no código-fonte atual do Batocera executa `pygame` com o caminho do
arquivo ROM; esse código-fonte atual não confirma o comportamento exato da
versão 43.
[Launcher Pygame no código-fonte do Batocera](https://github.com/batocera-linux/batocera.linux/blob/master/python-src/batocera-launch/batocera_launch/emulators/pygame.py).

## Pré-requisitos

- Rodar a coleta local do alvo com o Python planejado para iniciar o jogo:
  `python3 tools/diagnostics.py --format json`.
- Pygame/SDL disponíveis para a categoria Pygame; para Ports, `python3` precisa
  importar Pygame.
- Pymunk e suas bibliotecas nativas precisam importar no mesmo interpretador.
  A verificação de versão/importação e a escolha de dependências pertencem à
  SE-024. Não copie wheels Windows para Linux e não instale pacotes globais no
  launcher.
- Os comandos abaixo pressupõem que o diretório do projeto está acessível no
  Batocera. Substitua `PROJECT_ROOT` pelo caminho real do checkout ou da cópia.

## Categoria Pygame

O arquivo `.pygame` inclui seu próprio caminho de instalação em `sys.path`. O
pacote Python e os dados de regras ficam ao lado dele; o catálogo localiza
`data/rules/classic-v1.json` a partir do próprio módulo.

```sh
PROJECT_ROOT="/userdata/system/suika-elika-source"
INSTALL_DIR="/userdata/roms/pygame/SuikaElika"
mkdir -p "$INSTALL_DIR"
cp -R "$PROJECT_ROOT/suika_elika" "$PROJECT_ROOT/data" \
  "$PROJECT_ROOT/assets" "$INSTALL_DIR/"
cp "$PROJECT_ROOT/packaging/batocera/pygame/SuikaElika.pygame" "$INSTALL_DIR/"
```

Depois atualize a lista de jogos no EmulationStation e abra **Pygame →
SuikaElika**. O formato da categoria é `.pygame`; a chamada e a inicialização
gráfica ainda precisam ser observadas no aparelho real.

## Alternativa Ports

Ports usa o mesmo bootstrap `.pygame` sob uma pasta oculta de dados. O launcher
`Suika Elika.sh` resolve seu próprio diretório, cita caminhos com espaços e
substitui o processo pelo `python3` (ou pelo comando definido em
`SUIKA_ELIKA_PYTHON`). Ele não altera `SDL_*`, `DISPLAY` ou outras variáveis SDL
do sistema.

```sh
PROJECT_ROOT="/userdata/system/suika-elika-source"
GAME_DIR="/userdata/roms/ports/.data/SuikaElika"
mkdir -p "$GAME_DIR"
cp -R "$PROJECT_ROOT/suika_elika" "$PROJECT_ROOT/data" \
  "$PROJECT_ROOT/assets" "$GAME_DIR/"
cp "$PROJECT_ROOT/packaging/batocera/pygame/SuikaElika.pygame" "$GAME_DIR/"
cp "$PROJECT_ROOT/packaging/batocera/ports/Suika Elika.sh" \
  "/userdata/roms/ports/Suika Elika.sh"
chmod +x "/userdata/roms/ports/Suika Elika.sh"
```

Atualize a lista e abra **Ports → Suika Elika**. O conteúdo em `.data` fica
oculto da lista de scripts conforme a organização documentada para Ports.

## Seleção de controle

Na inicialização, o jogo seleciona o primeiro controle nativo enumerado como
jogador 1. Enquanto ele estiver ativo, teclado emulado não gera uma segunda
fonte de ações. Se nenhum controle nativo for encontrado, o jogo habilita o
teclado como fallback de desenvolvimento. A ordem dos dispositivos e esse
fallback ainda precisam ser conferidos no Batocera 43 real.

Se o controle ativo for removido durante a partida, a sessão pausa e limpa as
entradas pendentes. O jogo aguarda reconectar um dispositivo com a mesma
identidade GUID/nome e exige uma confirmação antes de continuar; essa
confirmação não solta uma fruta. Um dispositivo diferente não substitui o
jogador 1 automaticamente. A API ou o mapeamento de joystick oferecido pelo
Batocera não foi homologado neste projeto.

## Dados persistentes e ambiente

O jogo grava configuração em `/userdata/system/configs/suika-elika` e dados de
partida em `/userdata/saves/suika-elika`, separados do diretório instalado. Os
launchers preservam as variáveis herdadas do EmulationStation; não defina
`SDL_VIDEODRIVER`, `SDL_AUDIODRIVER`, `SDL_GAMECONTROLLERCONFIG`, `DISPLAY` ou
`LD_LIBRARY_PATH` sem uma necessidade observada no equipamento.

## Diagnóstico no aparelho

Registre o relatório integral de `python3 tools/diagnostics.py --format json`.
Ele coleta metadados, mas não importa SDL nem verifica display, joystick, áudio
ou física. Em caso de falha, registre se abriu a tela, controle e saída de
áudio, logs do EmulationStation e resultado de importar Pygame/Pymunk. Esses
resultados pertencem à validação do Batocera e não podem ser inferidos pelos
testes Windows ou headless.
