# Auditoria local de fusões e desempenho

**Data:** 22/10/2026
**Escopo:** `SE-044` — diagnóstico local reproduzível; não é homologação do Batocera.

## Como reproduzir

Na raiz do projeto, execute os cenários naturais e o soak completo:

```powershell
.venv\Scripts\python.exe tools/performance.py --frames 30 --warmup 5 --full-scenarios --soak-seconds 300 --output .local/performance-full.json
```

O comando executa quatro perfis em cada modo, compara gravação em memória com JSON durável, mede o acumulador do `App`, inicializa o mixer SDL e mantém um renderizador durante ao menos cinco minutos ativos por modo. Os tempos são medidos nesta máquina; `--soak-seconds` pode ser reduzido para depuração.

Para comparar efeitos visuais com a mesma cena e a mesma quantidade de frutas:

```powershell
.venv\Scripts\python.exe tools/performance.py --frames 300 --warmup 30 --render-only --output .local/render-comparison.json
```

Os arquivos JSON ficam em `.local/`, fora do histórico do Git. O relatório abaixo registra os resultados obtidos em execução completa e a comparação controlada do renderizador.

## Máquina e limites da medição

- Windows 11 x64; CPython 3.14.7; 12 processadores lógicos; processador identificado pelo runtime como `Intel64 Family 6 Model 151 Stepping 2, GenuineIntel`.
- pygame-ce 2.5.8; Pymunk 7.3.1; SDL 2.32.10; tela 1280×720.
- SDL de vídeo e áudio em modo `dummy`. O desenho usa superfícies Pygame, sem validar GPU física. O mixer Pygame inicializou e consumiu eventos no driver dummy, sem validar HDMI, alto-falantes ou latência do Batocera.
- Orçamento de referência: 16,67 ms por quadro a 60 FPS. A simulação usa passo fixo de 8,33 ms. Como o equipamento que apresenta as travadas não foi usado, o resultado local não estabelece limites homologados para ele; essa prova continua em SE-052.

## Cenários reproduzíveis

Cada replay envia `InputFrame` reais para `GameSession` ou `BattleSession`, com física Pymunk. Só conta chamadas executadas; ao game over ou fim da batalha, o replay termina imediatamente.

| Modo e cenário | Seed e ações | Passos e resultado observado |
| --- | --- | --- |
| Clássico — fusão isolada | seed 0; launcher neutro em x=400; DROP nos passos 0 e 120 | 360 passos; 2 frutas aceitas; 1 fusão; pico de 2 frutas |
| Clássico — cascata | seed 4417; x=400; DROP a cada 42 passos | 391 passos; 10 quedas; fusões nos passos 324 e 330; a fruta criada no passo 324 foi consumida 6 passos depois |
| Clássico — pilha densa | seed 4417; `move_x=((tick*17+4417)%121)/60-1`; DROP a cada 42 passos | 7.200 passos; 172 quedas; 135 fusões; pico de 42 frutas; score 1.104 |
| Clássico — partida longa | mesmas ações da pilha densa até game over | 14.690 passos / 122,4167 s ativos; 346 quedas; 287 fusões; pico de 60 frutas; score 2.531; game over natural |
| Batalha — fusão isolada | seed 2; ambos neutros em x=240; DROP a cada 90 passos | 180 passos; cada tabuleiro aceitou 2 quedas e teve 1 fusão; pico de 2 frutas |
| Batalha — cascata | seed 2; ambos neutros em x=240; DROP a cada 90 passos | 662 passos; cada tabuleiro teve 4 fusões; relação pai/filho nos passos 581→601 (20 passos) |
| Batalha — pilha densa | seed 4417; movimento triangular determinístico; DROP a cada 42 passos | 6.822 passos / 56,85 s ativos; cada tabuleiro teve 162 quedas e 124 fusões, pico de 41 frutas; término natural por overflow com 942 pontos |
| Batalha — partida longa | mesmas ações até a batalha terminar | Mesmo término natural por overflow aos 6.822 passos; não são acrescentados passos após o terminal |

Em cada tabuleiro, o contador de chamadas a `GameSession.step` coincide com os passos do replay. Os resultados da batalha são medidos por jogador, pois os IDs de fruta começam novamente em cada tabuleiro.

## Medições e achados

### Simulação, física e fusões

- Na partida clássica longa, o tempo de `GameSession.step` teve p50/p95/p99 de 0,837/1,292/1,832 ms; física, 0,394/0,621/0,696 ms; `MergeSystem.resolve`, 0,084/0,130/0,911 ms. O pico de contatos permaneceu baixo.
- Na pilha densa clássica, `GameSession.step` teve p50/p95/p99 de 0,642/0,927/1,361 ms; na batalha densa, o tabuleiro mais lento ficou em 0,648/0,952/1,577 ms.
- Uma execução registrou um pico isolado de 61,5 ms dentro de `MergeSystem.resolve`, também presente com persistência em memória. Ele não se repetiu no replay longo com a mesma seed: p99 de 0,873 ms, máximo de 3,911 ms e nenhuma chamada acima do passo fixo de 8,33 ms. O pico não sustenta uma causa determinística na resolução de fusões; precisa ser correlacionado com quadros e pausas do GC no equipamento de referência.

### Persistência de recorde

O mesmo replay clássico (seed 4417, 14.690 passos, score 2.531) foi executado abaixo e acima do recorde anterior, com stub em memória e com `JsonPersistence` real em diretório temporário. A gravação JSON percorre serialização, `flush`/`fsync`, cópia de backup e substituição atômica.

| Caso | Backend | Salvamentos | p50/p95/p99 por salvamento | p99 de `GameSession.step` |
| --- | --- | ---: | ---: | ---: |
| Abaixo de 100.000 pontos | Memória | 1 | 0,001/0,001/0,001 ms | 1,684 ms |
| Abaixo de 100.000 pontos | JSON durável | 1 | 3,839/3,839/3,839 ms | 1,708 ms |
| Acima de 0 pontos | Memória | 283 | 0,001/0,001/0,001 ms | 1,711 ms |
| Acima de 0 pontos | JSON durável | 283 | 3,530/4,194/4,352 ms | 5,440 ms |

Os arquivos recarregaram sem erro. No host local, uma gravação durável em cada fusão recordista acrescentou aproximadamente 3,5–4,4 ms por chamada e elevou o p99 de passo para 5,44 ms; o máximo do passo foi 8,72 ms. É custo síncrono mensurável, mas não explica sozinho os picos isolados de dezenas de milissegundos. Armazenamento mais lento no aparelho ainda pode mudar o resultado.

**Achado de correção para SE-047:** quando a partida supera o recorde, a duração persistida para a nova pontuação ficou em 121,525 s, embora o game over tenha ocorrido em 122,4167 s (diferença de 0,8917 s). A partida abaixo do recorde preservou os 91,25 s do registro anterior, como esperado. A atualização final precisa manter a duração total da partida recordista segundo a regra decidida pelo usuário.

### Renderização, efeitos e áudio

Comparação controlada de 300 quadros, mesmos 120 frutos, mesmo snapshot, mesmo estado de jogo e mesmo caminho de desenho:

| Variante | p50 | p95 | p99 | Máximo |
| --- | ---: | ---: | ---: | ---: |
| Sem efeitos | 5,706 ms | 6,006 ms | 6,081 ms | 6,178 ms |
| Três eventos de fusão por quadro | 7,061 ms | 7,370 ms | 7,615 ms | 8,623 ms |

Os efeitos acrescentaram 1,364 ms ao p95 neste host. A inicialização dos renderizadores levou 109,7 ms no clássico e 133,4 ms na batalha; esse custo cobre o construtor e a criação/carregamento das superfícies usadas, não é custo por quadro nem uma medição isolada de leitura de arquivos.

No replay de cascata, `PygameAudioManager` com mixer SDL dummy ficou em p50/p95/p99 de 0,0004/0,0005/0,0093 ms por `consume`, máximo de 0,0353 ms. O stub silencioso ficou abaixo de 0,0014 ms no máximo. Isso só mede o caminho do mixer dummy.

### Acumulador, memória e sessão longa

- O acumulador real do `App` processou 240 passos em 120 quadros regulares a 60 FPS e 330 passos com intervalos irregulares, sem descartar backlog. Um quadro de 500 ms foi limitado a 250 ms, processou no máximo 8 passos e descartou 22 passos acumulados; o resto do acumulador ficou abaixo de 8,33 ms.
- No soak clássico, o renderizador permaneceu vivo por 367,25 s ativos em 3 partidas completas. Na batalha, por 341,1 s em 6 partidas completas. Os tetos observados se mantiveram: rotações 128/128, partículas até 13/128, eventos de efeitos 512/512, 5 superfícies pequenas e 11 sprites de frutas. A estimativa de superfícies ficou em 23,9–24,7 MB no clássico e 27,8–28,5 MB na batalha (inclui fundo, recipiente e painel próprios da batalha), sem crescimento dos caches entre as amostras por rodada.
- O RSS terminou em 181,7 MB após o soak clássico e 179,2 MB após o soak de batalha; o pico do processo durante a execução foi 258,2 MB. O uso privado final foi 167,6 MB e 165,1 MB, respectivamente. São amostras do processo inteiro no Windows, não apenas do jogo.
- O harness observou 156 pausas de GC no clássico (p95 1,63 ms, máximo 125,82 ms) e 260 na batalha (p95 1,83 ms, máximo 143,28 ms). O próprio harness mantém `tracemalloc` ativo para medir alocações, então esses máximos precisam ser confirmados com a build do jogo sem instrumentação e correlacionados ao tempo de quadro. A variação de alocação Python inclui objetos e relatórios do harness e não é, isoladamente, prova de vazamento.

## Conclusão e próximos passos

Os cenários locais não reproduziram de forma estável um gargalo de fusão acima do orçamento de 16,67 ms. A gravação síncrona de recordes é custo real e repetido quando uma partida supera o recorde; efeitos visuais acrescentam cerca de 1,36 ms ao p95 de desenho neste host. O maior risco ainda por confirmar é a pausa de GC/host registrada no soak e no máximo isolado de uma execução. Não foi aplicada otimização de regras ou de desempenho sem evidência reproduzível.

1. **SE-052:** repetir os perfis na build de referência do Batocera, armazenamento real, vídeo e áudio HDMI, gravando duração de quadro e pausas do GC para confirmar a causa das travadas reportadas.
2. **SE-045:** usar a comparação de 283 gravações para avaliar consolidação durável apenas se o mesmo custo aparecer no aparelho; preservar a recuperação de dados e medir de novo os mesmos cenários.
3. **SE-047:** corrigir o checkpoint final de duração do recorde conforme o achado acima e as decisões de SE-046.

## Verificações executadas

- `python tools/performance.py --frames 30 --warmup 5 --full-scenarios --soak-seconds 300 --output .local/performance-full.json`: terminou com código 0; cobriu 300 s ativos por modo e encerrou cada partida pelo terminal natural.
- `python tools/performance.py --frames 300 --warmup 30 --render-only --output .local/render-comparison.json`: terminou com código 0; 300 amostras por variante de efeitos.
- `python -m pytest tests/tools/test_performance.py`: 9 passaram.
- `python -m pytest --basetemp .local/pytest-tmp-se044`: 318 passaram e 1 falhou em `test_collider_menu_adjusts_apple_and_saves_the_scale`; o teste espera 105%, mas a cena retorna 101%. A mesma falha já existia antes deste lote e não envolve o harness.
- `python -m ruff check tools/performance.py tests/tools/test_performance.py` e `python -m mypy`: passaram; `git diff --check`: passou.
