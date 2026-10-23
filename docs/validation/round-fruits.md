# Validação das sprites circulares — 23/10/2026

Pedido: recriar individualmente as onze frutas com um subagente, padronizar os
PNGs em 512×512 e fazer a silhueta acompanhar a colisão circular.

## Resultado

Onze chamadas individuais à ferramenta integrada `image_gen`, sem CLI/API externa.
As saídas RGBA 1254×1254 foram empacotadas com:

```powershell
.\.venv\Scripts\python.exe tools/process_art_assets.py --fruit-source work/round-fruits
```

Comando concluído com código 0. Todos os PNGs finais têm 512×512, o mesmo alpha
por pixel, interior opaco e círculo de raio 248 centrado em (256,256).
A margem transparente é de 8 pixels. Folhas, cabos e coroas ficam dentro do corpo.
O pequeno resíduo isolado da geração do abacaxi foi eliminado pela máscara final.

O carregamento usa dimensões pares para evitar deslocamento de meio pixel.
Nos onze raios padrão do catálogo, a maior diferença radial entre contorno visível
e raio físico foi **1,019 pixel**, medida com alpha acima de 32.

[Prévia das onze frutas](../art/round-fruits-preview.png).
[Prompts completos e SHA-256 dos PNGs finais](../art/round-fruits-prompts.json).

## Verificações executadas

| Comando | Resultado |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests/rendering -q` | 60 passaram |
| `.\.venv\Scripts\python.exe -m pytest -q` | 320 passaram; 1 falha preexistente |
| `.\.venv\Scripts\python.exe -m ruff check` | Passou |
| `.\.venv\Scripts\python.exe -m mypy` | Passou, 46 fontes |
| `git diff --check` | Passou |

A falha preexistente é
`tests/scenes/test_navigation.py::test_collider_menu_adjusts_apple_and_saves_the_scale`:
espera 105% após um ajuste, mas recebe 101%. Já estava registrada no TODO e foi
reproduzida antes da troca das sprites. Nenhum código de navegação foi alterado.
Os dez testes originais de assets passaram antes da implementação.

Também foram inspecionadas a galeria final e imagens do renderer real no clássico
e na batalha, com rotação e hitboxes visíveis. As duas capturas locais ficam em
`work/round-fruits-classic-debug.png` e `work/round-fruits-battle-debug.png`.

## Limites

Verificação local de pixels, superfícies e renderização. Não houve execução em
Batocera ou Android TV físico, nem homologação de joystick/áudio. Os ajustes
manuais de hitbox já salvos pelo jogador continuam tendo seu comportamento
anterior; a correspondência acima foi medida com os raios padrão do catálogo.
