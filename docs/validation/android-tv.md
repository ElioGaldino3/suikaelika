# Evidências de validação — Android TV

Atualizado em 21/10/2026.

## APK gerado

- Comando no Windows: `powershell -ExecutionPolicy Bypass -File packaging/android/build.ps1`
- O script executou `docker run ... kivy/buildozer:latest android debug` e o Gradle terminou com `BUILD SUCCESSFUL`.
- Artefato: `dist/android/suikaelika-0.1.0-arm64-v8a_armeabi-v7a-debug.apk`
- Tamanho: 48.334.127 bytes (46,1 MiB).
- Pacote: `com.suikaelika`; minSdk 23; targetSdk 35.
- Assinatura: debug, adequada para sideload; não é uma versão assinada para loja.

## Conteúdo Android TV

O `aapt2 dump xmltree` do APK confirmou:

- `MAIN` com `LEANBACK_LAUNCHER`, além do filtro `LAUNCHER`;
- orientação `landscape` na atividade;
- banner associado à aplicação;
- `android.software.leanback` e `android.hardware.touchscreen` como recursos opcionais;
- ícone e recursos adaptativos do launcher no pacote.

O APK contém as bibliotecas nativas SDL/Python e `libpybundle.so` para `arm64-v8a` e `armeabi-v7a`. A distribuição P4A gerada inclui pygame-ce 2.5.8 e Pymunk 7.3.1; os diretórios compilados das duas ABIs incluem as extensões pygame de vídeo/joystick e `pymunk/_chipmunk.abi3.so`. `assets/private.tar` inclui os módulos do jogo, dados e sprites. Os recursos usados vêm de `raw_assets/icons/android/`: ícone quadrado 512×512 e banner 320×180.

## Verificações

- Build Android: concluído; Gradle `BUILD SUCCESSFUL`.
- Manifesto e recursos: inspecionados com `aapt2 dump xmltree` e listagem do APK com `zipfile`.
- `.venv\Scripts\python.exe -m pytest -q tests\services\test_platform.py tests\packaging\test_layout.py`: **9 passaram**.
- `.venv\Scripts\ruff.exe check .`: aprovado.
- `.venv\Scripts\ruff.exe check --isolated --select E,F,I,UP,B --line-length 120 packaging\android\p4a-recipes\pygame-ce\__init__.py packaging\android\p4a-recipes\pymunk\__init__.py packaging\android\p4a-recipes\python3\__init__.py`: aprovado.
- `.venv\Scripts\python.exe -m mypy`: aprovado, 46 fontes.
- `git diff --check`: aprovado.
- Suíte completa `.venv\Scripts\python.exe -m pytest -q`: **296 passaram, 1 falhou** em `tests/rendering/test_assets.py::test_v3_sheet_generates_all_native_resolution_transparent_sprites`. O teste compara as dimensões da folha de frutas (193×207) com sprites empacotados em 5× (965×1035); essa falha de recursos visuais não está ligada ao build Android.

## Limites

Não foi possível instalar ou jogar em Android TV: `adb` não está instalado neste computador e não há TV/controle físico conectado. Portanto, inicialização no launcher, mapeamento de controle, reconexão, áudio e desempenho permanecem pendentes em SE-043. O APK debug foi produzido e inspecionado localmente, mas a experiência no aparelho não foi homologada.

## Referências consultadas

- [Android Developers — Create and run a TV app](https://developer.android.com/training/tv/get-started/create)
- [Buildozer — Specifications](https://buildozer.readthedocs.io/en/latest/specifications/)
- [python-for-android — Build options](https://python-for-android.readthedocs.io/en/latest/buildoptions.html)
