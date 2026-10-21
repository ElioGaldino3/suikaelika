# Suika Elika

Jogo de queda e fusão de frutas feito em Python + Pygame, com controle por
joystick e destino principal no Batocera. O jogo abre em tela cheia na
resolução atual do monitor/TV; o conteúdo mantém proporção e se ajusta à tela.

## Rodar no computador

É necessário Python 3.10 ou superior. Clone/extraia o projeto e rode os comandos
na pasta raiz, onde estão `main.py`, `data/` e `assets/`.

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

O primeiro comando de instalação baixa Pygame e Pymunk no ambiente virtual do
projeto. Não é necessário gerar um `.exe`: `main.py` inicia o jogo pelo Python.
Para sair, use a opção de saída do menu ou feche a janela. Se não houver
joystick, o teclado funciona como fallback de desenvolvimento; as instruções
de controles estão em [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Instalar no Batocera

O pacote atual é código Python com seus dados, imagens e um script de
inicialização. Não é um `.exe` nem um binário autocontido. O Batocera precisa
ter um `python3` com Pygame/Pymunk e dependências nativas compatíveis com a sua
versão e arquitetura. **Essa combinação ainda precisa ser validada no aparelho
alvo**; não copie pacotes Windows para o Batocera.

A organização recomendada para o EmulationStation é a categoria **Ports**:

```text
/userdata/roms/ports/
├── Suika Elika.sh
├── images/
│   └── suika-elika.png        # opcional: arte da lista
└── .data/
    └── SuikaElika/
        ├── SuikaElika.pygame
        ├── suika_elika/
        ├── data/
        └── assets/
```

No Batocera, `/userdata` normalmente é compartilhado pela rede como `share`.
Copie `suika_elika/`, `data/`, `assets/` e os dois launchers de
`packaging/batocera/` para a estrutura acima. Marque o launcher como executável
(`chmod +x "/userdata/roms/ports/Suika Elika.sh"`) e atualize a lista de jogos
em **Main Menu → Game Settings → Update Gamelists**. Depois abra **Ports →
Suika Elika**.

Também existe a categoria Pygame. Ela usa uma cópia do pacote em
`/userdata/roms/pygame/SuikaElika/` e o arquivo `.pygame`; os passos completos e
os comandos de cópia estão em [docs/BATOCERA.md](docs/BATOCERA.md).

### Arte na lista de jogos

Sim, dá para associar uma imagem à entrada do jogo no EmulationStation. Coloque
uma imagem em `roms/ports/images/suika-elika.png` e adicione/ajuste a entrada
correspondente em `roms/ports/gamelist.xml`:

```xml
<game>
  <path>./Suika Elika.sh</path>
  <name>Suika Elika</name>
  <image>./images/suika-elika.png</image>
  <desc>Jogo de queda e fusão de frutas.</desc>
</game>
```

O nome em `<path>` precisa corresponder ao launcher instalado. A arte só aparece
se o tema do EmulationStation mostrar o campo de imagem. Também é possível usar
as ferramentas de scraping do Batocera; a documentação de Ports e o formato de
metadados estão nas páginas oficiais [Ports](https://wiki.batocera.org/systems%3Aports)
e [criação de pacote e gamelist](https://wiki.batocera.org/create_pacman_package).

**Nota sobre executáveis:** empacotar Python com PyInstaller para uma versão
concreta de Linux é uma alternativa possível, mas não é o método fornecido aqui
e não garante compatibilidade com a libc, SDL, arquitetura ou runtime do
Batocera. Por enquanto, distribua o código e dados junto do launcher e use o
Python/dependências compatíveis do aparelho.

## Documentação

- [Instalação e validação no Batocera](docs/BATOCERA.md)
- [Requisitos e regras do jogo](docs/PROJECT.md)
- [Arquitetura](docs/ARCHITECTURE.md)
- [Desenvolvimento e comandos de qualidade](docs/DEVELOPMENT.md)
- [Backlog e estado das tarefas](TODO.md)

## Referências

Mecânica inspirada em Suika Game, da Aladdin X, e direção visual inspirada em
Fruit Match, da Play.Works. As regras e valores de balanceamento de Suika Elika
são próprios do projeto.
