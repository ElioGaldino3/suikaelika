# Desenvolvimento

## Requisitos

- Python 3.10 ou posterior.
- Pygame oficial 2.6.1 ou posterior da série 2.
- Pymunk 7.3 ou posterior da série 7.

As versões e dependências de execução são referências iniciais para desenvolver o jogo. O Batocera do usuário ainda não foi identificado, então esta configuração não é um lock nem comprova compatibilidade com um aparelho. As ferramentas de qualidade ficam no extra `dev` e não fazem parte das dependências de execução.

## Ambiente local

No PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Em Linux/macOS, substitua a ativação por `source .venv/bin/activate`. Use `python3` no lugar de `py -3` caso o launcher do Windows não esteja disponível.

## Controles de desenvolvimento

Inicie com `python main.py --desktop` (ou `python -m suika_elika --desktop`).
Sem `--desktop`, o jogo exige joystick inclusive no Windows. A opção autoriza
teclado como fallback quando não há controle ativo; um controle conectado tem
prioridade. Ao removê-lo, a partida pausa e o teclado pode confirmar a retomada.
Teclado nunca conta como joystick nem habilita BATALHA com um só controle.

- Teclas de seta: mover a mira e navegar pelos menus.
- Espaço ou Enter: cada novo aperto tenta soltar imediatamente; segurar repete a
  400 BPM (150 ms). Enter também confirma a opção selecionada nos menus.
- **Esc:** abrir o menu de pausa durante a partida; no menu, voltar/continuar.
- **P:** atalho adicional para abrir a pausa.
- No controle, o botão **Start** abre a pausa.

O botão sul do controle usa a mesma regra de aperto/hold, inclusive na batalha.
Não há cooldown artificial entre apertos novos. Nascer sobre outra fruta continua
bloqueado. Confirmações de menu/foco/reconexão são consumidas sem armar repetição;
solte e aperte novamente após retomar. O repeat do teclado do sistema não altera
a cadência. `classic-v4` mantém os novos recordes separados das regras anteriores.

Diagnóstico: `python tools/check_controllers.py` lista os joysticks nativos que
SDL enumera, sem abrir janela de jogo nem iniciar áudio. Também aceita
`--format json` e `--headless` para terminal sem display. É um script independente
que pode ser copiado para o Batocera e executado pelo `python3` local.

Seleção explícita de jogadores: `python main.py --p1-index 1 --p2-index 0`.
Informe ambos juntos, com índices distintos e não negativos da enumeração atual.
Se um índice não puder ser aberto, o jogo informa o erro no terminal e encerra
com código 1. Índice não é instance ID; após iniciar a partida, os lugares usam
instance ID e a política existente de reconexão.

## Verificações

Execute a partir da raiz do repositório:

```text
python -m pytest
python -m ruff check .
python -m mypy
```

Os comandos usam as configurações de `pyproject.toml`. O teste de importação inicia um interpretador limpo e confirma que importar os namespaces não importa Pygame nem módulos de implementação.
