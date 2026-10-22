# TODO — Desempenho, recordes e jogadores

Atualizado em 22/10/2026. Este backlog substitui integralmente o TODO anterior a pedido do usuário.
**Somente planejamento autorizado nesta etapa. Nenhuma tarefa abaixo foi iniciada ou implementada.**
Os caminhos de escrita são reservas propostas para execução futura, não alterações desta entrega.
Os IDs anteriores não são reutilizados; o histórico anterior pode ser consultado no Git.

## Pedidos e decisões de escopo

- Auditar o jogo completo para descobrir as causas das travadas durante fusões e corrigir os gargalos comprovados, com comparação antes/depois.
- Persistir e exibir o recorde e seu tempo após reiniciar o aplicativo e o equipamento.
- Manter um ranking local dos cinco melhores tempos, mostrado na tela inicial e no pós-jogo.
- Ao terminar uma partida, abrir identificação com **Desconhecido** como opção e foco inicial, grade de jogadores existentes e botão **Novo jogador**.
- Investigar entrada de nome fornecida pelo Batocera. Se não houver solução utilizável com joystick no runtime real, implementar teclado virtual próprio.
- Manter operação offline e experiência completa pelo controle. Não incluir contas online, edição de arte ou novos modos.
- Proposta de escopo para recordes/ranking/identificação: clássico. Preservar a separação da batalha; sua inclusão depende da definição em SE-046, sem misturar resultados de modos, metas ou rulesets diferentes.

**Decisões que precisam ser resolvidas antes dos contratos do ranking (SE-046):**

1. “Melhores tempos”: maior duração de sobrevivência ou menor tempo para atingir um objetivo? Se for velocidade, qual objetivo e quais partidas são elegíveis? Não ordenar por menor duração até a derrota, pois isso premiaria perder rapidamente.
2. “Tempo do recorde”: duração total da partida que fez a melhor pontuação ou instante em que essa pontuação foi atingida? Proposta: duração final da partida recordista, independente do ranking de tempos.
3. Ranking por partidas (permitindo nomes repetidos) ou apenas o melhor resultado de cada jogador? Definir desempate estável, inclusão de Desconhecido, tratamento da batalha e limites de nomes.

Essas decisões devem ser confirmadas com o usuário na execução; esta etapa apenas registra as perguntas.

## Contexto observado para orientar a execução

Inspeção estática de `game/session.py`, `persistence.py`, cenas e arquitetura; sem profiling ou reprodução nesta etapa:

- Já há persistência JSON e `RecordData.duration_seconds`; investigar integração, sem partir da premissa de que tudo precisa ser criado do zero.
- `GameSession._apply_merge_resolution()` chama `_save_record()` ao superar o recorde. `JsonPersistence._write_data()` serializa JSON, executa `flush`/`os.fsync`, copia backup e substitui arquivo no mesmo fluxo. É uma hipótese forte de bloqueio por I/O em fusões recordistas, ainda sem causa confirmada por medição.
- O salvamento durante a partida pode capturar o tempo intermediário; a política de preservar o registro anterior em empate de pontuação também deve ser auditada para garantir o tempo final correto.
- A arquitetura já registra grade espacial para contatos e cache LRU de rotações. Medir o comportamento real antes de propor novas otimizações de física ou gráficos.
- Já existe `tools/performance.py`; avaliar cobertura e reaproveitá-lo. O TODO anterior registrava falha em teste de assets, ainda não revalidada nesta etapa: medir a baseline antes de atribuir regressões.
- Homologações anteriores não são declaradas concluídas pela substituição do TODO. Este backlog cobre a validação no equipamento necessária aos pedidos atuais.

## Frente de desempenho

### SE-044 — Auditar travadas e produzir diagnóstico reproduzível

- Status: `in_review`
- Scope: `performance-records`
- Priority: `P0`
- Depends: `none`
- Writes: `tools/performance.py; tools/diagnostics.py; docs/validation/merge-performance.md`
- Reads: `suika_elika/**; tests/**; pyproject.toml; docs/PROJECT.md; docs/ARCHITECTURE.md; docs/BATOCERA.md; docs/ANDROID-TV.md`
- Owner: `/root/se044`
- Attempts: `2`
- Evidence: Tentativa 1 mediu workloads isolados e registrou baseline local (249 passed, 1 failed, 52 errors; Ruff passou; mypy teve 2 erros de tipos POSIX de `resource` no Windows). Tentativa 2 entregou workloads determinísticos de clássico/batalha, snapshot/fusão sintética, limiar de recorde com stub e sessão curta; resultados e limitações estão em revisão, incluindo falta de replay natural e I/O/áudio reais.
- Blocker: `none`

**Aceitação:**

- Reproduzir fusões isoladas, cadeias, pilha densa e sessões longas, no clássico e na batalha. Comparar partida abaixo do recorde e partida superando o recorde; registrar seed/ações, quantidade de frutas, hardware, plataforma e versões.
- Auditar loop/acumulador e recuperação de atrasos, física/contatos, busca e resolução de fusões, snapshots, renderização/cache/transformações, partículas, áudio, carregamento de assets, alocações/GC e persistência. Separar hipóteses, medições e achados descartados.
- Medir tempo por etapa e por quadro, p50/p95/p99, pior quadro, quantidade/duração de pausas e memória/cache em sessão prolongada. FPS médio sozinho não comprova fluidez.
- Isolar I/O de recordes, efeitos, áudio e desenho em comparações controladas, sem transformar os desvios de diagnóstico em alteração de regras do jogo.
- Produzir relatório com reprodução, perfis, causa(s) sustentada(s) por evidência e correções priorizadas por impacto/risco. Comparar com orçamento de 16,67 ms para 60 FPS e fixar limites verificáveis no equipamento de referência.
- Usar Context7 para APIs de Pygame/Pymunk se necessário; resolver biblioteca antes de consultar cada conceito. Se indisponível, registrar e usar documentação oficial.
- Obter baseline dos testes configurados. Se faltar acesso ao equipamento que apresenta o problema, concluir apenas diagnóstico local e registrar explicitamente o que SE-052 ainda precisa medir.

### SE-045 — Corrigir os gargalos comprovados nas fusões

- Status: `pending`
- Scope: `performance-records`
- Priority: `P0`
- Depends: `SE-044`
- Writes: `suika_elika/**; tests/**; tools/performance.py; docs/ARCHITECTURE.md; docs/validation/merge-performance.md`
- Reads: `docs/PROJECT.md; pyproject.toml`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Não executada; intervenções dependem das medições de SE-044.
- Blocker: `none`

**Aceitação:**

- Corrigir causas medidas e comparar os mesmos cenários antes/depois, com limites de tempo por quadro definidos no diagnóstico, incluindo fusões recordistas e cadeias.
- Se confirmada a hipótese de I/O, retirar gravações duráveis repetidas do passo crítico e definir política de consolidação, falhas e encerramento. Preservar dados em pontos seguros e declarar a janela de perda em interrupção abrupta; não apenas remover `fsync` ou transferir custo para outro quadro sem medir.
- Preservar pares de fusão únicos, pontuação, RNG, cadência de lançamento, perigo, pausa e simetria da batalha. Otimizações visuais não alteram física; mudança real de regra exige versionamento explícito.
- Verificar limites de memória/cache, ausência de acumulação de trabalho e comportamento com armazenamento lento/indisponível. Não escrever JSON por fruta/fusão como efeito colateral das novas telas.
- Rodar testes relevantes e suíte, Ruff e mypy conforme `pyproject.toml`; documentar resultados reais, comparação de desempenho e limitações de hardware.
- Reserva ampla temporária: reduzir `Writes` aos arquivos identificados pela auditoria antes de distribuir implementação. Serializar esta tarefa com mudanças de sessão/persistência das demais frentes.

## Contratos e dados locais

### SE-046 — Definir regras de tempo, ranking e identificação

- Status: `pending`
- Scope: `performance-records`
- Priority: `P1`
- Depends: `none`
- Writes: `docs/PROJECT.md; docs/ARCHITECTURE.md; suika_elika/contracts/ports.py; suika_elika/contracts/models.py; suika_elika/contracts/input.py; suika_elika/contracts/__init__.py; tests/contracts/test_contracts.py`
- Reads: `suika_elika/game/session.py; suika_elika/game/battle.py; suika_elika/persistence.py; suika_elika/scene_manager.py`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Não executada; decisões semânticas pendentes descritas no início.
- Blocker: `none`

**Aceitação:**

- Resolver com o usuário as três decisões do início antes de implementar sua lógica; registrar regra explícita e exemplos de classificação/desempate.
- Definir relógio de jogo ativo: pausa, perda de foco, desconexão e identificação não aumentam tempo; início/fim do intervalo são explícitos. Comparar duração com precisão interna, arredondando apenas a apresentação.
- Definir jogador com ID estável e nome de exibição, identidade reservada Desconhecido, resultado com ID único e vínculo ao jogador, modo/ruleset/objetivo, pontos e tempo. Não confundir jogadores com perfis de controle existentes.
- Definir contratos de consulta/gravação e fluxo: fim da rodada → identificação → confirmação → resultado com ranking → nova partida/menu; um resultado é registrado uma única vez.
- Definir salvamento provisório como Desconhecido antes da identificação e associação posterior sem duplicação, para não perder resultado ao fechar nessa tela. Definir também checkpoint de recorde durante partida interrompida.
- Definir schema/migração compatível com dados atuais e política de nomes vazios, duplicados, acentos, comprimento e desempate. Ausência de dados antigos não pode gerar tempos fictícios no ranking.
- Verificar contratos com testes focados e documentar decisões como futuras até sua implementação.

### SE-047 — Persistir recorde, tempo, jogadores e melhores resultados

- Status: `pending`
- Scope: `performance-records`
- Priority: `P1`
- Depends: `SE-045, SE-046`
- Writes: `suika_elika/persistence.py; suika_elika/platform.py; suika_elika/game/session.py; suika_elika/records.py; tests/services/test_persistence.py; tests/services/test_platform.py; tests/game/test_session.py; tests/services/test_records.py; docs/ARCHITECTURE.md`
- Reads: `suika_elika/contracts/**; docs/PROJECT.md; docs/BATOCERA.md; docs/ANDROID-TV.md; docs/validation/merge-performance.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Não executada; contratos e correção de desempenho são pré-requisitos.
- Blocker: `none`

**Aceitação:**

- Diagnosticar a perda/ausência atual: criação do serviço, diretório gravável, carregamento no início, chave modo/ruleset e exibição. Reutilizar persistência existente com migração não destrutiva e backup recuperável.
- Salvar recorde e tempo segundo SE-046, mantendo o vínculo à partida correta inclusive quando a pontuação final empata com checkpoint da mesma partida. Uma partida inferior não sobrescreve o recorde.
- Persistir jogadores e resultados identificados/Desconhecido, extrair no máximo cinco melhores tempos pela regra acordada e aplicar desempate estável. Confirmar de novo ou revisitar a tela não duplica entradas.
- Garantir dados após sair/reabrir o processo e após reinício do equipamento, usando caminhos persistentes do Batocera e Android TV quando aplicável, sem gravar na pasta instalada do jogo.
- Testar primeira execução, migração, reinício com nova instância do serviço, arquivo corrompido, falha de escrita e interrupção em pontos de salvamento. Apresentar erro sem travar; não afirmar que cache em memória está salvo em disco.
- Verificar que a política de gravação respeita o orçamento de SE-045; preservar isolamento de modo/ruleset/objetivo e dados anteriores.

## Entrada de nome e pós-jogo

### SE-048 — Investigar entrada de texto disponível no Batocera

- Status: `done`
- Scope: `performance-records`
- Priority: `P1`
- Depends: `none`
- Writes: `docs/decisions/player-name-input.md`
- Reads: `docs/BATOCERA.md; suika_elika/input/**; suika_elika/app.py; packaging/batocera/**`
- Owner: `unassigned`
- Attempts: `1`
- Evidence: `docs/decisions/player-name-input.md` distingue o teclado/configuração do EmulationStation e Evmapy de uma API de texto acessível ao processo Pygame. Consultadas fontes oficiais do Batocera, documentação oficial do Pygame e Context7 (Pygame/SDL; SDL consultado é SDL3 e está rotulado como limitação). Não foi encontrada integração nativa demonstrável; recomendação para SE-049: teclado virtual próprio navegável por joystick. Whitespace verificado; navegação física permanece para SE-052.
- Blocker: `none`

**Aceitação:**

- Consultar documentação oficial do Batocera sobre entrada de texto/teclado virtual acessível a um processo Pygame externo; distinguir UI do EmulationStation de recurso chamável pelo jogo.
- Para APIs Pygame/SDL, consultar Context7 primeiro; registrar fontes, versões, disponibilidade e limitações. Falta de documentação ou de acesso ao aparelho não comprova suporte.
- Avaliar abertura, foco, navegação integral pelo controle, confirmação/cancelamento, acentos e retorno ao jogo. Teclado físico pode ser adicional, nunca requisito.
- Entregar decisão de integração nativa somente com viabilidade demonstrada; na ausência de solução demonstrável, adotar teclado virtual próprio na SE-049. Prova no aparelho pendente permanece explícita.

### SE-049 — Implementar cadastro e teclado para nomes

- Status: `pending`
- Scope: `performance-records`
- Priority: `P1`
- Depends: `SE-047, SE-048`
- Writes: `suika_elika/scenes/player_name.py; suika_elika/input/text.py; suika_elika/input/actions.py; suika_elika/rendering/player_name.py; suika_elika/app.py; suika_elika/scene_manager.py; tests/input/test_text.py; tests/scenes/test_player_name.py`
- Reads: `suika_elika/contracts/**; suika_elika/persistence.py; suika_elika/records.py; docs/decisions/player-name-input.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Não executada; mecanismo de texto depende da pesquisa SE-048.
- Blocker: `none`

**Aceitação:**

- Usar entrada nativa viável conforme SE-048 ou criar teclado virtual de letras, espaço, apagar, concluir e cancelar, legível na TV e totalmente navegável por direcional/analógico e botões.
- Aceitar nomes em português segundo SE-046, impedir nome vazio e duplicidade conforme política definida e dar feedback para comprimento máximo.
- Ao confirmar cadastro, persistir jogador e retornar à grade com o novo jogador selecionado. Cancelar retorna sem criar jogador e sem perder resultado pendente.
- Conexão/desconexão, repetição ao segurar direção e foco não geram caracteres ou confirmações residuais. Texto digitado não aciona soltura/atalhos de gameplay.
- Testar fluxo com eventos simulados e inspecionar visualmente o teclado. Reservar validação com controle físico ao SE-052; não exigir `--desktop` para identificar jogador no Batocera.

### SE-050 — Criar identificação pós-jogo com grade de jogadores

- Status: `pending`
- Scope: `performance-records`
- Priority: `P1`
- Depends: `SE-049`
- Writes: `suika_elika/scenes/player_select.py; suika_elika/rendering/player_select.py; suika_elika/scenes/play.py; suika_elika/scenes/results.py; suika_elika/scene_manager.py; tests/scenes/test_player_select.py; tests/integration/test_app_flow.py`
- Reads: `suika_elika/records.py; suika_elika/persistence.py; suika_elika/contracts/**; suika_elika/scenes/player_name.py; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Não executada; depende de persistência e cadastro.
- Blocker: `none`

**Aceitação:**

- Toda partida concluída no escopo acordado abre identificação antes do resultado; Desconhecido está visível e focado inicialmente e permite continuar com um comando de confirmação.
- Exibir jogadores persistidos em grade, botão Novo jogador e navegação bidimensional previsível. Lista vazia, muitas pessoas, nomes longos e paginação/rolagem têm comportamento definido.
- Selecionar jogador existente associa resultado sem novo cadastro. Novo jogador abre SE-049; retorno preserva a partida encerrada e a seleção esperada.
- Resultado permanece congelado. Confirmar/voltar, reconectar ou repetir evento não reabre a rodada nem grava duplicatas. Definir retorno/cancelamento mantendo possibilidade de seguir como Desconhecido.
- Testar encadeamento fim → identificação → cadastro/seleção → resultado → menu/reinício, inclusive falha de gravação e encerramento na identificação.

## Apresentação e validação final

### SE-051 — Exibir recorde, tempo e top 5 no início e pós-jogo

- Status: `pending`
- Scope: `performance-records`
- Priority: `P1`
- Depends: `SE-050`
- Writes: `suika_elika/scenes/title.py; suika_elika/scenes/results.py; suika_elika/rendering/renderer.py; suika_elika/rendering/hud.py; suika_elika/scene_manager.py; tests/scenes/test_navigation.py; tests/rendering/test_composition.py; docs/validation/records-ui.md`
- Reads: `suika_elika/records.py; suika_elika/persistence.py; suika_elika/contracts/**; docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Não executada; depende do fluxo completo de identificação.
- Blocker: `none`

**Aceitação:**

- Tela inicial e pós-jogo mostram recorde com tempo associado e ranking de até cinco posições com jogador e tempo, carregados do disco na abertura do jogo. HUD mantém recorde/tempo legíveis durante a partida conforme regra acordada.
- Título do ranking explica a métrica escolhida; dados do resultado recém-confirmado aparecem imediatamente. Identificar contexto de modo/objetivo/ruleset sem misturar classificações incompatíveis.
- Tratar zero a cinco entradas sem inventar resultados, destacar a partida atual se classificada e formatar durações acima de uma hora sem corte.
- Inspecionar renderização a 1280×720 e escalas suportadas, área segura da TV, contraste, nomes longos e foco de menus. Ranking não encobre opções nem impede reinício pelo controle.
- Testar reabrir o aplicativo, retorno do resultado ao menu e nova partida preservando recordes, tempos, nomes e ordenação.

### SE-052 — Validar integração, desempenho e persistência no equipamento

- Status: `pending`
- Scope: `performance-records`
- Priority: `P1`
- Depends: `SE-051`
- Writes: `docs/validation/performance-records-hardware.md; docs/BATOCERA.md; docs/ANDROID-TV.md; README.md`
- Reads: `suika_elika/**; tests/**; tools/performance.py; tools/build_batocera.py; packaging/**; pyproject.toml; docs/validation/merge-performance.md; docs/validation/records-ui.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Não executada; disponibilidade do equipamento deverá ser verificada na execução.
- Blocker: `none`

**Aceitação:**

- Rodar `python -m pytest -q`, `python -m ruff check .`, `python -m mypy` e build/smoke aplicáveis aos pacotes alterados; registrar comandos/resultados e separar falhas preexistentes de regressões.
- Validar no Batocera com controle físico: fusões repetidas e recordistas, cadeias, pilha densa, jogo prolongado, grade, cadastro, teclado escolhido, ranking, hotplug/foco e áudio. Repetir no Android TV se for o equipamento do relato ou receber pacote alterado.
- Comparar medições com SE-044/045 no equipamento de referência, inclusive pausas de I/O e memória. Não aprovar desempenho somente por FPS médio ou teste headless.
- Encerrar e reabrir o jogo, reiniciar equipamento e confirmar recorde/tempo/top 5/jogadores. Verificar erro de armazenamento, encerramento na identificação e limites de recuperação acordados.
- Se faltar aparelho/controle, registrar tarefa como bloqueada com condição concreta de desbloqueio; manter evidências locais separadas e não declarar homologação física.
- Revisar diff e critérios de cada lote, atualizar estados/evidências no TODO e criar commits com caminhos explícitos somente após verificações. Nada desta lista autoriza execução durante a entrega atual de planejamento.

## Ordem e critérios de execução futura

1. Auditar desempenho (SE-044) e corrigir causas comprovadas (SE-045).
2. Resolver contratos/semântica (SE-046) e investigar entrada do Batocera (SE-048); podem ser preparados antes, sem editar caminhos em conflito com a otimização.
3. Persistência (SE-047) → cadastro/teclado (SE-049) → identificação (SE-050) → apresentação (SE-051) → validação final (SE-052).

Todos os itens permanecem `pending`, com zero tentativas. Dependências não concluídas impedem consumidores; ausência futura de hardware pode bloquear apenas as verificações que dependem dele. Os caminhos compartilhados exigem serialização ou divisão revisada antes de qualquer delegação. Esta alteração do TODO não inicia o backlog.
