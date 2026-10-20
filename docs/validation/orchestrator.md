# Verificação da governança e da skill

Data: 20/10/2026. Escopo: AGENTS, arquitetura complementar, backlog e skill `todo-orchestrator`. Nenhuma tarefa de implementação do jogo foi executada.

## Verificações executadas

| Verificação | Comando / método | Resultado |
|---|---|---|
| Esquema da skill | `quick_validate.py skills/todo-orchestrator`, do skill-creator | Válido |
| Backlog real | `python skills/todo-orchestrator/scripts/todo_graph.py validate --todo TODO.md` | 34 tarefas, dependências válidas, sem ciclos |
| Comportamento do helper | `python -m unittest discover -s skills/todo-orchestrator/scripts -p "test_*.py" -v` | 23 testes aprovados |
| Lint | `python -m ruff check skills/todo-orchestrator/scripts --select E,F,I --ignore E501` | Aprovado, sem erros após organizar imports |
| Tipos | `python -m mypy --strict --python-executable <python-validado> skills/todo-orchestrator/scripts` | Aprovado nos 2 arquivos Python |
| Revisão independente | Um subagente, somente leitura no projeto e fixtures temporárias | Achados corrigidos; repetição independente sem pendências nos casos examinados |
| Integridade dos arquivos | Links Markdown relativos, cópia instalada e `git diff --check` | Links existentes, cópia conferida e espaços finais corrigidos; finais LF definidos em `.gitattributes` |

Ambiente de QA: Windows, Python 3.14; Ruff 0.17.1, mypy 2.4.0 e PyYAML 6.0.3 instalados apenas na pasta temporária de QA do chat. O jogo não ganhou dependências nem ambiente de execução nesta etapa. O helper distribuído usa somente a biblioteca padrão; PyYAML foi necessário apenas ao validador do skill-creator.

A primeira chamada do mypy tentou um alias de Python indisponível no Windows. A verificação foi repetida com o caminho explícito do interpretador e passou. Não houve supressão global de erros nem alteração dos aliases do sistema.

## Casos exercitados

Dependências só liberam consumidores após aceite. Arquivos iguais, subárvores e conflito leitor/escritor são serializados. Tarefas ativas mantêm reserva em revisão. Donos duplicados, dependências desconhecidas, ciclos e conclusão sem evidência são rejeitados.

Quatro posições totais permitem três subagentes; um trabalhador já ativo reduz os novos despachos. Capacidade maior continua limitada a quatro subagentes. Sem capacidade explícita, o helper oferece zero despachos paralelos.

Um gate de hardware bloqueado não impede tarefas locais independentes nem permite `complete: true`. Tarefas futuras permanecem excluídas. Interrupção conserva a reserva até reconciliação do escritor e do diff. As três operações da CLI são somente leitura e retornam código 2 para entradas inválidas.

## Correções decorrentes da revisão

1. Cabeçalhos com IDs malformados poderiam ser ignorados e produzir falsa conclusão do backlog. Agora geram erro; meia-risca válida é reconhecida.
2. Componentes terminados em ponto poderiam representar o mesmo arquivo no Windows e passar como reservas distintas. Agora são rejeitados, assim como nomes reservados e componentes ambíguos.
3. Exemplos cercados por crases/tildes eram interpretados como tarefas. Agora são excluídos; bloco sem fechamento gera erro.
4. Uma seção de aceitação vazia era aceita. Agora precisa conter ao menos um critério não vazio.

Regressões correspondentes foram acrescentadas. A revisão independente repetiu as reproduções e confirmou as correções, preservando o reconhecimento das 34 tarefas reais.

## Limitações

O helper não controla processos, não cria agentes e não comprova a verdade de uma evidência. A reserva é declarativa e depende de o orquestrador conferir agentes vivos e entradas reais. Junctions, symlinks, hardlinks e nomes curtos precisam de inspeção pelo coordenador, conforme o contrato da skill.

A orquestração foi exercitada com cenários sintéticos e uma revisão independente. Não houve execução completa do backlog com quatro subagentes reais, nem implementação de Pygame ou homologação no Batocera. Os gates de hardware e licença continuam registrados no TODO.

O commit fecha este lote de governança. Seu hash é informado no relatório final, sem referência circular dentro do próprio commit.
