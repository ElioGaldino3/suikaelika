# Build e instalação no Batocera

Este projeto usa o sistema **Pygame** do Batocera. A documentação oficial
identifica `/userdata/roms/pygame` como a pasta de jogos e `.pygame` como a
extensão aceita ([sistema Pygame](https://wiki.batocera.org/systems:pygame)). O
código atual do lançador do Batocera usa a pasta do arquivo `.pygame` como
diretório de execução e chama `pygame <arquivo-rom>`
([lançador atual](https://github.com/batocera-linux/batocera.linux/blob/master/python-src/batocera-launch/batocera_launch/emulators/pygame.py)).
O wiki observa que sua página Pygame precisa de atualização; confirme o
comportamento na versão instalada no aparelho.

## O que o build gera

Na raiz do checkout, rode:

```powershell
python tools/build_batocera.py
```

O script monta a pasta `dist/SuikaElika.pygame/`, removendo apenas a saída
anterior com esse mesmo nome dentro de `dist/`:

```text
dist/SuikaElika.pygame/
├── main.py                 # entrada principal que inicia o jogo
├── SuikaElika.pygame       # arquivo ROM reconhecido pelo sistema Batocera
├── README-BATOCERA.txt
├── bootstrap.py            # instalação inicial de Pymunk no espaço do usuário
├── suika_elika/            # código do jogo
├── data/                   # regras classic-v4 e versões anteriores
└── assets/                 # imagens do jogo
```

O diretório completo termina em `.pygame`, como solicitado. O Batocera encontra
o arquivo `SuikaElika.pygame` que fica dentro dele; esse lançador chama
`main.py`. O build não é um executável compilado; reúne os pontos de entrada, o
pacote Python e seus dados. Ele não baixa nem inclui Python, Pygame ou SDL.

## Instalar e atualizar um checkout do GitHub

Para manter uma cópia do repositório no Batocera e atualizá-la com Git, clone-o
em uma pasta própria dentro de `/userdata/roms/pygame` (substitua a URL pelo
endereço do repositório):

```sh
cd /userdata/roms/pygame
git clone https://github.com/USUARIO/REPOSITORIO.git SuikaElika.pygame
```

Troque `USUARIO/REPOSITORIO` pelo caminho do projeto no GitHub.

O arquivo `main.pygame` na raiz do checkout é a entrada do EmulationStation.
Ele reutiliza `packaging/batocera/pygame/main.py` e `bootstrap.py`, mantendo o
jogo e seus assets no diretório do repositório. Atualize a lista de jogos no
EmulationStation e inicie **Pygame → main**. Para receber mudanças publicadas
no GitHub:

```sh
git -C /userdata/roms/pygame/SuikaElika.pygame pull --ff-only
```

O primeiro lançamento ainda exige internet para instalar Pymunk caso ele não
esteja disponível. Esse método mantém `.git` no aparelho; para uma cópia pronta
sem histórico Git, use o build descrito acima.

## Copiar para o Batocera

Copie a pasta **inteira** `dist/SuikaElika.pygame` para `/userdata/roms/pygame/`.
No Windows, use o compartilhamento de rede, normalmente
`\\BATOCERA\share\roms\pygame\`; substitua `BATOCERA` pelo nome/IP do aparelho
se necessário. No aparelho, a estrutura final deve ser:

```text
/userdata/roms/pygame/SuikaElika.pygame/
├── main.py
├── SuikaElika.pygame
├── README-BATOCERA.txt
├── bootstrap.py
├── suika_elika/
├── data/
└── assets/
```

Atualize a lista de jogos pelo menu do EmulationStation (**Main Menu → Game
Settings → Update Gamelists**) e inicie **Pygame → SuikaElika**.

## Arte opcional no EmulationStation

Guarde a imagem, por exemplo, em
`/userdata/roms/pygame/images/SuikaElika.png` e associe-a à entrada em
`/userdata/roms/pygame/gamelist.xml`:

```xml
<game>
  <path>./SuikaElika.pygame/SuikaElika.pygame</path>
  <name>Suika Elika</name>
  <image>./images/SuikaElika.png</image>
  <desc>Jogo de queda e fusão de frutas.</desc>
</game>
```

O campo `<image>` é um metadado usado pelos temas do EmulationStation
([exemplo de gamelist do Batocera](https://wiki.batocera.org/create_pacman_package)).
O tema ativo precisa ter uma área para exibir a imagem.

## Dependências e validação

### Teclado e ordem dos controles

O [Batocera não considera o teclado comum um controle para gerar configurações](https://wiki.batocera.org/supported_controllers#keyboard).
Pygame também separa eventos de teclado da enumeração `pygame.joystick`.
Suika Elika ignora teclado por padrão; `--desktop` é uma autorização explícita
de fallback para testes de computador. Não use essa opção no lançador Batocera
quando quiser somente controles nativos. Pad-to-keyboard não é necessário para
este jogo e suas teclas geradas são ignoradas no modo padrão.

O menu [Controller & Bluetooth Settings](https://wiki.batocera.org/menu_tree#controller_and_bluetooth_settings)
permite definir a ordem dos jogadores no EmulationStation, mas não se deve
confundir essa ordem com a enumeração SDL do processo do jogo. Foram consultados
o [gerador Pygame do Batocera 42](https://github.com/batocera-linux/batocera.linux/blob/batocera-42/package/batocera/core/batocera-configgen/configgen/configgen/generators/pygame/pygameGenerator.py)
e o [lançador atual](https://github.com/batocera-linux/batocera.linux/blob/master/python-src/batocera-launch/batocera_launch/emulators/pygame.py):
ambos chamam `pygame <rom>` sem argumentos P1/P2 específicos do Suika. Não há
integração automática comprovada com a seleção da interface do aparelho.

Copie `tools/check_controllers.py` para o aparelho e execute:

```sh
python3 tools/check_controllers.py --headless
```

Os índices começam em zero. Para fixar a atribuição no jogo, o lançador Python
do pacote (`main.py`) pode chamar, por exemplo:

```python
raise SystemExit(main(["--p1-index", "1", "--p2-index", "0"]))
```

Use os índices vistos no aparelho, nunca os números do relatório Windows. Eles
podem mudar após desconectar/reiniciar; são resolvidos para instance IDs ao abrir
o jogo. Durante uma batalha, a reconexão preserva o lugar do jogador restante.
Sem seleção explícita, o jogo usa os dois primeiros dispositivos abertos.
Não filtrar controles pelo nome: um encoder arcade convertido pelo
[keyboardToPads](https://wiki.batocera.org/diy-arcade-controls#using_keyboardtopads_to_convert_keyboard_controllers_to_gamepads_controllers)
é um joystick virtual legítimo para SDL e pode contar como controle.

### Runtime do aparelho

O sistema Batocera precisa oferecer `python3` e Pygame/SDL compatíveis. Na
primeira execução, o pacote verifica o Pymunk e instala `pymunk>=7.3,<8` com pip
em `/userdata/system/configs/suika-elika/python-packages`. Se `pip` não existir,
tenta `ensurepip`; se o Python do sistema não o oferecer, baixa o instalador
oficial do PyPA e instala pip no espaço de usuário. A instalação exige internet
na primeira execução; depois o Pymunk fica no armazenamento persistente para
execuções offline. O instalador não altera os diretórios do Python do sistema.

O primeiro lançamento precisa de espaço gravável em `/userdata` e acesso ao
PyPI. A disponibilidade de uma wheel Linux compatível depende da versão do
Python e da arquitetura; caso contrário, o pip poderá tentar compilar Pymunk e
precisará de compilador e dependências nativas, que normalmente não fazem parte
do runtime do Batocera. Não copie wheels do Windows para Linux. O diagnóstico
abaixo ajuda a identificar a combinação do aparelho:

```sh
python3 tools/diagnostics.py --format json
```

Rode o diagnóstico no checkout do projeto, se ele estiver disponível no
aparelho. Ele registra metadados e disponibilidade das bibliotecas sem abrir
janela, testar áudio ou acessar o joystick. A inicialização gráfica, a física,
os controles (incluindo joystick físico) e o áudio ainda precisam ser conferidos
no Batocera real. Testes locais não comprovam compatibilidade com o aparelho.

O jogo salva opções em `/userdata/system/configs/suika-elika` e dados da partida
em `/userdata/saves/suika-elika`, separados dos arquivos de instalação.
