# Android TV

Suika Elika continua sendo o mesmo jogo Python/Pygame. O APK usa SDL2 pelo
`python-for-android`, com receitas locais para CPython, Pygame CE e Pymunk nas
versões compatíveis com o runtime do projeto. A receita do Pygame usa Cython 3.3.0
no host de build. A receita CPython desativa a depuração remota opcional e o módulo
de depuração do CPython para manter API mínima 23. A atividade declara a categoria
de inicialização Leanback, orientação horizontal e ausência de dependência de tela
de toque. O pacote inclui ABIs ARM64 e ARM de 32 bits.

## Gerar o APK no Windows

O build do Android precisa de um ambiente Linux. No Windows, o script usa a
imagem oficial `kivy/buildozer` pelo Docker Desktop e guarda o SDK, NDK e caches
em um volume Docker chamado `suika-elika-buildozer-cache`:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/android/build.ps1
```

O primeiro build baixa o SDK, NDK e as bibliotecas nativas; pode demorar e usar
vários gigabytes. Builds seguintes reutilizam o cache. O APK debug fica em
`dist/android/` e pode ser instalado por sideload.

## Instalar na TV

Copie o APK gerado para a TV e abra o arquivo com um instalador de pacotes. Se a
TV tiver depuração sem fio habilitada e o Android SDK Platform Tools estiver no
computador, também é possível instalar pela rede:

```powershell
adb connect IP_DA_TV:5555
adb install -r dist/android/NOME_DO_APK.apk
```

Use o nome exato exibido ao final do build. A tela da TV precisa permitir
instalação de apps de fontes externas. O filtro Leanback faz o jogo aparecer na
interface de TV compatível, além de permitir iniciar o pacote por um instalador.

## Ícone e entrada

O ícone quadrado de loja de `raw_assets/icons/android/play_store_512.png` é a
imagem base do launcher. As camadas adaptativas de foreground e background em
`raw_assets/icons/android/res/mipmap-xxxhdpi/` alimentam o ícone adaptativo do
Android. O banner 16:9 do launcher fica em
`raw_assets/icons/android/res/drawable-xhdpi/tv_banner.png` (320×180); ele foi
derivado da mesma arte e inclui o nome do jogo. O build inclui esses recursos no
APK e define o banner da aplicação no manifesto.

O jogo aceita controles Bluetooth/USB que o SDL do Android expuser como joystick
ou game controller. A experiência da partida e da BATALHA continua sem teclado;
o suporte real depende do mapeamento SDL do controle e deve ser confirmado na TV.
O modo de desenvolvimento `--desktop` não é ativado pelo APK.

## Limites de validação

O build local confirma a compilação e os recursos declarados no APK. Ainda é
necessário instalar e jogar em uma Android TV real para homologar inicialização
no launcher, controle, hotplug, áudio e desempenho. O pacote debug não é um
release assinado para uma loja; para distribuição direta, a TV pode instalar o
APK debug após autorizar fontes externas.
