# Runtime Batocera — coleta parcial

**Estado:** bloqueado; dados abaixo ainda não substituem uma coleta no equipamento.

## Informação relatada

Em 20/10/2026, o usuário informou que usa Batocera 43 em um notebook x86 e que o
`python3` está disponível. Esses dados são relato do usuário; não foram medidos
por esta sessão.

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
