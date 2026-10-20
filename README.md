# Suika Elika

Jogo de queda e fusão de frutas, planejado em **Python + Pygame**, com controles por joystick e execução no **Batocera**.

A especificação completa está em [docs/PROJECT.md](docs/PROJECT.md). Ela reúne pesquisa das referências, análise dos vídeos, regras propostas, física, direção de arte, áudio, arquitetura e distribuição.

As instruções de desenvolvimento estão em [AGENTS.md](AGENTS.md), os contratos e limites de componentes em [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e as tarefas com dependências em [TODO.md](TODO.md).

**Estado atual:** projeto em fase de especificação. Ainda não há implementação executável, imagens geradas ou pacote instalado no Batocera. O primeiro protótipo será desenhado com formas do Pygame.

**Referências:** mecânica de Suika Game, da Aladdin X, e direção visual de Fruit Match, da Play.Works. Os valores de balanceamento e as regras específicas de Suika Elika são propostas próprias, identificadas no documento.

Documentação pesquisada em 20 de outubro de 2026.

Para executar o backlog com delegação, use a skill [todo-orchestrator](skills/todo-orchestrator/SKILL.md), também instalada no diretório local de skills do Codex. Exemplo de pedido: “Use $todo-orchestrator para executar as tarefas prontas do escopo mvp do TODO.md e continuar até restarem somente bloqueios externos”. Até quatro subagentes são permitidos, respeitando a capacidade real do ambiente; com quatro posições totais, são três trabalhadores e um orquestrador.

Para apenas verificar o planejamento, sem executar tarefas nem alterar o TODO:

```text
python skills/todo-orchestrator/scripts/todo_graph.py validate --todo TODO.md
python skills/todo-orchestrator/scripts/todo_graph.py plan --todo TODO.md --scope mvp --team-slots 4 --max-workers 4
```

O helper usa apenas a biblioteca padrão. Seus testes: `python -m unittest discover -s skills/todo-orchestrator/scripts -p "test_*.py" -v`.
