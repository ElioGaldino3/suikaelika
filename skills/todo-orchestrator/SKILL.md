---
name: todo-orchestrator
description: Execute um backlog TODO.md por lotes com dependências, revisão, evidências e commits, coordenando até quatro subagentes dentro da capacidade disponível. Use ao pedir execução ou continuidade das tarefas por um orquestrador; editar apenas um plano ou TODO não inicia o backlog.
---

# Orquestrador de TODO

Conduza o escopo autorizado do backlog até a conclusão verificável ou até restarem apenas bloqueios reais. O pedido de criar/editar a skill não autoriza executar o backlog. A skill não cria agendamentos nem chats independentes e não amplia autorização para publicação, deploy ou mensagens externas.

## Preparar a execução

1. Identifique a raiz correta e leia `AGENTS.md`, `TODO.md`, o contexto do produto e, para contratos/integração, `docs/ARCHITECTURE.md`. Registre branch, HEAD e alterações pré-existentes. Não adote uma pasta apenas porque contém um TODO.
2. Respeite o escopo pedido, inclusive IDs, milestone e exclusões. Por padrão use o escopo `mvp` quando o backlog deste projeto for executado; `future` e `deferred` exigem pedido correspondente. Um resumo de status não autoriza iniciar trabalho.
3. Leia [o contrato do backlog](references/backlog-contract.md). Valide antes de delegar: `python <skill>/scripts/todo_graph.py validate --todo <repo>/TODO.md`. O helper é somente leitura; erro de esquema, dependência ou conflito interrompe novos despachos até ser resolvido.
4. Descubra a capacidade real dos agentes. Limite global: até **4 subagentes simultâneos**, sem delegação recursiva. Se o ambiente limita agentes totais, reserve a posição do orquestrador: quatro posições totais permitem três subagentes. Conte agentes de revisão e trabalhadores existentes; não invente posições livres.
5. Prepare um plano curto de lotes e consulte `plan --todo <arquivo> --team-slots <total> --max-workers 4 --scope mvp`. O plano é uma sugestão conservadora: confirme conflitos semânticos, recursos externos e contratos antes de despachar. Sem ferramenta de delegação, execute sequencialmente e declare essa limitação.

## Despachar e acompanhar

Somente o orquestrador escreve `TODO.md`, faz staging/commit e integra arquivos compartilhados. Em checkout compartilhado, todos veem as alterações imediatamente; não copie de novo o patch de um subagente. Reserve também os caminhos da tarefa executada pelo próprio orquestrador, se houver.

Antes de iniciar cada tarefa, releia o estado e reserve seus `Writes`/`Reads`: transição `pending → in_progress`, `Owner` único e `Attempts + 1`. Inclua na mensagem de delegação o ID, objetivo, dependências verificadas, base de trabalho, arquivos autorizados e critérios de aceitação. Use [o protocolo de entrega](references/delegation.md) para o formato e as regras de retorno.

- Delegue uma tarefa por trabalhador; pode haver nova tarefa ao mesmo agente quando a anterior estiver integrada.
- Preserve modelo e esforço herdados, salvo instrução explícita aplicável.
- Proíba subdelegação e alterações de TODO ou índice/histórico Git pelo trabalhador. Contratos compartilhados só podem ser preparados/alterados em tarefa de contrato explicitamente reservada, sem consumidores ativos e com revisão do orquestrador antes de liberá-los.
- Um trabalhador que precise editar fora de `Writes` solicita redistribuição; não adquire arquivos por conta própria.
- Não permita escrita concorrente nem leitura de contrato que outro agente esteja alterando. O helper cobre caminhos declarados; o orquestrador cobre dependências semânticas.
- Mantenha atualizações curtas ao usuário sobre entregas, descobertas e bloqueios. Espere eventos de agentes com espera limitada; não faça polling contínuo nem alegue trabalho em segundo plano depois de encerrar a resposta.
- Resultado recebido vira `in_review`. Não marque `done` com base apenas na mensagem do agente.

## Revisar e integrar

Para cada entrega, confirme que o trabalhador terminou e inspecione os arquivos e o diff dos caminhos reservados, incluindo arquivos novos. Compare com a base capturada e os critérios. Execute verificações relevantes; confira que comandos citados realmente foram executados e distinguem teste simulado de hardware real.

Corrija ou devolva defeitos com um critério preciso. Não reescreva arquivos de um agente que ainda está trabalhando. Problemas que envolvam outro contrato exigem serialização e atualização do plano.

Marque `done` apenas quando todos os critérios da tarefa estiverem satisfeitos e as evidências estiverem registradas. Se uma verificação externa fizer parte da tarefa, mantenha-a bloqueada ou separe uma tarefa local já aceita de uma tarefa de homologação; não marque tudo concluído acrescentando uma ressalva. Libere o responsável e registre testes, resultado e limitações em `Evidence`.

Depois de cada integração, revalide o grafo e selecione novas tarefas prontas. Um bloqueio de hardware não impede frentes locais independentes. Não desbloqueie uma tarefa apenas pelo tempo transcorrido ou porque um teste diferente passou.

## Recuperação e parada

- Agente ausente, timeout ou erro: consulte o estado real, recolha progresso e inspecione o diff antes de redistribuir. Interrompa e confirme que o agente parou antes de liberar arquivos. Não apague alterações alheias nem repita uma entrega já aplicada.
- `Attempts` conta despachos. Após **duas tentativas malsucedidas para o mesmo bloqueio**, registre causa, evidência e condição de desbloqueio, e passe a outras tarefas. Não faça ciclos infinitos, não abra agentes extras para o mesmo problema e não redefina o contador para contornar o limite.
- Na retomada, reconcilie `in_progress`/`in_review` com os agentes vivos, o diff e o último checkpoint. Ownership antigo não expira automaticamente; só reutilize depois de verificar ausência de escritor ativo. Preserve alterações parciais até revisá-las.
- Ao pedido de parar, não despache mais tarefas; recolha ou interrompa trabalho com segurança, registre o estado e cumpra a política de commit do projeto para um lote coerente. Não trate parada como conclusão das tarefas restantes.
- Encerre quando o escopo solicitado estiver todo `done`, o usuário parar, ou não houver tarefa executável após revisar bloqueios/capacidade. Informe IDs e condição concreta para continuar. Sem limite explícito do usuário, continue enquanto houver trabalho autorizado e executável.

## Commit e relatório

Em cada lote coerente, espere os escritores terminarem, revise o diff, execute checks, atualize TODO/evidências e faça commit conforme `AGENTS.md`. Adicione caminhos explicitamente. Não use `git add .`, não inclua mudanças pré-existentes sem autorização e não desative hooks. Apenas o orquestrador altera o índice/histórico.

O commit fecha o lote integrado; uma tarefa pode estar aceita em `done` enquanto o commit do lote ainda está sendo preparado, mas o orquestrador não encerra o trabalho com mudanças autorizadas sem tentar o commit exigido. `done` não significa publicado ou homologado em outro ambiente.

Reporte: tarefas concluídas, arquivos/resultados principais, comandos e resultados das verificações, bloqueios e riscos pendentes, hash do commit e estado residual do Git. Se o commit falhar, informe o erro; não invente sucesso nem hash. Não crie commits vazios para um pedido somente de status.
