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
├── suika_elika/            # código do jogo
├── data/                   # regras classic-v2
└── assets/                 # imagens do jogo
```

O diretório completo termina em `.pygame`, como solicitado. O Batocera encontra
o arquivo `SuikaElika.pygame` que fica dentro dele; esse lançador chama
`main.py`. O build não é um executável compilado; apenas reúne os pontos de
entrada, o pacote Python e seus dados. Ele não baixa nem inclui Python, Pygame,
SDL ou Pymunk.

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

O sistema Batocera precisa oferecer um `python3` compatível que consiga importar
Pygame e Pymunk, junto das bibliotecas nativas exigidas por elas. O build não
torna essas dependências portáveis. Não copie wheels do Windows para Linux. A
combinação de versão, arquitetura e ABI deve ser verificada no aparelho:

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
