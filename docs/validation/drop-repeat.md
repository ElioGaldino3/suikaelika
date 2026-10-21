# Aperto imediato e repetição a 400 BPM

Data: 20/10/2026. Lote SE-041.

## Alterações verificadas

- Removido o cooldown artificial entre apertos de DROP. Cada borda nova faz uma
  tentativa imediata, ainda sujeita à região de nascimento estar livre.
- `drop_held` passa dos adaptadores de teclado/SDL Controller/Joystick para
  InputSample, InputFrame e as cenas de clássico e batalha. Bordas continuam
  consumidas uma única vez; não repetir confirmações de menus.
- HeldDropRepeater por sessão usa tempo fixo de simulação: primeira repetição
  150 ms após o aperto, depois a cada 150 ms, equivalente a 400 BPM.
- Soltar, pausar, retomar ou reiniciar desarma o temporizador. Um botão já segurado
  ao entrar na cena não arma lançamentos; precisa de nova borda de gameplay.
- Tentativas bloqueadas não consomem fruta e não viram rajada quando a boca abre.
- Velocidade vertical inicial de 520 unidades/s libera a boca entre batimentos
  para as frutas sorteáveis, preservando a consulta de sobreposição. Raios,
  pontuação, gravidade e regras de vitória não foram alterados.
- Ruleset padrão classic-v4 separa recordes da regra anterior; arquivos antigos
  foram preservados. Ajuda, README, arquitetura e especificação atualizados.

Context7: resolve-library-id para Pygame e query-docs em `/pygame/pygame` para
estado contínuo versus KEYDOWN/repeat. Referências oficiais:
[teclado](https://www.pygame.org/docs/ref/key.html),
[joystick](https://www.pygame.org/docs/ref/joystick.html).
O estado segurado é lido por get_pressed/get_button. A cadência pertence ao jogo,
sem configurar a repetição de teclas do Pygame/sistema operacional.

## Comandos e evidências

Ambiente existente: Windows, Python 3.14.7, pygame-ce 2.5.8 / SDL 2.32.10,
Pymunk 7.3.1. Não houve instalação/troca de dependências.

| Verificação | Resultado |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | 266 testes passaram |
| `.\.venv\Scripts\python.exe -m ruff check .` | Aprovado |
| `.\.venv\Scripts\python.exe -m mypy` | Aprovado, 46 fontes |
| `.\.venv\Scripts\python.exe skills/todo-orchestrator/scripts/todo_graph.py validate --todo TODO.md` | Aprovado, 7 tarefas |
| `.\.venv\Scripts\python.exe tools/build_batocera.py` | Pacote atualizado |
| Smoke App do pacote, desktop, drivers dummy e frame_limit=2 | Código de saída 0 |
| `git diff --check` | Sem erros |

Os 15 testes novos usam mundos Pymunk reais: nove cenários de cadência (seeds
0/2/31, renderização 30/60/120 FPS), aperto consecutivo em passos adjacentes,
soltura/pausa/retomada, hold de confirmação de menu sem disparo, repetição
bloqueada sem rajada, dois jogadores independentes e teclado com repeat do SO
ignorado. Testes existentes também verificam propagação contínua pelo InputManager,
botões nativos segurados e reset de bordas sem inventar apertos.

Em um segundo smoke a partir de `dist/SuikaElika.pygame/`, a sessão importada do
pacote informou `classic-v4` e em 120 passos registrou quedas em
`[0, 18, 36, 54, 72, 90, 108]`. O intervalo entre elas é exatamente 18/120 s.
Os dois jogadores da batalha tiveram contagens 7 e 2 ao segurar P1 por um segundo
e soltar P2 antes do terceiro batimento.

## Limitações

Colisões podem impedir lançamentos se a boca estiver obstruída; 400 BPM é a
cadência de tentativas, comprovada como quedas efetivas em cestas livres. Apertos
manuais não passam por cooldown, mas também não criam corpos sobrepostos.
Não foram homologados controle físico, Pygame oficial, áudio HDMI, desempenho
em cesta cheia ou execução no Batocera. Essas pendências continuam em SE-038/039.
O arquivo preexistente `raw_assets/jogo.png` permanece fora deste lote.
