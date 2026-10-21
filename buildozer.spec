[app]
title = Suika Elika
package.name = suikaelika
package.domain = com
source.dir = .
source.include_exts = py,png,json,txt
source.exclude_dirs = .git,.venv,tests,docs,raw_assets,tools,packaging,skills,work,dist,build
source.exclude_patterns = *.pyc,*.pyo
version = 0.1.0
requirements = python3,pygame-ce,pymunk
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/raw_assets/icons/android/play_store_512.png
icon.adaptive_foreground.filename = %(source.dir)s/raw_assets/icons/android/res/mipmap-xxxhdpi/ic_launcher_foreground.png
icon.adaptive_background.filename = %(source.dir)s/raw_assets/icons/android/res/mipmap-xxxhdpi/ic_launcher_background.png

android.api = 35
android.minapi = 23
android.ndk = 28c
android.ndk_api = 23
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.extra_manifest_xml = packaging/android/manifest/extra.xml
android.manifest.intent_filters = packaging/android/manifest/leanback_intent_filters.xml
android.extra_manifest_application_arguments = packaging/android/manifest/application_arguments.txt
android.add_resources = %(source.dir)s/raw_assets/icons/android/res

p4a.bootstrap = sdl2
p4a.branch = master
p4a.local_recipes = packaging/android/p4a-recipes

[buildozer]
log_level = 2
warn_on_root = 0
bin_dir = dist/android
