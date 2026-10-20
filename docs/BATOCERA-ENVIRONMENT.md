# Coleta do ambiente Batocera

Este roteiro registra o ambiente real antes de escolher versões finais ou afirmar compatibilidade. O alvo ainda não foi identificado; preencha os dados abaixo somente depois de executar os comandos no aparelho.

## Coleta sem display ou dispositivos

Execute o diagnóstico com o mesmo Python que será usado para iniciar o jogo, a partir da pasta do projeto:

```sh
python tools/diagnostics.py
python tools/diagnostics.py --format json > suika-elika-environment.json
```

O relatório identifica versão e implementação do Python, sistema, release, arquitetura do aparelho, arquitetura do processo e disponibilidade/metadados das dependências runtime e de desenvolvimento. A coleta usa somente a biblioteca padrão e não importa Pygame. Ausência de Pygame ou Pymunk aparece como resultado parcial; isso não interrompe a coleta.

O relatório não lê nem imprime variáveis de ambiente. Ele também não prova que uma biblioteca nativa carregará, que o SDL encontrará uma tela, que o áudio funcionará ou que um controle será reconhecido. Os campos `device_probes` deixam essas verificações como `not_run`.

## Verificações gráficas e de dispositivos

Faça estas verificações separadamente, no Batocera real e pelo EmulationStation, quando houver uma versão executável do jogo ou uma prova gráfica controlada:

| Área | O que registrar |
|---|---|
| Inicialização gráfica | Se o jogo abriu pela categoria Pygame; resolução, orientação, tela cheia e erros de SDL registrados pelo processo |
| Entrada | Modelo do controle, conexão USB/Bluetooth, modo reconhecido pelo sistema e resultado de cada ação do jogo, incluindo remoção e reconexão |
| Áudio | Saída selecionada no Batocera e confirmação auditiva dos efeitos; registrar dispositivo HDMI/analógico e falhas |
| Física | Se a biblioteca Pymunk importou e se um cenário físico avançou no processo do jogo |
| Encerramento | Se a saída pelo menu e o retorno ao EmulationStation funcionaram |

Essas provas podem inicializar SDL e acessar dispositivos. Não as execute implicitamente ao importar o pacote nem trate a coleta de metadados como substituta dos testes. Drivers simulados e testes locais devem ser identificados como simulados/locais.

## Registro do alvo

Copie o relatório produzido pelo comando e complete os campos durante a prova:

| Campo | Resultado |
|---|---|
| Modelo do Batocera e versão | Pendente de coleta |
| Modelo do aparelho | Pendente de coleta |
| Arquitetura do sistema / processo | Pendente de coleta |
| Python, implementação e ABI | Pendente de coleta |
| Pygame / SDL e resultado gráfico | Pendente de coleta |
| Pymunk e avanço de física | Pendente de coleta |
| Controle e conexão | Pendente de coleta |
| Saída e resultado de áudio | Pendente de coleta |
| Erros observados / ação seguinte | Pendente de coleta |

Mantenha a saída integral do diagnóstico junto ao registro. Não preencha esses valores com base em um computador local ou em uma imagem do sistema que ainda não foi testada no aparelho.
