# Contrato do backlog

O helper aceita Markdown com um bloco por tarefa. Cabeçalho: `### SE-001 — Título` (também aceita `–` ou `-` como separador). Prefixos podem variar; IDs seguem `[A-Z]+-000` (três ou mais algarismos ASCII). Cada bloco termina no próximo cabeçalho de nível 2 ou 3. Use IDs estáveis; não recicle IDs removidos. Cabeçalho malformado com metadados gera erro, sem esconder a tarefa. Exemplos em blocos cercados por crases ou tildes são ignorados; bloco sem fechamento gera erro.

Campos obrigatórios, uma vez por bloco:

```markdown
### EX-001 — Exemplo de tarefa

- Status: `pending`
- Scope: `mvp`
- Priority: `P1`
- Depends: `none`
- Writes: `package/component.py; tests/test_component.py`
- Reads: `docs/PROJECT.md; docs/ARCHITECTURE.md`
- Owner: `unassigned`
- Attempts: `0`
- Evidence: Ainda não executada.
- Blocker: `none`

**Objetivo:** resultado concreto.

**Aceitação:**
- Critério observável e forma de verificação.
```

## Estados

| Estado | Significado e transição |
|---|---|
| `pending` | Não reservada. Pode iniciar se dependências estiverem `done` e caminhos livres |
| `in_progress` | Reservada e em execução por `Owner`; `Attempts` deve ser pelo menos 1 |
| `in_review` | Entrega recebida e caminhos ainda reservados até revisão |
| `done` | Critérios verificados e `Evidence` preenchida; `Owner` liberado |
| `blocked` | Motivo concreto em `Blocker`; não se torna pronta automaticamente |
| `deferred` | Fora do escopo atual; só reativar mediante escopo correspondente |

Somente o orquestrador faz transições. Estados ativos exigem dono diferente de `unassigned`; estados inativos exigem dono liberado. `blocked` exige uma condição de desbloqueio; os demais usam `Blocker: none`. Todas as dependências de uma tarefa `done` ou ativa devem estar `done`.

Prioridades: `P0` bloqueador/fundação, `P1` MVP, `P2` polimento e `P3` extensão. Não ignore dependências para atender uma prioridade. `Attempts` é contador não negativo; tarefas decompostas recebem novos IDs e explicação, sem apagar o histórico do problema.

`Evidence` de `done` deve dizer quais critérios foram satisfeitos e quais verificações ocorreram. O verificador pode exigir conteúdo, mas não demonstra a veracidade dele: o orquestrador precisa conferir resultados reais. Hash de commit pode constar no log de lote/final, evitando a referência circular de gravar dentro do commit seu próprio hash.

## Reserva de caminhos

Paths relativos à raiz, separados por ponto e vírgula, com `/`. Aceita arquivo exato ou subárvore terminada em `/**`. Não aceita caminhos absolutos, `..`, `.git`, glob genérico, nomes reservados do Windows, componentes terminados em ponto/espaço ou expansão de shell. `none` representa conjunto vazio. Para uma tarefa de hardware, pode haver `Writes: docs/validation/target.md` porque o resultado inclui um relatório, mesmo sem mudanças de código.

Colisões são conservadoras e ignoram diferença de caixa para preservar segurança em Windows: `pkg/**` conflita com `pkg/a.py`; dois arquivos distintos na mesma pasta não conflitam por si só. Renomear exige reservar origem e destino. `Writes(A)` não pode intersectar `Writes(B)` nem `Reads(B)`, e vice-versa.

Junctions, symlinks, hardlinks e aliases como nomes curtos podem apontar caminhos textualmente distintos ao mesmo arquivo. O helper não resolve o filesystem: o orquestrador deve verificar a raiz e os alvos reais antes de reservar, serializando aliases ou substituindo-os por um caminho canônico comum.

`Reads` deve incluir contratos e módulos efetivamente usados. Leituras amplas podem serializar demais; prefira fronteiras explícitas. Path ownership não substitui a análise de contrato, recursos de sistema, operações de Git, geração de lockfiles ou edição do mesmo dispositivo.

`TODO.md`, `AGENTS.md` e contratos compartilhados são coordenados pelo orquestrador. Um worker não altera esses arquivos ainda que uma descrição ampla de diretório os inclua por acidente.

## Helper somente leitura

```text
python <skill>/scripts/todo_graph.py validate --todo <repo>/TODO.md
python <skill>/scripts/todo_graph.py plan --todo <repo>/TODO.md --scope mvp --team-slots 4 --max-workers 4
python <skill>/scripts/todo_graph.py report --todo <repo>/TODO.md --scope mvp
```

`--team-slots` é a capacidade total efetivamente permitida para esta árvore, incluindo raiz e agentes já existentes. Padrão 1 é conservador e não oferece despacho paralelo. `--max-workers` aceita 0–4. O plano desconta donos ativos que não sejam `root`, respeita as reservas existentes e indica tarefas prontas não selecionadas. Confirme capacidade da ferramenta também: agentes vivos sem tarefa no TODO e revisores avulsos não podem ser inferidos pelo arquivo.

O helper valida IDs, metadados, paths, referências, ciclos, estado de dependências, evidência mínima e conflitos entre reservas ativas. Não modifica o backlog, não cria agentes, não executa código do texto e não autoriza ações. Retorna código 0 para grafo válido e 2 para entrada inválida.
