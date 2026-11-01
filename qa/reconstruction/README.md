# Точное восстановление APK для облачной QA

Комплект восстанавливает **уже собранный и подписанный** Android APK, не запуская
компилятор или подпись:

| Поле | Значение |
| --- | --- |
| APK | `KaM_Remake_r16397_ARM64_debug.apk` |
| Размер | 856 629 249 байт |
| SHA-256 | `c7df4b880984b9a475b57ee00b41fa5ba6140f4c21e5f688a9188ab1622169c4` |
| Application ID | `org.kamremake.android` |
| ABI | `arm64-v8a` |
| Проверенный исходный commit | `c9214fd1451ac264d9bfc1b851b7b9360ab9eb52` |

`recipe.json` — самостоятельный manifest: provenance исходников и установщика,
размеры и хеши шаблона, а также все 8 885 уникальных игровых файлов с точными
исходными путями, смещениями в APK, размерами, методами ZIP и SHA-256 исходного
файла и сжатого payload.

## Как устроено восстановление

В `template.gz` сохранены исходные байты APK за пределами содержимого всех
`assets/kamdata/`: скомпилированные библиотеки и Java-код, ZIP-заголовки,
таблица ресурсов, manifest данных и исходная подпись. Игровые payloads
в шаблон не включены. Их 824 879 185 байт восстанавливаются из официального
установщика. Имена и хеши игровых файлов присутствуют в recipe и ZIP metadata.

4 933 payloads хранятся без сжатия; 3 952 восстанавливаются raw-deflate level 1.
Вне `assets/kamdata/` среди APK assets остаются только `kamdata.lst`,
`licenses/AGPL-3.0.txt` и `licenses/SOURCE.txt`.

| Шаблон | Размер | SHA-256 |
| --- | ---: | --- |
| `template.gz` | 30 104 246 | `3f9a8ab6628dc28ad959a912d40c7504a9b81aa3902a351ca023031a0732e0a4` |
| Распакованные диапазоны | 31 750 064 | `e2de8a9071dad4fd4e1d87604f7a4d14c474a677c2eac9398eab3aa22df44377` |

Если шаблон доставлен частями, сначала соедините их в порядке, указанном в
manifest частей, затем передайте полученный gzip через `--template`. Сам CLI
принимает один целый gzip и проверяет его размер и SHA-256 до восстановления.

## Получение и извлечение данных

Источник — [официальная страница KaM Remake](https://www.kamremake.com/download/).
Зафиксированная ссылка полного r16397:

<https://www.kamremake.com/files/kam-remake-r16397/?tmstv=1793532124>

Выполняется **GET с переходом по redirect**, не HEAD: сервер может отвечать
на HEAD HTML-страницей. HTTP 200 сам по себе не является проверкой файла.
Проверьте полный скачанный файл перед извлечением:

| Поле | Значение |
| --- | --- |
| Имя | `KaM-Remake-Beta-r16397.exe` |
| Размер | 711 493 971 байт |
| SHA-256 | `9980a414f4adbe3806c322de5a74068861857968b3b5ddd4ec1d84987208cd9e` |

```bash
innoextract -s -d /tmp/kam-installer /tmp/KaM-Remake-Beta-r16397.exe
```

Проверено извлечение с `innoextract 1.9`. Установщик Windows не запускается.
Для `--data-root` нужен каталог `/tmp/kam-installer/app`, содержащий `data`,
`Campaigns`, `Maps`, `MapsMP`, `Music`, `Sounds`, `Tutorials` и корневые Readme.
Recipe использует настоящий регистр путей installer, включая `data/sprites`.
Не нужно вручную переименовывать каталоги или создавать bundle symlinks.

## CLI восстановления

Требуются Python 3.9+ со стандартными модулями `gzip` и `zlib` и достаточно
места для нового APK. Родительский каталог `--output` должен существовать.

```bash
python3 qa/reconstruct_apk.py \
  --data-root /tmp/kam-installer/app \
  --template /tmp/kam-input/template.gz \
  --output /tmp/kam-input/app.apk
```

По умолчанию recipe находится рядом со скриптом в `reconstruction/recipe.json`;
другой путь можно задать через `--recipe`. Если `--template` не указан,
используется `template.gz` рядом с recipe. Три source patches и `LICENSE.txt`
должны оставаться рядом с recipe: CLI также проверяет их размеры и SHA-256.

CLI проверяет каждый source/payload, распакованный шаблон, итоговый размер и
**фиксированный SHA APK, встроенный в код**. Временный файл публикуется только
после всех проверок. Существующий output никогда не перезаписывается; при ошибке
временный файл удаляется. Успех выводится в JSON с exit 0, ошибка — JSON в stderr
с ненулевым exit. Иная версия zlib, изменившая bytes, даст ошибку payload check.

Проверка без записи 857 MB выполняет **тот же producer байтов**:

```bash
python3 qa/reconstruct_apk.py --data-root /tmp/kam-installer/app --verify-only
```

После успешного восстановления и проверки файла runner может удалить свои
временные установщик, извлечённые данные и собранный gzip, оставив `app.apk` для
QA. В публичные результаты QA не нужно включать APK или каталог игровых данных.

## Соответствующие исходники

База: [Vadim170/kam-remake-android](https://github.com/Vadim170/kam-remake-android/tree/e81c3b765a13d730140c26159eab4506499d44e6)
на `e81c3b765a13d730140c26159eab4506499d44e6`.

1. В корне базы последовательно применяются
   `patches/0001-linux-build-15eeaae.patch` и
   `patches/0002-bundled-data-c9214fd.patch`. Это опубликованные в комплекте
   mail patches локальных commits `15eeaae…` и `c9214fd…`.
2. Инициализируется `src/ext/pascalscript_submodule` на
   `ce8590dd7b9cf48fd0e446731989603e09e239b8`.
3. Внутри submodule применяется
   `patches/0003-pascalscript-working-tree.patch`. Он сохраняет **полное
   фактическое грязное дерево** при сборке: четыре изменённых tracked файла
   и два новых файла `Source/aarch64.inc`, `Source/aarch64methods.inc`.

Main patches можно применить через `git am` или `git apply` из соответствующего
checkout; patch submodule — через `git apply` из его каталога. Если уже
применён donor PascalScript patch, второй раз не применяйте patch к тому же
дереву: начните с указанной чистой базы submodule.

`source-provenance.json` и встроенная в recipe копия фиксируют main tree,
submodule base, полные hashes patches, dependency commits и версии toolchain.
После `git am` committer metadata может изменить commit SHA; для проверки
содержимого используется зафиксированный tree SHA.

В donor `android/toolchain/setup_toolchain.sh` находятся сборка зависимостей и
патчи FPC/gl4es. Native build выполнялся с FPC 3.2.2, NDK 29.0.13599879 и
CMake 3.22.1; Gradle 8.13 / AGP 8.13.2 / JDK 17. Команда APK:

```bash
KAM_BUILD_TYPE=Debug KAM_BUNDLE_DATA=1 bash android/build_apk.sh
```

Приватный ключ подписи в комплект не входит. Сведения о source и его лицензии
сохранены в `LICENSE.txt`, source patches и исходном `assets/licenses/SOURCE.txt`.

## Проверки комплекта

- Все 8 885 payloads сопоставлены побайтно с исходным APK при подготовке.
- Совпадение всех 3 952 DEFLATE payloads отдельно подтверждено для zlib 1.3 и
  1.3.2, level 1.
- Полный patch грязного PascalScript воспроизведён на чистой базе: все
  516 путей совпали; оригинальный checkout не менялся.
- Результат настоящего файлового восстановления и независимый SHA записаны в
  `local-validation.json`; проверка `--verify-only` использует тот же код.
- `source-provenance-verification.json` содержит результат сверки submodule.

Эти проверки подтверждают восстановление точных байтов APK. Они **не являются
Android runtime, игровым тиком или подтверждением играбельности**. Запуск и
игровые проверки выполняет отдельный QA runner.

Для повторного изготовления комплекта из того же APK предусмотрен
`prepare_template.py`; это отдельный инструмент подготовки, он не нужен для
восстановления в CI.
