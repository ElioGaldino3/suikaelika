# SE-048 — Entrada de nome no Batocera

**Estado:** investigação documental concluída; a integração nativa não está demonstrada.
**Alvo do projeto:** processo Pygame iniciado pelo EmulationStation (página Batocera Pygame consultada em 22/10/2026; a própria página avisa que precisa de atualização). A versão efetiva de Batocera/Python/Pygame/SDL no aparelho ainda não foi registrada.

## Decisão

Para SE-049, implementar um teclado virtual dentro do jogo, navegável pelo joystick, a menos que um teste no Batocera alvo prove um serviço de teclado virtual invocável pelo processo Pygame e com retorno confiável ao jogo. Não tratar o teclado virtual de EmulationStation, os menus de emuladores/libretro, `padtokeyboard` ou Evmapy como tal serviço.

Essa recomendação não afirma que o Batocera seja incapaz de exibir teclado virtual. As fontes comprovam teclados e mapeamentos em contextos específicos, mas não documentam uma API para um aplicativo Pygame externo abrir, controlar e receber texto de um teclado global do sistema.

## Evidências e limites

| Fonte primária | O que prova | Limite para este jogo |
|---|---|---|
| [Batocera Wiki — sistema Pygame](https://wiki.batocera.org/systems:pygame), consultada em 22/10/2026; página identifica ROMs `.pygame`, pasta `/userdata/roms/pygame` e configurações `pygame.videomode`, `pygame.ratio`, `pygame.padtokeyboard`, `pygame.decoration`; avisa que precisa de atualização | Pygame é executado como sistema/ROM do Batocera e há configuração para traduzir pad em teclado | Não descreve chamada para teclado virtual de texto, foco/modalidade, eventos de confirmação/cancelamento, acentos ou callback ao processo. A página é explicitamente desatualizada; não fixa uma versão suportada do runtime |
| [Batocera Wiki — controles/teclado](https://wiki.batocera.org/supported_controllers#keyboard), consultada em 22/10/2026 | EmulationStation tem bindings para o teclado físico; Batocera não trata teclado como controle e seu gerador de configuração de controles não é aplicado a ele | Trata do teclado físico e da navegação/configuração do EmulationStation; não é uma API de composição de texto para o jogo |
| [Batocera Wiki — Evmapy](https://wiki.batocera.org/evmapy), consultada em 22/10/2026; [wiki — pad remapping](https://wiki.batocera.org/remapping_controls_per_emulator) | Evmapy pode traduzir eventos de controle em eventos de tecla; pad-to-key é configurado para um sistema/jogo | Emite teclas para o aplicativo. Não exibe uma grade de caracteres, não entrega uma string Unicode escolhida pelo jogador e não documenta uma API de abertura/foco/retorno para Pygame. Pad-to-keykeyboard não resolve digitação de nomes |
| [Batocera Linux — launcher Pygame atual](https://github.com/batocera-linux/batocera.linux/blob/master/python-src/batocera-launch/batocera_launch/emulators/pygame.py) | O fluxo conhecido inicia o comando `pygame <rom>`; o launcher do projeto chama seu `main.py` dentro do pacote | O código do launcher é mutável e não prova a ausência de ferramentas adicionais numa imagem instalada. Não mostra protocolo para pedir teclado de texto ao EmulationStation |
| [Pygame 2.6.0 — `pygame.key.start_text_input`](https://www.pygame.org/docs/ref/key.html#pygame.key.start_text_input), documentação oficial atual consultada em 22/10/2026 | Desde Pygame 2.0.0, `start_text_input()` ativa eventos `TEXTEDITING`/`TEXTINPUT`; a documentação diz que pode mostrar teclado/IME “if applicable”. `stop_text_input()` encerra essa entrada e pode ocultar a interface se ela foi exibida | Eventos de texto Unicode são úteis se caracteres chegam ao SDL, mas a ressalva “se aplicável” não garante teclado visual em Linux/Batocera, navegação por joystick, foco, confirmação/cancelamento, acentos, nem voltar ao processo. A versão Pygame/SDL empacotada no aparelho é desconhecida |
| [SDL Wiki — práticas de entrada de texto](https://wiki.libsdl.org/SDL3/BestKeyboardPractices) (SDL 3) e [SDL_StartTextInput](https://wiki.libsdl.org/SDL3/SDL_StartTextInput) | SDL recomenda eventos de texto em vez de decompor digitação em teclas; o início da entrada mostra teclado/IME somente em algumas plataformas | É documentação SDL 3, não prova qual versão SDL o Pygame do Batocera usa nem que há suporte a teclado de tela em Linux Batocera. Não usar a referência SDL 3 para inferir suporte do SDL2 do aparelho |

O Context7 foi consultado para Pygame e SDL conforme a regra do projeto. A página SDL retornada foi SDL 3; portanto, ela serve apenas para explicar a distinção entre eventos de texto e UI de plataforma, não para afirmar compatibilidade SDL2. A fonte aplicável ao código é a API Pygame, cujo comportamento de UI também é condicional.

## Distinção de fluxos

EmulationStation é o frontend que inicia a ROM; menus e teclados vistos nesse frontend pertencem à interface do frontend ou a emuladores com integração própria. O pacote do projeto, em contraste, inicia o processo Python/Pygame (ver `docs/BATOCERA.md` e `packaging/batocera/pygame/main.py`). `padtokeyboard`/Evmapy produzem eventos de teclado dentro do fluxo de entrada do jogo; não há evidência de que invoquem a interface de busca/configuração do EmulationStation. Um teclado virtual de C64/libretro é igualmente específico ao emulador e não é uma API de sistema para a ROM `.pygame`.

No código atual, navegação de menus já é semântica e orientada por joystick: `InputFrame` inclui navegação vertical e bordas de confirmar/cancelar; `App` compõe e despacha essa entrada. O teclado é apenas fallback explícito de desktop no clássico/menu (`--desktop`), e a batalha usa dois controles. A tela de entrada de nome futura deverá usar o mesmo controle nativo, sem depender de teclado físico ou pad-to-key.

## Requisitos para SE-049

O teclado virtual próprio deve permanecer dentro da janela Pygame e receber navegação/confirmar/cancelar pela interface semântica já existente. Isso dá controle explícito sobre abertura e foco, seleção de letra, confirmação, cancelamento e retorno à cena anterior. A composição de caracteres e o conjunto de caracteres (incluindo acentos do português) devem ser definidos e validados em SE-049; não se deve alegar suporte a composição IME somente com base em `KEYDOWN`. `TEXTINPUT` é apropriado quando disponível para entrada Unicode por teclado externo, mas não substitui a interface navegável por controle.

| Ação | UI Pygame + joystick (recomendação) | API nativa Batocera demonstrada? |
|---|---|---|
| Abrir e manter foco | Cena/modal do próprio jogo | Não |
| Navegar por joystick | Ações `nav_up`/`nav_down` e confirmar existentes; horizontal deve ser ligado na UI de nome | Não há rota genérica documentada |
| Confirmar/cancelar | Ações semânticas existentes e retorno explícito à cena anterior | Não há protocolo documentado para a ROM Pygame |
| Acentos | Definir caracteres de nome permitidos; `TEXTINPUT` opcional para teclado externo | SDL/Pygame só descreve eventos e IME condicional; sem suporte de teclado visual provado no alvo |
| Voltar ao jogo | Fechar a UI no mesmo processo, sem trocar de janela/processo | Nenhum contrato de foco/retorno encontrado |

## Prova física que continua pendente

Se houver interesse posterior em integrar um teclado nativo, testar na versão e hardware reais antes de substituir essa decisão: registrar versão/arquitetura de Batocera, Python, Pygame e SDL; iniciar o pacote pelo EmulationStation; disparar a API de texto Pygame e verificar se aparece uma UI; percorrer todos os caracteres somente por joystick; testar confirmar, cancelar e voltar sem perder foco; inserir `á`, `ã`, `ç` e letras maiúsculas; verificar o evento Unicode recebido e que nenhum comando do jogo é acionado; repetir com e sem teclado físico e com as configurações padrão de `padtokeyboard`. Sem uma interface visível com navegação e ciclo completo, manter o teclado virtual próprio.
