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

- Teclas de seta: mover a mira e navegar pelos menus.
- Espaço ou Enter: soltar fruta; Enter também confirma a opção selecionada.
- **Esc:** abrir o menu de pausa durante a partida; no menu, voltar/continuar.
- **P:** atalho adicional para abrir a pausa.
- No controle, o botão **Start** abre a pausa.

## Verificações

Execute a partir da raiz do repositório:

```text
python -m pytest
python -m ruff check .
python -m mypy
```

Os comandos usam as configurações de `pyproject.toml`. O teste de importação inicia um interpretador limpo e confirma que importar os namespaces não importa Pygame nem módulos de implementação.
