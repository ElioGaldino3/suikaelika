# Sprites circulares das frutas

As 11 frutas foram recriadas individualmente com a ferramenta integrada `image_gen`,
por um subagente dedicado, conforme pedido do usuário em 23/10/2026. O conjunto
preserva o estilo de personagens com olhos grandes, sorriso, volume e brilho.
Os prompts completos de cada chamada ficam em [round-fruits-prompts.json](round-fruits-prompts.json).
A [prévia do conjunto](round-fruits-preview.png) e o
[relatório de validação](../validation/round-fruits.md) registram a entrega.

## Padrão dos PNGs de runtime

- Arquivos `assets/sprites/<fruit_id>.png`, todos RGBA **512×512**.
- Corpo circular centrado em **(256,256)**, raio **248**, margem transparente de 8 pixels.
- Interior opaco, borda com antialias e fundo realmente transparente.
- Cabos, folhas e coroas inscritos no corpo; nenhuma projeção fora do círculo.
- Identidade reconhecível por cor, textura e detalhes internos.

| Nível | ID | Identidade dentro do círculo |
|---:|---|---|
| 1 | `cherry` | Cereja vermelha, cabo e folhas internos |
| 2 | `strawberry` | Morango vermelho com sementes e folhas |
| 3 | `grape` | Esfera roxa de uva, folhas internas |
| 4 | `lemon` | Limão amarelo com textura cítrica |
| 5 | `apple` | Maçã vermelha, cabo e folha internos |
| 6 | `orange` | Laranja com poros da casca |
| 7 | `pear` | Pera verde com pintinhas |
| 8 | `peach` | Pêssego rosado com sulco interno |
| 9 | `pineapple` | Abacaxi dourado, losangos e coroa interna |
| 10 | `melon` | Melão verde claro com rede na casca |
| 11 | `watermelon` | Melancia verde com listras escuras |

O runtime continua medindo a distância do contorno opaco ao centro e ajustando-a
ao raio do catálogo, com margem para rotação e superfícies em cache. Agora o
contorno preenche o círculo em todas as direções. As dimensões reduzidas são pares
para manter o centro da imagem alinhado ao centro físico, sem deslocamento de meio
pixel. A opção de ajuste manual de
hitboxes continua tendo seu comportamento próprio; esta troca de arte não altera
os fatores salvos nem o tamanho físico das frutas.

## Empacotamento

Para importar imagens individuais já circulares, com os mesmos onze nomes:

```powershell
python tools/process_art_assets.py --fruit-source work/round-fruits
```

O empacotador valida o conjunto inteiro antes de substituir sprites. Ele recorta
a margem externa, padroniza as dimensões, admite até 10% de ampliação para eliminar
pequenas irregularidades da geração e aplica a mesma máscara circular suave.
Arte alongada ou com falhas no preenchimento é rejeitada para nova geração.
Esse preparo geométrico não desenha nem substitui a ilustração gerada.

As saídas originais desta geração ficam localmente em `work/round-fruits/`, que é
ignorado pelo Git. Os onze PNGs finais são versionados e suficientes para instalar
e jogar; nenhuma ferramenta de IA ou fonte bruta é necessária no aparelho.

`python tools/process_art_assets.py` sem argumentos regenera **apenas os cenários**,
preservando as sprites atuais. Ele requer as fontes locais em `raw_assets/`:
`background_menu.png`, `background_jogo.png` e `battle_background.png`.
Os cenários continuam preenchendo 1280×720 com corte central proporcional.

## Folha histórica

`raw_assets/frutinhas_v3.png` (1448×1086) e os recortes fixos de `FRUIT_CELLS`
permanecem como fontes históricas locais. `process_fruit_sprites` continua disponível
para extrair esses recortes para um diretório escolhido, sem relacioná-los às
dimensões das novas sprites. Não execute essa função sobre `assets/sprites/`.
O fallback procedural continua disponível quando faltam assets instalados.
