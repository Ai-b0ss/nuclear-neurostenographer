package ru.neurostenographer.core

/**
 * Starter dictionary: IT terms that are normally written in Latin but that Russian ASR spells in Cyrillic.
 * Selection rules (see docs/TERM_DICTIONARY_B0_2026-11-05.md): only terms whose Cyrillic spelling is not an ordinary Russian
 * word, unless marked ambiguous; no russified brands usually written in Cyrillic (Яндекс, Хабр, Телеграм, бэкенд);
 * chosen from general knowledge and the Podlodka DEV errors, NOT from the HOLDOUT errors.
 * Stems never collide with common words: «шел*» (шёл), «раст*» (растёт), «редис» and «кафка», «плюсы», «оникс» are left out on purpose.
 */
object BuiltinTerms {
    val ALL: List<Term> = listOf(
        Term("JavaScript", listOf("джаваскрипт*", "джава скрипт*", "яваскрипт*")),
        Term("TypeScript", listOf("тайпскрипт*", "тайп скрипт*")),
        Term("Java", listOf("джава", "джавы", "джаве", "джаву", "джавой", "джавовый*", "джавовск*")),
        Term("Kotlin", listOf("котлин*")),
        Term("Swift", listOf("свифт*")),
        Term("Haskell", listOf("хаскел*", "хаскелл*")),
        Term("Fortran", listOf("фортран*")),
        Term("Python", listOf("пайтон*", "питон*"), ambiguous = true),
        Term("Ruby", listOf("руби"), ambiguous = true),
        Term("Pascal", listOf("паскал*"), ambiguous = true),
        Term("Shell", listOf("шелл*")),
        Term("C++", listOf("си плюс плюс", "сиплюсплюс")),
        Term("C#", listOf("си шарп*", "сишарп*")),
        Term("Go", listOf("голанг*", "го ланг*")),
        Term("PHP", listOf("пиэйчпи", "пхп")),
        Term("SQL", listOf("эскьюэль")),
        Term("PostgreSQL", listOf("постгрес*", "постгрескьюэль")),
        Term("Android", listOf("андроид*")),
        Term("iOS", listOf("айос", "ай ос")),
        Term("Linux", listOf("линукс*")),
        Term("Windows", listOf("виндоус*", "виндовс*")),
        Term("GitHub", listOf("гитхаб*", "гит хаб*")),
        Term("GitLab", listOf("гитлаб*", "гит лаб*")),
        Term("Git", listOf("гит", "гите", "гитом")),
        Term("Docker", listOf("докер*")),
        Term("Kubernetes", listOf("кубернетес*", "кубернетис*")),
        Term("DevOps", listOf("девопс*")),
        Term("Scrum", listOf("скрам*")),
        Term("Agile", listOf("эджайл*", "аджайл*")),
        Term("Product Owner", listOf("продакт оунер*", "продакт овнер*", "продакт-оунер*")),
        Term("Jira", listOf("джира", "джиру", "джире", "джиры", "джирой")),
        Term("Slack", listOf("слак*")),
        Term("Figma", listOf("фигма", "фигме", "фигму", "фигмы", "фигмой")),
        Term("Excel", listOf("эксель*", "эксел*")),
        Term("PowerPoint", listOf("пауэрпоинт*", "поверпоинт*")),
        Term("ChatGPT", listOf("чатжипити", "чат джипити", "чат гпт", "чатгпт")),
        Term("GPU", listOf("джипию", "гпу")),
        Term("CPU", listOf("сипию", "цпу")),
        Term("API", listOf("эйпиай")),
        Term("PyTorch", listOf("пайторч*")),
        Term("TensorFlow", listOf("тензорфлоу", "тензор флоу")),
        Term("ONNX", listOf("онникс")),
        Term("Gradle", listOf("градл*", "грэдл*")),
        Term("Stockfish", listOf("стокфиш*")),
        Term("AlphaZero", listOf("альфазеро", "альфа зеро")),
        Term("opcode", listOf("опкод*")),
        Term("machine learning", listOf("машин лернинг*")),
        Term("deep learning", listOf("дип лернинг*")),
        Term("open source", listOf("опен сорс*", "оупен сорс*", "опенсорс*")),
    )
}
