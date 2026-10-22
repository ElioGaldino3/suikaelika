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
python main.py --desktop
```

Por padrão, o jogo abre em tela cheia. Para abrir em uma janela de 1600×900,
use `python main.py --window` (também pode combinar com `--desktop`).

### Linux

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python main.py --desktop
```

Não é preciso gerar um `.exe`: `main.py` inicia o jogo pelo Python. Se não
iniciar com `--desktop` e não houver joystick, o teclado funciona como fallback
de desenvolvimento. Sem essa opção, somente controles nativos são aceitos. Os
controles estão em [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Para visualizar os colisores durante a partida, execute `python main.py --debug`.
O círculo verde mostra a hitbox física; o retângulo amarelo mostra seus limites.
Sem joystick no computador, combine com `--desktop`.

Para soltar frutas, aperte o botão sul/A ou o botão X do controle (ou Espaço/Enter
com `--desktop`). Novos apertos não têm cooldown artificial. Segurar repete a
**180 BPM**, uma fruta a cada **333,33 ms**, enquanto a boca da cesta estiver livre.
Soltar interrompe a repetição; após pausar ou retomar, aperte novamente para lançar.

Para conferir quantos controles o Pygame vê pelo terminal:

```powershell
python tools/check_controllers.py
```

O relatório mostra quantidade, nomes, índices, instance IDs, GUIDs e mapeamento
SDL. Teclado comum não entra nessa contagem; pads virtuais podem aparecer.
Use `--format json` para JSON ou `--headless` se executar por SSH sem display.
Para escolher explicitamente os controles de cada jogador, use os índices do
relatório (começam em zero):

```powershell
python main.py --p1-index 1 --p2-index 0
```

Os índices são da enumeração atual e podem mudar ao reconectar. O jogo não
presume que o lançador Pygame herdou a ordem P1/P2 do EmulationStation.

## BATALHA 1x1 local

Conecte dois controles e escolha **BATALHA** no menu principal. A opção fica
cinza com menos de dois controles e muda automaticamente ao conectar/remover.
O primeiro controle é o jogador 1, à esquerda; o segundo é o jogador 2, à direita.

Ao escolher BATALHA, selecione a meta: **1000, 2000 ou 5000 pontos**.
Cada jogador tem uma cesta menor, sua mira e seu placar. O primeiro a atingir
a meta vence. A revanche mantém o objetivo escolhido. Transbordar a cesta dá
a vitória ao adversário, com a mesma
tolerância de perigo do clássico. Se os dois atingirem a meta ou perderem no
mesmo passo de simulação, há empate. Transbordamento tem prioridade sobre pontos
obtidos no mesmo passo. Os dois recebem a mesma sequência de frutas.

Cada controle move e solta apenas na sua cesta; **Start** de qualquer jogador
pausa ambos. Ambos podem operar os menus de pausa, resultado e revanche.
Remover qualquer controle congela as duas cestas até reconectar e confirmar;
o botão de voltar do controle restante permite retornar ao menu. A confirmação
de retomada é consumida sem soltar fruta. Controles com mapeamento SDL aceitam
botão sul/A e X para confirmar/soltar. Em joysticks genéricos, o índice 0
(posição sul mais comum) confirma/solta; o índice 2 não é presumido como X
porque pode ser o botão norte em alguns controles.
O teclado de desenvolvimento não conta como segundo controle.

O fundo vem de `raw_assets/battle_background.png`. A cópia preparada em
`assets/backgrounds/battle.png` segue no pacote Batocera. Para regenerar as artes,
execute `python tools/process_art_assets.py`.

Testes locais com dispositivos simulados não substituem a homologação de dois
controles físicos no Batocera. Evidências em [docs/validation/battle.md](docs/validation/battle.md).

## Build para o sistema Pygame do Batocera

O build monta a pasta `SuikaElika.pygame`. Dentro dela, `main.py` inicia o jogo
e o arquivo `SuikaElika.pygame` é a entrada reconhecida pelo sistema Batocera:

```text
dist/SuikaElika.pygame/
├── main.py
├── SuikaElika.pygame
├── bootstrap.py
├── suika_elika/
├── data/
├── assets/
└── README-BATOCERA.txt
```

Gere o pacote na raiz do projeto:

```powershell
python tools/build_batocera.py
```

Para gerar também um tarball compacto para anexar a uma Release do GitHub:

```powershell
python tools/build_batocera.py --archive
```

O arquivo fica em `dist/SuikaElika-Batocera.tar.gz`. Enviar uma tag `v*` ao
GitHub também aciona `.github/workflows/batocera-release.yml`, que publica o
arquivo como anexo da Release. No Batocera, use a URL `releases/latest/download`
descrita em [docs/BATOCERA.md](docs/BATOCERA.md); ela fica disponível depois da
primeira Release.

O resultado pronto para copiar fica em `dist/SuikaElika.pygame/`. Copie a pasta
inteira para `/userdata/roms/pygame/`, para que o destino seja
`/userdata/roms/pygame/SuikaElika.pygame/`. No Windows, transfira pelo
compartilhamento de rede do Batocera, normalmente
`\\BATOCERA\share\roms\pygame\` (ou substitua `BATOCERA` pelo IP do aparelho).
Depois, atualize a lista de jogos no EmulationStation e inicie **Pygame →
SuikaElika**.

### Atualizar diretamente com GitHub

Também é possível clonar o repositório na pasta de ROMs do Batocera. O arquivo
`main.pygame` na raiz do projeto inicia o jogo usando o bootstrap de Pymunk
existente. No Batocera, clone o repositório em uma pasta própria (substitua a
URL pelo endereço do repositório no GitHub):

```sh
cd /userdata/roms/pygame
git clone https://github.com/USUARIO/REPOSITORIO.git SuikaElika.pygame
```

Troque `USUARIO/REPOSITORIO` pelo caminho do projeto no GitHub.

Após atualizar a lista de jogos, inicie `main.pygame` em **Pygame**. Para
atualizar o jogo depois, use:

```sh
git -C /userdata/roms/pygame/SuikaElika.pygame pull --ff-only
```

Esse fluxo precisa de acesso à rede no Batocera. O pacote produzido pelo build
continua disponível para instalações sem checkout Git.

O arquivo `SuikaElika.pygame` dentro da pasta é o lançador do sistema; `main.py`
é a entrada Python principal. Nenhum deles é `.exe` ou binário independente:
o aparelho ainda precisa de uma versão compatível de Python e Pygame/SDL. Na
primeira execução, o launcher instala Pymunk via pip em `/userdata` (internet
necessária); pip é instalado automaticamente se o Python não o fornecer.
Confira os passos e limites em [docs/BATOCERA.md](docs/BATOCERA.md).

## Arte na lista de jogos

Pode-se associar uma imagem no `gamelist.xml` do sistema Pygame. Exemplo para a
instalação acima:

```xml
<game>
  <path>./SuikaElika.pygame/SuikaElika.pygame</path>
  <name>Suika Elika</name>
  <image>./images/SuikaElika.png</image>
  <desc>Jogo de queda e fusão de frutas.</desc>
</game>
```

Coloque a arte em `/userdata/roms/pygame/images/SuikaElika.png`; o tema do
EmulationStation precisa exibir imagens da lista.

## Android TV

O jogo também pode ser empacotado em APK para Android TV. No Windows, com o
Docker Desktop aberto, gere o pacote com:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/android/build.ps1
```

O APK fica em `dist/android/`. Copie-o para a TV e instale-o por sideload. Os
detalhes de build, ícone Android e instalação estão em
[docs/ANDROID-TV.md](docs/ANDROID-TV.md). A homologação de controles físicos e
desempenho depende da TV real.

## Documentação

- [Build e instalação no Batocera](docs/BATOCERA.md)
- [Build e instalação no Android TV](docs/ANDROID-TV.md)
- [Requisitos e regras do jogo](docs/PROJECT.md)
- [Arquitetura](docs/ARCHITECTURE.md)
- [Desenvolvimento e comandos de qualidade](docs/DEVELOPMENT.md)
- [Backlog e estado das tarefas](TODO.md)
