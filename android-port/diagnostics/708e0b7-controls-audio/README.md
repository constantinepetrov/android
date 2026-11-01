# Controls / OpenAL: облачная проверка Android AArch64

Проверенный опубликованный checkout: `708e0b771abec73ec0c06fd1315ca0a1d102e43a`.
Tree: `de435ea9b73d4aaa3841fd05b4c24a97edda7219`. До и после проверок checkout чистый.
База реализации: `2e68fa2b7fa8ead426331b0a428a428cc3c6ddf8`.
Следующий commit добавляет только этот отчёт/логи и обновление плана; его SHA не выдаётся за проверенный checkout.

[Читаемая сводка с provenance, кодами, ошибками и цепочками](summary.log).
[Полные логи и команды](cloud-logs.tar.gz), [SHA-256](SHA256SUMS).
В архиве `run-cloud-checks.sh` воспроизводит проверку в подготовленной среде; каждый `overlay-*.log` содержит точный `FPC_COMMAND`, SHA/tree и версию компилятора.

## Результат ARM64

| Цель с контролируемым Pascal Script overlay | Exit | Результат |
| --- | --- | --- |
| KM_ControlsTypes | 0 | Unit скомпилирован |
| KM_UtilsExt | 0 | Unit скомпилирован |
| KM_AudioSession | 0 | Unit скомпилирован, ELF AArch64 |
| KM_OpenALBackend | 0 | Unit скомпилирован, ELF AArch64 |
| kamprobe.lpr | 0 | Компиляция с `-Cn`, без линковки |
| KM_Sound | 1 | Следующая зависимость оконных настроек |
| KM_ControlsList | 1 | Та же транзитивная зависимость |
| KM_ControlsBase | 1 | Та же транзитивная зависимость |
| KM_ControlsEdit | 1 | Та же транзитивная зависимость |
| KM_Game | 1 | Та же транзитивная зависимость |

Первая ошибка всех пяти остановившихся целей:

```text
lcltype.pp(51,3) Fatal: Can't find unit WSReferences used by LCLType
```

Подтверждённый `-vu` путь для KM_Game:

```text
KM_Game -> KM_InterfaceGamePlay -> KM_GUICommonGameOptions
 -> KM_GUICommonOptions -> KM_MainSettings -> KM_WindowParams
 -> Forms -> LCLType -> WSReferences
```

Для списка добавляется префикс `KM_ControlsList -> KM_Controls -> KM_ControlsBase -> KM_Sound -> KM_HandsCollection -> KM_Game`.
Полные индивидуальные пути находятся в `dependency-chains.log` и читаемой сводке.
В `src/settings/KM_WindowParams.pas` действительно используются `TWindowState` и `TPosition` из Forms (поля, record, свойства состояния/позиции окна). Их нельзя считать неиспользуемыми импортами.
В этом срезе Forms/widgetset не подменяется, связанные игровые units не исключаются.
Далее нужны независимые значения оконной конфигурации с сохранением desktop-ordinal/сериализации и адаптер desktop-окна; затем новая проверка графа.

Прямые Android-импорты Controls/LCLIntf/LCLType в ControlsList и соседних контролах заменены существующим KM_ControlsTypes только для реально используемых событий, клавиш и состояния ввода.
Аудит подтверждает неизменность тел методов всех 15 затронутых контролов относительно базы (после нормализации EOL); это статическая проверка, не UI runtime.
Фактический GetKeyState в KM_UtilsExt использует живое состояние ввода. Настоящий GetMultiplicator проверен на Alt+LMB/RMB, Shift, игнорирование Ctrl.
Найденный компилятором GetDoubleClickTime на Android получает системный getDoubleTapTimeout через JNI; отсутствие настройки и некорректные значения — явная ошибка. Desktop сохраняет исходный LCL/Windows API.

## Звук

Анонимный init удалён из настоящего TKMSoundPlayer. Он владеет TKMAudioSession с обычным TThread и реальным OpenAL-адаптером.
Worker не обращается к владельцу плеера, gLog или диалогам. Readiness защищена lock и публикуется после полного init и успешного detach; playback явно привязывает контекст.
Destroy сначала Terminate/WaitFor, затем освобождает sources перед buffers, context и device; промежуточные ошибки используют тот же cleanup.
Playback и Destroy требуют сериализации владельцем; зависший вызов драйвера может задержать WaitFor.
Set8087CW выполняется только на x86/x64.

Реальный Linux OpenAL эксперимент сначала дал Access violation при загрузке старого binding. Причина подтверждена: Linux FPC THandle имеет 4 байта, а dlopen handle — указатель 8 байт. Новый TOpenALLibraryHandle — PtrUInt для FPC/Unix и прежний THandle для Windows. Сигнатуры alcMakeContextCurrent/alcCloseDevice исправлены на ALCboolean.
После исправления реальный OpenAL Soft 1.24.2 с null driver успешно выполнил init, создание объектов, передачу контекста и teardown. Это Linux x86_64, НЕ Android OpenAL runtime и не проверка слышимого звука.
Компилятор полного KM_Sound пока останавливается в зависимостях до проверки всего implementation; успешная ARM64-компиляция вынесенного владельца и backend не равнозначна завершению KM_Sound.

## Регрессии

Все проверки ниже завершились с exit 0 (точные коды в status.log):

- Владелец audio session: успех, 12 точек отказа, частично созданные объекты, отмена/Destroy при заблокированном init, порядок cleanup, повторный Stop. Это контролируемый backend, а не драйвер.
- Реальный Linux OpenAL Soft null driver: init, context transfer, объекты, teardown; отдельный тест от проверки владения.
- Ввод и модификаторы; JNI-настройка системного интервала, настоящая JNI-ветка загрузчика карты (синтетический fixture и отказ на усечённом файле).
- Game messages и прежняя сериализация; Game options; presentation port; Fog of War; platform services; map header; font types; terrain types.
- Pascal Script classic invoker; libffi ABI и отдельные record/out compatibility probes с контролируемым overlay (Linux x86_64).
- Actionlint 1.7.7; javac 17.0.17 main + instrumentation source против Android API 35.

Ранее в этой среде FFI link останавливался на отсутствии linker-имени libffi.so. Финальный проход явно использовал LIBFFI_LIB_DIR с symlink на установленную libffi.so.8; это подготовка cloud linker path, не изменение игрового ABI или кода.
Pan/pinch и GL-context instrumentation сохранены и скомпилированы javac; повторного Android runtime/жестов в этом срезе нет. Windows-сборка и desktop UI runtime не выполнялись.

## Pascal Script и воспроизведение

FPC 3.2.2, target aarch64/android; FPC source `0d122c49534b480be9284c21bd60b53d99904346`.
Lazarus source `9d15c73c91a1545be50bee02b27bd3b43f9d90e8` (только source search path, desktop PPU/widgetset не добавлен).
Pascal Script submodule `ce8590dd7b9cf48fd0e446731989603e09e239b8`.
Overlay generator SHA-256 `22b61ecbc2c3da690438d053eb93e8a7b7a5c1348b0f9c6de1832944993a59c6`, не изменён.
Assembler GNU binutils 2.44; FPC wrapper добавляет `-Sc`.

Основные параметры: `-Paarch64 -Tandroid -XPaarch64-linux-gnu- -Mdelphi -dDBG_SKIP_SECURE_AUTH -B -Cn`, `-vu` для Controls и KM_Sound/KM_Game. ANDROID/UNIX/CPUAARCH64 задаются target, не имитацией host-архитектуры. DBG_SKIP_SECURE_AUTH — уже существующая диагностическая опция из-за отсутствующего upstream secure-auth unit, не режим production APK.
Сначала `prepare-pascalscript-fpc.py`, затем отдельный PORT_TARGETS для каждой цели и PS_OVERLAY; точные команды/search paths включены в каждый лог. Для baseline PS_OVERLAY удалён и PORT_BUILD_DIR отдельный.

Unpatched baseline KM_Game: exit 1, первая ошибка `InvokeCall.inc(116,5) Error: Wrong number of parameters specified for call to "Invoke"`, итог 32 ошибки uPSRuntime. Это отдельный baseline.log, не результат overlay; исправлять эти 32 ошибки в данном срезе не предпринималось.

## Границы результата

Actions не запускался и не переоткрывался PR; проверка выполнена самостоятельно в облаке. PR остаётся draft, master не изменён.
Сборка units/объектов, линковка, APK и runtime — разные результаты: первые пять целей скомпилированы; Android-клиент не слинкован, новый APK не создан, Android runtime/OpenAL не проверен, реальный TKMGame.PlayNextTick ещё не выполняется.
Отсутствие runtime не объясняет ошибку WSReferences: она воспроизведена самим AArch64-компилятором.
