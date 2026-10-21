# Arte fornecida para o protótipo

O processamento reproduzível é feito com `python tools/process_art_assets.py`
no ambiente de desenvolvimento com Pygame instalado. A folha `raw_assets/frutinhas_v2.png`
tem 1536×1024 pixels e transparência por pixel; o script a usa sem reamostrar
os recortes. Os arquivos de entrada em `raw_assets/` ficam intactos. As células
seguem a ordem do catálogo, ignoram apenas o halo quase invisível ao calcular
os limites e mantêm os pixels originais com alpha dentro da caixa recortada.
Os PNGs são salvos sem compressão com perda.
Os cenários são ajustados para preencher o canvas lógico 1280×720, com corte
central e preservação da proporção.

| Nível | ID do catálogo | Desenho na folha |
|---:|---|---|
| 1 | `cherry` | cereja, superior 1 |
| 2 | `strawberry` | morango, superior 2 |
| 3 | `grape` | uva, superior 3 |
| 4 | `lemon` | limão amarelo, superior 4 |
| 5 | `apple` | maçã, superior 5 |
| 6 | `orange` | laranja, superior 6 |
| 7 | `pear` | pera, inferior 1 |
| 8 | `peach` | pêssego, inferior 2 |
| 9 | `pineapple` | abacaxi, inferior 3 |
| 10 | `melon` | melão, inferior 4 |
| 11 | `watermelon` | melancia, inferior 5 |

Os sprites originais variam em proporção e escala. O jogo preserva a proporção,
centraliza cada desenho dentro do envelope visual correspondente ao raio do
catálogo e mantém as superfícies em cache. Os PNGs gerados são os recursos de
runtime; a folha original não é necessária na instalação.

`assets/backgrounds/menu.png` vem de `raw_assets/background_menu.png` e
`assets/backgrounds/gameplay.png` vem de `raw_assets/background_jogo.png`.
Ambos são exibidos preenchendo a tela; o menu recebe um painel translúcido para
manter o texto legível. Se os diretórios processados não estiverem disponíveis,
a renderização mantém o fallback procedural anterior.

**Limitação do recorte:** a separação usa células fixas porque a folha não tem
guias. A nova imagem aproxima algumas sombras nas linhas inferiores; os limites
foram posicionados entre os pixels opacos para não misturar as frutas vizinhas.
Confira os PNGs individuais antes de substituir a arte fonte ou alterar a
composição da folha.
