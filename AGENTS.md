# Instruções de desenvolvimento

## Contexto

- Leia `docs/PROJECT.md` para entender o produto, os requisitos e os critérios de aceitação.
- Consulte `docs/ARCHITECTURE.md` quando a tarefa envolver decisões arquiteturais, contratos, dependências entre componentes ou mudanças no fluxo da simulação.
- Use `TODO.md` como fonte de tarefas, dependências, responsáveis, bloqueios e evidências. Não confunda tarefas planejadas com funcionalidades implementadas.
- O jogo será feito em Python + Pygame, terá suporte integral a joystick e será distribuído para Batocera. Comece com gráficos procedurais, sem imagens externas.

## Ciclo de trabalho

### Planejar

- Entenda o objetivo e os critérios de aceitação.
- Inspecione os componentes afetados e o estado do Git antes de editar.
- Para mudanças complexas, elabore um plano com dependências, contratos e verificações.
- Identifique quais partes dependem do equipamento Batocera. Continue o trabalho local independente e registre os bloqueios reais.

### Agir

- Execute mudanças incrementais.
- Siga a arquitetura existente; registre decisões que alterem contratos em `docs/ARCHITECTURE.md`.
- Não amplie o escopo sem justificativa. Arte final, fases, loja, serviços online e outros modos exigem escopo próprio.
- Use Skills apenas quando pertinentes. Para executar o backlog por delegação, leia `skills/todo-orchestrator/SKILL.md`.
- Consulte o Context7 MCP para documentação atual de bibliotecas e APIs quando a mudança depender delas: primeiro `resolve-library-id`, depois `query-docs`, por conceito. Se estiver indisponível, registre a limitação e consulte a documentação oficial; não invente uma consulta bem-sucedida.
- Preserve alterações do usuário e de outros agentes. Não use reset, clean, checkout ou restauração ampla para limpar trabalho concorrente.

### Avaliar

- Execute os testes relacionados à mudança e registre os comandos e resultados reais.
- Verifique erros de tipos e lint usando as ferramentas configuradas no projeto. Se ainda não houver ferramenta aplicável, registre isso; não apresente um check inexistente como aprovado.
- Revise o diff, incluindo arquivos novos e efeitos de renomes/remoções.
- Compare o resultado com os critérios de aceitação. Relatos de subagentes são insumos para revisão, não comprovação suficiente por si só.
- Testes locais ou com drivers simulados não homologam joystick físico, áudio HDMI nem execução no Batocera.

## Trabalho paralelo

- Um único orquestrador coordena o backlog. Até quatro subagentes podem trabalhar simultaneamente, limitados pela capacidade real da ferramenta; o orquestrador também ocupa uma posição quando o ambiente conta agentes totais.
- Delegue apenas tarefas com dependências concluídas e contratos estáveis. Não crie subagentes recursivamente para contornar o limite.
- Reserve os caminhos de escrita antes de delegar. Escrita concorrente no mesmo arquivo ou em arquivos de entrada ainda em alteração exige serialização ou nova divisão da tarefa.
- Somente o orquestrador altera `TODO.md`, integra mudanças de contratos compartilhados, faz staging e cria commits. Subagentes não executam comandos Git que alterem o índice, branches ou histórico.
- Em checkout compartilhado, as mudanças dos subagentes já estão nos arquivos. Não reaplique patches nem faça cherry-pick dessas mesmas mudanças.
- Atualize o estado para `in_review` ao receber uma entrega. Use `done` somente depois de revisar o diff, conferir critérios e registrar verificações.
- Não inicie a implementação do backlog por causa de uma solicitação que apenas crie ou edite documentos, planos ou a skill.

## Conclusão

Não declare sucesso sem indicar:

- Alterações realizadas.
- Verificações executadas e seus resultados.
- Limitações e riscos pendentes, incluindo verificações não executadas.
- Tarefas concluídas e bloqueadas quando houver execução do backlog.

**IMPORTANTE: faça um commit no final** de cada lote integrado e verificado que tenha mudanças autorizadas. Apenas o orquestrador faz esse commit em trabalho paralelo.

Antes de commitar, espere os agentes envolvidos terminarem ou interrompa-os e confirme a liberação dos arquivos. Revise e adicione caminhos explicitamente; não inclua alterações alheias nem segredos. Use uma mensagem que descreva o resultado e informe o hash no relatório final.

Se uma verificação relevante falhar, corrija o problema antes de marcar a tarefa como concluída. Se o commit estiver impedido por identidade, hook ou outro erro, registre o motivo e o estado real; não invente hash, não desabilite o hook e não declare conclusão total. Um lote parcial só pode ser commitado quando for coerente e seu escopo e limitações estiverem explícitos.
