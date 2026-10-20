# Delegação e revisão

## Mensagem para o trabalhador

```text
Tarefa: <ID e título>; trabalhe apenas nessa tarefa.
Raiz/base: <caminho absoluto>; <branch e HEAD>; <checkout compartilhado ou isolado>.
Contexto: leia AGENTS.md, trechos relevantes do produto e arquitetura.
Dependências concluídas: <IDs e contratos estabilizados>.
Objetivo: <resultado concreto>.
Escrita autorizada: <arquivos/subárvores exatos do campo Writes>.
Leitura: <arquivos/contratos estáveis do campo Reads>.
Critérios de aceitação: <critérios completos, sem depender de outro chat>.
Verificações: <comandos existentes ou comportamento que deve ser verificado>.

Não subdelegue, não altere TODO.md/AGENTS.md/contratos fora da reserva e não
execute staging, commit, checkout, reset, stash, merge ou cherry-pick.
Outros agentes compartilham os arquivos: preserve o trabalho deles.
Se precisar editar fora da reserva, reporte antes de alterar.
Ao terminar, pare de escrever e entregue o relatório abaixo.
```

## Retorno obrigatório

```text
ID / resultado: concluído para revisão | parcial | bloqueado.
Arquivos criados, alterados, removidos ou renomeados.
Comportamento entregue e relação com cada critério.
Comandos executados, códigos de saída e resumo dos resultados reais.
Verificações não executadas e motivo.
Dependências/decisões pendentes e eventual impacto em contratos.
Confirmação: terminei as escritas nos caminhos reservados.
```

O trabalhador não muda o estado global da tarefa nem faz promessas de commit. Quando possível, inclui testes relevantes no mesmo lote e indica a diferença entre aprovação automática e observação manual.

Uma tarefa explícita de preparação de contratos pode reservar seus arquivos, desde que não haja consumidores ativos. A revisão do orquestrador congela a interface antes de liberar as tarefas dependentes. Isso não autoriza trabalhadores de implementação a mudar contratos por conveniência.

## Revisão pelo orquestrador

Em checkout compartilhado, capture estado inicial dos caminhos e mudanças preexistentes antes de delegar. Na volta, use status/diff dos mesmos paths e inspecione novos arquivos (que ainda não aparecem em `git diff` comum). Compare resultado com a reserva e aceite somente o conteúdo atribuível à tarefa. Um diretório reservado por um agente não autoriza apagar arquivos que já existiam nele.

Execute testes direcionados e checks configurados. Só repita ou amplie uma suíte quando houver mudanças, falhas ou riscos que justifiquem. Review de documentação não precisa instalar as dependências do jogo; scripts novos da skill precisam de validação comportamental em fixtures isoladas.

Revisor paralelo, quando útil, também ocupa uma posição no limite global. Recebe uma tarefa de leitura e devolve achados com evidências. Não reserve uma posição de escrita para dois agentes nem conclua a tarefa antes do retorno da revisão exigida.

Se for preciso mudar contrato, aguarde ou interrompa consumidores, confirme parada, atualize a reserva e só então faça a alteração. Reiniciar a tentativa usa o novo contrato e registra por que a entrega anterior não foi aceita.

## Checkpoint e retomada

Use `TODO.md` para estado/owner/evidência e um log de lote quando necessário. Um checkpoint informa IDs ativos, donos, arquivos, base, verificações já feitas e bloqueios. Não precisa copiar todo o produto a cada ciclo.

Após interrupção, confira agentes vivos e arquivos reais. Se um agente antigo ainda puder escrever, não entregue sua reserva a outro. Se ele já encerrou, revise a entrega parcial antes de escolher reaproveitar, corrigir ou retornar a `pending`. Preserve a evidência das tentativas anteriores.

## Exercícios de validação da skill

Use apenas diretório temporário e nenhum hardware real. Exemplos úteis:

- Duas tarefas independentes e uma dependente: a dependente só inicia depois de aceite das duas.
- Arquivos iguais, subárvores sobrepostas ou entrada lida por outro escritor: tarefas conflitantes são serializadas.
- Quatro posições totais: no máximo três trabalhadores além da raiz.
- Hardware bloqueado com trabalho local pronto: o trabalho local avança; não há falsa homologação.
- Worker interrompido com diff parcial: a reserva só é redistribuída depois de reconciliar o escritor.
- Entrega que afirma ter passado em teste sem saída verificável: permanece em revisão.

As instruções desta referência não mandam executar o backlog real como teste da skill.
