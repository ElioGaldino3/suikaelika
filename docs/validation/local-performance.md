# Desempenho local

## Ambiente e método

Medição feita em 20/10/2026 no Windows 11 (build 10.0.26300), AMD64, CPython 3.13.16, Pygame 2.6.1 e SDL 2.28.4. O harness usa SDL `dummy`, janela lógica de 1280×720, seed fixa, 30 quadros de aquecimento e cronometra 1.200 quadros por cenário. Não acessa display físico, GPU, áudio ou joystick.

Comando da medição de renderização longa:

```powershell
python tools/performance.py --frames 1200 --warmup 30 --render-only
```

Comando que inclui renderização e os cenários de física de 24, 120 e 400 corpos:

```powershell
python tools/performance.py --frames 400 --warmup 30
```

O harness imprime JSON e aceita `--output caminho.json` para salvar um relatório. Tempos reportados são por callback/quadro, com percentis nearest-rank aproximados por índice arredondado. A instrumentação de `tracemalloc` fica ativa durante os quadros medidos e pode afetar os tempos; compare resultados com a mesma configuração e máquina.

## Cenários de renderização

| Cenário | Corpos/frutas | p50 ms | p95 ms | p99 ms | Máximo ms | Delta Python | Pico Python | Working set inicial → final |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Partida normal atual | 24 | 6,0602 | 7,0201 | 9,5477 | 11,6059 | 38 KB | 42 KB | 59,05 → 58,52 MB |
| Referência do PROJECT | 150 | 12,1703 | 13,0871 | 18,2144 | 25,1104 | 36 KB | 55 KB | 58,57 → 58,90 MB |
| Estresse de renderização e efeitos | 120 + 3 fusões/quadro | 12,8884 | 14,2423 | 17,9528 | 21,6453 | 334 KB | 349 KB | 58,91 → 59,47 MB |
| Sobreposição de pausa | 24 | 7,3384 | 8,2252 | 10,3934 | 11,5991 | 36 KB | 39 KB | 59,62 → 59,67 MB |

Delta e pico Python são leituras de `tracemalloc`, não RSS. O pico de working set do processo durante esta execução foi 63,32 MB; a memória privada final do processo variou de 39,7 a 40,9 MB entre cenários. A estimativa estática das superfícies SDL do renderer foi 20.164.580 bytes. Ela soma `pitch × altura` das superfícies conhecidas e não inclui todas as alocações internas de SDL, Pygame, fontes, Pymunk ou Python.

O cenário de 150 frutas representa a quantidade de referência mencionada em `docs/PROJECT.md`; o cenário normal medido continua com 24 corpos. A configuração de estresse produziu o limite de 128 partículas. Esses cenários são sintéticos e não executam uma rodada física junto com a renderização.

## Física isolada

Medição de 400 quadros e 30 de aquecimento, com `space.step(1/120)` por quadro. Os corpos são criados em grade e permanecem ativos; os valores não representam uma partida típica.

| Cenário | Corpos | p50 ms | p95 ms | p99 ms | Máximo ms |
|---|---:|---:|---:|---:|---:|
| Normal atual | 24 | 0,8470 | 0,8978 | 1,0893 | 1,6114 |
| Estresse | 120 | 4,4343 | 5,2858 | 5,6767 | 7,0073 |
| Diagnóstico do PROJECT | 400 | 22,4355 | 29,5579 | 40,8647 | 51,3795 |

O passo de simulação de 120 Hz tem orçamento de 8,33 ms. O caso diagnóstico de 400 corpos excedeu esse orçamento já no p50; o p95 foi 29,56 ms. O resultado justifica manter 400 como cenário de diagnóstico e não como expectativa de jogo fluido. Não foram alterados física, sorteio, regras ou pontuação.

## Gargalos e alterações

Antes das alterações, um perfil local de 400 quadros identificou `pygame.transform.smoothscale` de quadro completo como o maior custo observado, em torno de 4 ms e 31% do tempo acumulado do perfil. A apresentação criava a superfície de saída da escala repetidamente. O overlay de pausa/fim também alocava e preenchia uma superfície alfa de 1280×720 a cada quadro.

O renderer agora mantém uma superfície de destino para a escala e uma superfície de véu pré-preenchida para overlays. Em microbenchmark local, fornecer `dest_surface` ao `smoothscale` reduziu a mediana de aproximadamente 3,24 ms para 2,72 ms. A medição longa atual do cenário normal ficou em p50 6,06 ms; a coleta inicial anterior à otimização havia marcado 6,46 ms em 400 quadros. Como duração, aquecimento e carga variam, essa diferença não é uma estimativa controlada de ganho. A otimização evita a alocação recorrente observada; o benchmark não demonstra uma melhoria estável de FPS.

O histórico de 1.200 quadros após a alteração manteve superfícies SDL com tamanho fixo; o working set por cenário variou aproximadamente entre 58,5 e 59,5 MB, com pico de processo em 63,3 MB. Não foi feita uma execução de 30 minutos e esses números não provam ausência de vazamento.

## Memória e limites

- `tracemalloc`: bytes de alocações rastreadas pelo alocador Python durante cada cenário; não mede buffers nativos de Pygame, SDL ou Pymunk.
- Windows PSAPI: `WorkingSetSize` é o working set residente (RSS aproximado) no início e fim de cada cenário; `PeakWorkingSetSize` é pico do processo até aquele ponto. `PrivateUsage` informa memória privada comprometida, não RSS.
- Superfícies SDL: soma estimada de `Surface.get_pitch() × Surface.get_height()` para superfícies mantidas pelo renderer, separada das duas métricas anteriores.

Os dados são do host Windows com backend de vídeo `dummy`. Não representam execução com compositor, display, GPU, controle físico ou áudio. Nenhuma medição foi realizada no Batocera v43 ou no notebook x86 do usuário. O teste de 150 frutas, o teste de 400 corpos e os limites de memória precisam ser repetidos no aparelho alvo antes de homologar desempenho ou definir um requisito mínimo.
