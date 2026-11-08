# Android: исходные файлы

Рабочий проект: [app](../../app/) — Activity, импорт/экспорт, UI, Android-модели; [core](../../core/) — обработка аудио, текст, временные интервалы. Перемещать их ради шаблона не нужно: это сломает Gradle.

Product-флаги: `-PnemotronProduct=true -PasrA3=true -PenglishAuto=true -PfddtHybrid=true`. Пробы: `:core:runCoreTests` и `:app:lintDebug`. APK: `:app:assembleRelease` с корректными модельными весами и отдельным хранилищем ключа подписи; секреты не коммитить.

[Архитектура](../../docs/ARCHITECTURE.md), [модели](../../docs/MODELS.md), [тестирование](../../docs/TEST_RESULTS.md), [инструкция для пользователей](../../README.md).
