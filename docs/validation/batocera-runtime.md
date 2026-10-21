# Runtime Batocera — coleta parcial

**Estado:** bloqueado; dados abaixo ainda não substituem uma coleta no equipamento.

## Informação relatada

Em 20/10/2026, o usuário informou que usa Batocera 43 em um notebook x86 e que o
`python3` está disponível. Esses dados são relato do usuário; não foram medidos
por esta sessão.

O usuário também relatou que scripts Pygame no Batocera usam `pygame.joystick`,
que o mapeamento feito no EmulationStation seria herdado e que os drivers do
sistema operacional dispensariam instalação adicional. Isso ainda não foi
verificado no equipamento. A API `pygame.joystick` apresenta eixos e botões por
índices do dispositivo; a abstração SDL Game Controller oferece controles
semânticos padronizados quando há um mapeamento compatível. Portanto, a
disponibilidade de um controle no sistema não comprova, por si só, qual API ou
qual mapeamento o launcher Batocera entrega ao processo. [Documentação de
pygame.joystick](https://www.pygame.org/docs/ref/joystick.html) e
[documentação de pygame._sdl2.controller](https://www.pygame.org/docs/ref/sdl2_controller.html).

## Diagnóstico local informado

O usuário forneceu uma saída de `tools/diagnostics.py` executada no Windows 11,
em processo CPython 3.13.16 de 64 bits/AMD64. O diagnóstico identificou Pygame
2.6.1, Pymunk 7.3.1, pytest 9.1.1, Ruff 0.17.1 e mypy 1.20.2. SDL, display,
áudio e controles não foram sondados. Este resultado descreve o ambiente local
Windows e não confirma nenhuma versão, ABI ou capacidade do Batocera.

## Dados ainda não coletados

| Campo | Resultado |
|---|---|
| Modelo/revisão do notebook | Pendente |
| Arquitetura exata do sistema e do processo (32/64 bits) | Pendente |
| Versão e implementação do Python | Pendente |
| Pygame, SDL e disponibilidade de importação | Pendente |
| Pymunk e disponibilidade de importação | Pendente |
| ABI/libc e bibliotecas nativas | Pendente |
| Display, resolução e inicialização gráfica | Pendente |
| Joystick, conexão e reconexão | Pendente |
| Saída de áudio, incluindo HDMI | Pendente |

## Próxima coleta

No Batocera, na pasta do projeto, execute com o mesmo interpretador previsto para
iniciar o jogo:

```sh
python3 tools/diagnostics.py --format json
```

Anexe a saída integral ao registro. O diagnóstico consulta metadados sem importar
Pygame, inicializar SDL ou abrir dispositivos; display, joystick e áudio exigem
provas separadas no equipamento. Nenhum teste local ou simulado está registrado
como homologação Batocera.
