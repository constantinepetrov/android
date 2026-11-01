# Независимые оконные настройки и безопасный Stop аудио

Проверенный опубликованный SHA: `594d6ed36a57af2e9a104376abcf4e31c3c1f9fa`.
Tree: `c315807b5393ac30e219caf4351ba17783655496`.
База: `17b344e5e3abbc6522da5d99587b897b141faa19`; предыдущий проверенный код: `708e0b7`.
Checkout был чист до и после всех проверок. Следующий commit добавляет только отчёт/логи и ссылку в плане; его SHA не выдаётся за проверенный исходный код.

[Читаемая сводка](summary.log) · [Полный архив логов и команд](cloud-logs.tar.gz) · [SHA-256](SHA256SUMS).
Каждый overlay-лог содержит фактические SHA/tree, версию и полный FPC_COMMAND. В архиве run-cloud-checks.sh записывает все переменные, команды и коды завершения.
Actions не запускался, PR остаётся draft, master не изменён.

## Оконные настройки и совместимость

`KM_WindowTypes` — собственные значения данных с явными функциями XML-кодирования; `KM_WindowParams` и `KM_MainSettings` не используют Forms/UITypes. Ord проектных enum не используется ни в XML, ни в desktop-преобразованиях.

Закреплённый Lazarus 4.0: commit `9d15c73c91a1545be50bee02b27bd3b43f9d90e8`, реальные определения lcl/forms.pp и их SHA-256 включены в desktop-definitions.log. Test-desktop-types компилирует **настоящие** Forms/Interfaces/nogui и KM_DesktopWindowTypes, затем проверяет все 4 состояния и 9 позиций в обе стороны.

| Состояние desktop | Старый XML-код | После загрузки |
| --- | --- | --- |
| wsNormal | 0 | normal (0) |
| wsMinimized | 1 | normal (0) |
| wsMaximized | 2 | maximized (2) |
| wsFullScreen (LCL) | 3 | maximized (2), прежний clamp |

| Позиция desktop | Старый XML-код |
| --- | --- |
| poDesigned | 0 |
| poDefault | 1 |
| poDefaultPosOnly | 2 |
| poDefaultSizeOnly | 3 |
| poScreenCenter | 4 |
| poDesktopCenter | 5 |
| poMainFormCenter | 6 |
| poOwnerFormCenter | 7 |
| poWorkAreaCenter (LCL) | 8, при загрузке ограничивается до 7 |

Desktop-адаптер сохраняет живые LCL extensions 3/8. XML loader сохраняет исторические ограничения State 0..2 / Position 0..7 и defaults 0/4. Minimized нормализуется после загрузки и затем сохраняется normal. TFormMain.ShowInCustomWindow использует ToDesktopWindow*, GetWindowParams — FromDesktopWindow*; остальные потребители передают record дальше и не выполняют casts в Forms-типы.

Проверены **настоящие TKMainSettings.LoadFromXML/SaveToXML** с 33 авторскими XML fixtures: все 24 старые пары, отрицательные/слишком большие/нечисловые и отсутствующие атрибуты, extensions 3/8, отсутствие Left/Top и Main. Проверяются повторная загрузка сериализованного XML, сохранение других секций, UTF-8/escaping и очистка obsolete children/attributes.
Реальная модель проверена на минимальные размеры, IsValid, FixedPosition, LockParams/UnlockParams и ApplyWindowParams. Lock сохраняет прежний контракт: блокируется ApplyWindowParams, а не произвольное прямое изменение свойств. При отсутствии координат остаётся NeedResetToDefaults, как прежде; desktop затем применяет default window params.

Для этих тестов пришлось завершить FPC-ветку KM_IoXML: ранее AddChild/FindNode, атрибуты и XML Text не имели реализации. Теперь используется реальный laz2_DOM, реализованы Clear/элементные children, чтение/запись атрибутов и текста; root выбирается корректно, новый документ принимается с освобождением прежнего. WDC-методы сохранены. Heaptrc: 0 unfreed memory blocks в XML-тесте.

**Предел desktop-проверки:** настоящий Lazarus/nogui adapter собран, слинкован и выполнен. Полные TFormMain/GUI и Windows/Delphi VCL не собраны и не запущены; их поведение целиком не подтверждается тестом enum. Коммерческие VCL sources/toolchain в среде отсутствуют. VCL-ветка адаптера использует поимённые преобразования первых 3/8 значений, а LCL extensions ограничены FPC. Обновления обоих методов TFormMain проверены по исходникам.

## Ошибка Stop

До исправления CloseDevice exception оставлял aisReady и старые IDs после уничтожения контекста. Новый адресный тест на неизменённом KM_AudioSession из `708e0b7` воспроизводит `Exception: ready after failed Stop`, exit **217 — ожидаемый отрицательный контроль**, отдельный old-audio-negative.log.

На исправлении тот же тест проходит: Stop в finally публикует stopped, Activate требует ready + живые owned context/device, успешные освобождения немедленно инвалидируются. После DestroyContext массивы обнуляются до CloseDevice. При отказе закрытия сохраняется device handle, ошибка остаётся в ErrorText и исключении; повторный Stop действительно закрывает его один раз. Ошибки независимых операций агрегируются. Неудачный detach не приводит к DestroyContext текущего контекста: context/device остаются для безопасного retry.

Сохранены успех init, 12 промежуточных отказов, частично созданные объекты, уничтожение при заблокированном init, порядок sources-before-buffers, повторный Stop. Добавлены CloseDevice failure/retry и detach failure/retry. Heaptrc: 0 unfreed memory blocks.
Это детерминированные проверки настоящего владельца с контролируемым backend. Отдельный реальный Linux OpenAL Soft null-driver test также проходит. **Ни один из них не является Android OpenAL runtime.** Постоянный отказ backend не выдаётся за успешное освобождение: явная ошибка и pending handles требуют повторной попытки, пока объект жив; при невозможности очистки destructor также может выбросить исключение. Worker/teardown не используют gLog.

## Android AArch64

| Цель (контролируемый Pascal Script overlay) | Exit | Результат |
| --- | --- | --- |
| KM_WindowTypes | 0 | Скомпилирован |
| KM_WindowParams | 0 | Скомпилирован отдельно; ELF AArch64 |
| KM_MainSettings | 0 | Скомпилирован отдельно; ELF AArch64 |
| KM_AudioSession / KM_OpenALBackend | 0 / 0 | Скомпилированы |
| KM_ControlsTypes / KM_UtilsExt | 0 / 0 | Скомпилированы |
| kamprobe.lpr | 0 | Компиляция с -Cn; без Android-линковки |
| KM_Sound | 1 | KM_ControlsForm:99, inline var |
| KM_ControlsList | 1 | Та же первая ошибка |
| KM_ControlsBase | 1 | Та же первая ошибка |
| KM_ControlsEdit | 1 | Та же первая ошибка |
| KM_Game | 1 | Та же первая ошибка |

```text
KM_ControlsForm.pas(99,3) Error: Illegal expression
KM_ControlsForm.pas(99,7) Fatal: Syntax error, ";" expected but "identifier DESIREDWIDTH" found
```

Фактическая цепочка -vu для KM_Game:

```text
KM_Game -> KM_InterfaceGamePlay -> KM_GUICommonGameOptions
 -> KM_GUICommonOptions -> KM_GUICommonKeys -> KM_ControlsForm
```

Для списка перед ней добавляются KM_ControlsList -> KM_Controls -> KM_ControlsBase -> KM_Sound -> KM_HandsCollection. Все отдельные цепочки находятся в dependency-chains.log и summary.log.
Прежний путь оконных настроек к Forms/WSReferences пройден. До текущей ошибки в trace KM_Game нет импортов Forms, LCLType, LCLIntf и WSReferences; это не доказывает отсутствие других LCL-путей дальше по компиляции.

Первая оставшаяся ошибка — синтаксис inline-объявлений Delphi в конструкторе настоящей UI-формы, неподдерживаемый FPC 3.2.2. Следующий срез должен перенести desiredWidth/Height/Left/Top в обычные Integer locals, сохранить формулы полей/центрирования, margin/clamp, порядок вычисления и inherited Create; затем повторно проверить граф. Эта форма не исключена и не заменена заглушкой. Никаких утверждений о завершении компиляции всего KM_Sound/Controls/KM_Game нет.

## Инструменты, команды, регрессии

FPC 3.2.2; target aarch64/android; FPC source `0d122c49534b480be9284c21bd60b53d99904346`; binutils assembler 2.44. JDK 17.0.17, Android API 35 jar для javac; Actionlint 1.7.7.
Основная команда: wrapper ppcrossa64 добавляет `-Sc`, затем `-Paarch64 -Tandroid -XPaarch64-linux-gnu- -Mdelphi -dDBG_SKIP_SECURE_AUTH -B -Cn`, source/RTL paths и -vu на зависимых целях. Полный argv сохранён для каждой цели. ANDROID/UNIX/CPUAARCH64 задаются Android target. DBG_SKIP_SECURE_AUTH — существующая диагностическая опция из-за отсутствующего secure-auth unit; не production-конфигурация APK.

```sh
python3 android-port/experiments/prepare-pascalscript-fpc.py "$PS_SOURCE" "$PS_OVERLAY"
PORT_TARGETS=src/settings/KM_WindowParams.pas bash android-port/experiments/compile-game-android.sh
PORT_TARGETS=src/settings/KM_MainSettings.pas bash android-port/experiments/compile-game-android.sh
# Затем отдельный PORT_TARGETS для Sound, ControlsList/Base/Edit, KM_Game.
bash android-port/tests/test-window-settings-linux.sh
bash android-port/tests/test-audio-session-linux.sh
bash android-port/tests/test-desktop-window-types-linux.sh
```

Все env, output dirs и полные команды записаны в run-cloud-checks.sh. Desktop build дополнительно использует настоящий CHM parser из FPC source; отсутствующий fpcres собран из utils/fpcres того же закреплённого FPC, без подмены library/widgetset. Для FFI предоставлено linker-имя libffi.so к установленной libffi.so.8; OpenAL null test использует libopenal.so.1 через локальное loader-имя.

Pascal Script submodule: `ce8590dd7b9cf48fd0e446731989603e09e239b8`; overlay generator SHA-256 `22b61ecbc2c3da690438d053eb93e8a7b7a5c1348b0f9c6de1832944993a59c6`, не изменён.
Отдельный **unpatched baseline** KM_Game: exit 1, `InvokeCall.inc(116,5): Wrong number of parameters specified for call to Invoke`, итог 32 ошибки uPSRuntime. Baseline использует другой output dir без PS_OVERLAY; эти ошибки не смешиваются с overlay или новой границей ControlsForm.

Все запущенные положительные регрессии exit 0: window-settings, desktop enum adapter, audio lifecycle, real Linux OpenAL, input, messages/legacy serialization, Fog of War, platform services, options/presentation, map header, fonts, terrain, JNI map loader, Pascal Script, libffi ABI, record/out probes. Actionlint и javac main/instrumentation — exit 0. Pan/pinch/GL-context instrumentation сохранена и скомпилирована; повторного Android runtime в этом срезе нет.

## Разделение результатов

- Android: успешно скомпилированы перечисленные units/объекты и kamprobe с -Cn. Клиент не слинкован.
- Host Linux: тестовые программы слинкованы и выполнены; desktop adapter использует реальный Lazarus/nogui.
- APK: новый APK не создавался.
- Android runtime: не выполнялся; Android OpenAL, жесты и игровой цикл на Android этим срезом не подтверждаются. Реальный TKMGame.PlayNextTick ещё не выполняется.
