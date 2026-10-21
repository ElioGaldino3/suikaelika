# Suika Elika

Jogo de queda e fusão de frutas feito em Python + Pygame, com suporte a joystick.
O jogo ajusta a apresentação à resolução atual do monitor ou da TV.

## Rodar no computador

É necessário Python 3.10 ou superior. Na pasta raiz do projeto:

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python main.py
```

### Linux

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python main.py
```

Não é preciso gerar um `.exe`: `main.py` inicia o jogo pelo Python. Se não
houver joystick, o teclado funciona como fallback de desenvolvimento. Os
controles estão em [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Build para o sistema Pygame do Batocera

O arquivo `.pygame` é o script Python de entrada do jogo. O build monta uma
pasta `SuikaElika` com esse script e os arquivos que ele importa:

```text
dist/SuikaElika/
├── SuikaElika.pygame
├── suika_elika/
├── data/
├── assets/
└── README-BATOCERA.txt
```

Gere o pacote na raiz do projeto:

```powershell
python tools/build_batocera.py
```

O resultado pronto para copiar fica em `dist/SuikaElika/`. Copie essa pasta
inteira para `/userdata/roms/pygame/`, para que o destino seja
`/userdata/roms/pygame/SuikaElika/`. Por exemplo, no Windows, a pasta pode ser
copiada pelo compartilhamento de rede do Batocera, normalmente
`\\BATOCERA\share\roms\pygame\` (ou substitua `BATOCERA` pelo IP do aparelho).
Depois, atualize a lista de jogos no EmulationStation e inicie **Pygame →
SuikaElika**.

`SuikaElika.pygame` é um arquivo dentro da pasta do jogo, não o nome da pasta.
Não é `.exe` nem binário independente: o aparelho ainda precisa de uma versão
compatível de Python, Pygame/SDL e Pymunk. O build organiza os arquivos do jogo,
mas não compila nem inclui essas bibliotecas do sistema. Confira os passos e
limites de instalação em [docs/BATOCERA.md](docs/BATOCERA.md).

## Arte na lista de jogos

Pode-se associar uma imagem no `gamelist.xml` do sistema Pygame. Exemplo para a
instalação acima:

```xml
<game>
  <path>./SuikaElika/SuikaElika.pygame</path>
  <name>Suika Elika</name>
  <image>./images/SuikaElika.png</image>
  <desc>Jogo de queda e fusão de frutas.</desc>
</game>
```

Coloque a arte em `/userdata/roms/pygame/images/SuikaElika.png`; o tema do
EmulationStation precisa exibir imagens da lista.

## Documentação

- [Build e instalação no Batocera](docs/BATOCERA.md)
- [Requisitos e regras do jogo](docs/PROJECT.md)
- [Arquitetura](docs/ARCHITECTURE.md)
- [Desenvolvimento e comandos de qualidade](docs/DEVELOPMENT.md)
- [Backlog e estado das tarefas](TODO.md)
