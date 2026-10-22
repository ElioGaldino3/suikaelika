# Diagnóstico reproduzível de travadas em fusões (SE-044)

## Estado e limite da evidência

Este diagnóstico mede somente o checkout em Windows 11, CPython 3.14.7, Pygame CE 2.5.8 / SDL 2.32.10, display e áudio SDL `dummy`, em CPU AMD64 do host local (modelo não coletado). Não houve acesso ao equipamento do relato, ao Batocera, à Android TV ou a joystick físico. Os tempos abaixo não demonstram nem refutam a travada relatada nesses aparelhos. SE-052 ainda precisa coletar o relatório de `tools/diagnostics.py --format json`, modelo/CPU/RAM/armazenamento/GPU, resolução/refresh, versão do sistema, backend SDL, versão do jogo e carga reproduzida no aparelho.

## Reprodução disponível e lacunas

O harness atual `tools/performance.py` permite repetir carga normal de render com 24 frutas, render de referência com 150 frutas, estresse visual com 120 frutas e três eventos de fusão por quadro, overlay pausado, e física isolada com 24, 120 e 400 corpos. Comando medido:

```powershell
.venv\Scripts\python.exe tools\performance.py --frames 30 --warmup 2
```

Além das cargas isoladas, o harness roda 2.400 passos (20 s simulados) em `GameSession` e `BattleSession`, seed `4417`, DROP a cada 42 passos, `move_x=((tick*17+seed)%121)/60-1`. Conta fusões emergentes e mede `step` e snapshot separadamente. No helper de 2.400 passos, os resultados foram:

| Modo | fusões | step p50/p95/p99/máximo ms | snapshot p50/p95/p99/máximo ms |
|---|---:|---|---|
| Clássico | 31 | 1,183 / 2,046 / 3,410 / 13,158 | 0,077 / 0,116 / 0,144 / 0,234 |
| Batalha (dois tabuleiros) | 32 | 2,001 / 4,063 / 4,669 / 20,706 | 0,112 / 0,188 / 0,213 / 0,344 |

O passo integrado de batalha excedeu 16,67 ms uma vez, sob tracemalloc; p99 foi 4,669 ms. A medição não inclui App accumulator, renderer nem SDL events, então não representa um quadro completo.

`MergeSystem.resolve` foi medido isoladamente sobre frutas sintéticas sobrepostas: 2 frutas (unitária), 10 (“cadeia”) e 32 (densa), com 15/15/5 chamadas. Na primeira coleta, máximos foram 3,343 / 74,559 / 220,653 ms; na execução final o cenário denso teve máximo 223,566 ms. A entrada artificial congestionada é repetida por chamada e não constitui cascata física sequencial nem resultado de gameplay; o rótulo cadeia descreve a forma da entrada, não uma cadeia confirmada.

Comparação de `_save_record`: 120 chamadas com scores 900/recorde 1000 e 1100/1000. Na execução final, stub em memória: abaixo p50/p95/p99/máx 0,0018/0,0020/0,0039/0,0071 ms; acima 0,0018/0,0019/0,0028/0,0062 ms. Isso mede lógica, sem JSON, filesystem ou flush. Áudio real não foi isolado; efeitos usam eventos sintéticos. Sessão longa: 1.200 passos (10 s simulados), 249,570 ms de parede, 2 pausas GC totalizando 0,291 ms (máxima 0,178 ms), 16 frutas no fim e RSS 87,9 MB. Sem renderer/cache no perfil longo; cache = não aplicável.

## Resultados medidos

Valores por callback/quadro, milissegundos. Orçamento de referência: 16,67 ms por quadro a 60 Hz. `p50/p95/p99/máximo`:

| Carga isolada | p50 | p95 | p99 | máximo | alocação Python pico | partículas | orçamento no máximo |
|---|---:|---:|---:|---:|---:|---:|---:|
| Render, 24 frutas | 3,619 | 4,034 | 4,084 | 4,084 | 4.200 B | 0 | 24,5% |
| Render, 150 frutas | 6,125 | 6,383 | 6,592 | 6,592 | 18.784 B | 0 | 39,6% |
| Render, 120 frutas + efeitos | 7,803 | 8,261 | 8,703 | 8,703 | 90.410 B | 128 | 52,2% |
| Overlay pausado | 3,993 | 4,179 | 4,187 | 4,187 | 3.528 B | 0 | 25,1% |
| Física, 24 corpos | 0,559 | 0,596 | 0,637 | 0,637 | 7.456 B | — | 3,8% |
| Física, 120 corpos | 3,255 | 3,399 | 4,152 | 4,152 | 34.840 B | — | 24,9% |
| Física, 400 corpos | 11,063 | 11,415 | 11,587 | 12,086 | 119.896 B | — | 72,5% |

O comando completo roda também os cenários integrados e o perfil de 10 s descritos acima. `tracemalloc` mede alocações Python, não alocações nativas SDL/Pymunk. O renderer sintético inclui cache já aquecido; não mede cache frio.

## Auditoria por hipótese

| Área | Estado | Evidência / próxima medição |
|---|---|---|
| Loop e acumulador | hipótese aberta | `App.run` usa `Clock.tick`, lê eventos, limita delta e avança simulação em passos fixos; não há decomposição temporal por estágio nem contagem de passos/quadro no harness. |
| Física e contatos | parcialmente medido | `PhysicsWorld.step` isolado: 24/120/400 corpos conforme tabela. Contatos Pymunk, `poses`, construção dos mapas e callbacks precisam ser cronometrados separadamente. |
| Resolução de fusão | parcialmente medida | `MergeSystem.resolve` sintético e passo integrado com fusões emergentes; não é cascata determinística de gameplay. |
| Snapshots | medido | `GameSession.snapshot`/`BattleSession.snapshot` cronometrados à parte no roteiro seed 4417. |
| Render/cache | medido parcialmente | renderer normal/efeitos e cache aquecido; comparar primeiro quadro/cache frio e escala/resolução do aparelho. |
| Partículas | medido parcialmente | workload sintético com três eventos de merge por callback atinge 128 partículas; comparar efeitos reduzidos e desligados sem alterar outras variáveis. |
| Áudio | não isolado | mixer não foi medido; comparar habilitado/silenciado em host e aparelho, registrando driver/saída. |
| Assets | não isolado | harness usa renderer existente e assets carregados; carga a frio e cache de superfície devem ser separados. |
| Alocações/GC | parcial | alocações Python por cenários e pausas GC em sessão curta; sem checkpoints contínuos ou memória nativa/cache da sessão longa. |
| Persistência/recorde | lógica medida | comparação abaixo/acima usa stub em memória; filesystem e serialização não incluídos. |

## Achados, descartes e prioridade

**Comprovado neste host:** física sintética com 400 corpos chega a 72,5% do orçamento em `step()` isolado; render sintético com efeitos chega a 52,2%. O `BattleSession.step` integrado teve máximo 20,706 ms e excedeu o orçamento, mas essa amostra foi medida sob tracemalloc e sem renderização. O resolver denso artificial alcançou 223,566 ms; não prova que uma cascata normal cause travada.

**Descartado somente para estes workloads e este host:** atualização lógica do recorde em memória não se aproxima do orçamento. I/O real, áudio, renderer dentro do mesmo quadro, driver e aparelho não foram descartados. Nenhuma causa foi causalmente confirmada.

Ainda falta replay de ações que produza especificamente fusão única, cascata natural, pilha densa e sessão longa em cada modo. Também falta quadro integral com App accumulator, áudio real, I/O real, série de RSS/cache, A/B de efeitos/desenho e execução no hardware reportado. O dado local não identifica causalidade nem autoriza correções de gargalo (SE-045).

## Verificações e documentação

Baseline amplo: `.venv\Scripts\python.exe -m pytest -q` no sandbox restrito terminou código 1: **249 passed, 1 failed, 52 errors**. As 52 falhas de setup vieram da criação do diretório numerado do `tmp_path` fora da raiz gravável do workspace. Depois de autorizar a escrita temporária fora do workspace, a mesma suíte terminou código 1: **301 passed, 1 failed, 0 errors em 10,85 s**. A falha remanescente é `tests/scenes/test_navigation.py::test_collider_menu_adjusts_apple_and_saves_the_scale`: o teste espera `Maçã: 105%`, mas a implementação retorna `Maçã: 101%` após um quadro de entrada horizontal.

Verificação focada nesta tentativa: `.venv\Scripts\python.exe -m pytest -q tests\game\test_merging.py tests\game\test_session.py tests\game\test_battle.py` terminou código 0: **30 passed**. `.venv\Scripts\ruff.exe check tools/performance.py tools/diagnostics.py` terminou código 0. `.venv\Scripts\mypy.exe` terminou código 0: **Success: no issues found in 46 source files**; uma falha de mypy reportada na primeira coleta não se reproduziu com o executável configurado na `.venv`. `.venv\Scripts\python.exe tools\performance.py --frames 30 --warmup 2` terminou código 0 e incluiu os workloads listados acima. `.venv\Scripts\python.exe tools\diagnostics.py --format json` terminou código 0, runtime Windows 11 AMD64, Pymunk 7.3.1; as sondagens SDL/display/audio/joystick são declaradas não executadas.

Context7: resolvido Pygame como `/pygame/pygame`; consultada a documentação de `pygame.time.Clock.tick` e `pygame.time.get_ticks`. A referência descreve retorno de milissegundos e aviso de precisão de `SDL_Delay`; logo, `Clock.tick` serve ao pacing, mas medições finas deste harness usam `time.perf_counter_ns`.

Fontes: [Pygame time API](https://www.pygame.org/docs/ref/time.html) e [documentação Context7 de Pygame](https://github.com/pygame/pygame/blob/main/docs/reST/ref/time.rst).
