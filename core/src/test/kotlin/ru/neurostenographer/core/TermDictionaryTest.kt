package ru.neurostenographer.core

fun testTermDictionary() {
    fun seg(text: String) = TranscriptSegment(0, 1000, "Speaker 1", text)
    val terms = BuiltinTerms.ALL
    fun one(text: String) = TermDictionary.suggest(listOf(seg(text)), terms)

    // Stem with a Russian ending keeps the ending after a hyphen; case of the ending is lowercased.
    check(one("какие-нибудь хаскелевские монады").single().replacement == "Haskell-евские")
    check(one("Пишем на свифте.").single().let { it.original == "свифте" && it.replacement == "Swift-е" })
    check(one("джаваскрипторам объясняют").single().replacement == "JavaScript-орам")
    check(one("Джаваскрипт").single().replacement == "JavaScript")
    // Multi-word variants need plain whitespace between the words.
    check(one("он продакт оунер").single().let { it.original == "продакт оунер" && it.replacement == "Product Owner" })
    check(one("продакт, оунер").isEmpty())
    // Longest variant wins over a shorter prefix: «джаваскрипт» is not «джав…».
    check(one("джава и джаваскрипт").map { it.replacement } == listOf("Java", "JavaScript"))
    // Ambiguous words are proposed but flagged; ordinary words and too-long suffixes are left alone.
    check(one("руби дрова").single().ambiguous)
    check(one("он шёл домой, шел дождь, растёт трава").isEmpty())
    check(one("котлинская котлинскаяяяя").map { it.original } == listOf("котлинская"))
    // Hackathon / Hex.Team theme: spellings A3 produced on the TTS probe; Cyrillic canonical forms take endings without a hyphen.
    fun pairs(text: String) = one(text).map { it.original to it.replacement }
    check(pairs("Хокотон проводит не яу Мефи. Студенты МЕФИ. Нейросеть для деарезации говорящих. Чекпоинт Хокатона. Команда Хека Стим.") ==
        listOf("Хокотон" to "Хакатон", "не яу Мефи" to "НИЯУ МИФИ", "МЕФИ" to "МИФИ", "деарезации" to "диаризации",
            "Хокатона" to "Хакатона", "Хека Стим" to "Hex.Team")) { one("x").toString() }
    check(pairs("Хакатон проводит НИЯУ МИФИ, диаризация, команда Hex.Team").isEmpty())
    // Offensive security (A3 output on the probe).
    check(pairs("Обсуждаем пентист внешнего периметра. Пентэстер нашёл SQL-инекцию. Используем энмоп и Вайершарк, потом метасполоид.") ==
        listOf("пентист" to "пентест", "Пентэстер" to "Пентестер", "SQL-инекцию" to "SQL-инъекцию", "энмоп" to "Nmap",
            "Вайершарк" to "Wireshark", "метасполоид" to "Metasploit")) { pairs("Обсуждаем пентист внешнего периметра. Пентэстер нашёл SQL-инекцию. Используем энмоп и Вайершарк, потом метасполоид.").toString() }
    check(pairs("Эксплоид опубликован. Фазинг парсера и Фазир на ночь. Бэгдор и Рудкид в прошивке. Вредоносный шел-код.") ==
        listOf("Эксплоид" to "Эксплойт", "Фазинг" to "Фаззинг", "Фазир" to "Фаззер", "Бэгдор" to "Бэкдор", "Рудкид" to "Руткит",
            "шел-код" to "шелл-код")) { one("x").toString() }
    check(pairs("Реверс инжиниринг прошивки в Вайда про и Гидре.") == listOf("Реверс инжиниринг" to "Реверс-инжиниринг", "Вайда про" to "IDA Pro",
        "Гидре" to "Ghidra"))
    check(pairs("Скад-система показывает параметры.") == listOf("Скад-система" to "SCADA-система"))
    check(one("Гидре").single().ambiguous && one("люкс").single().ambiguous && one("Фриду").single().ambiguous)
    // Acronyms: letter-name spellings and A3 misspellings; plain Latin acronyms are untouched.
    check(pairs("Двухфакторная аутентификация, twfa, по впн и эс эс эйч, сиви и сивиэсэс, овасп, сием, эдр.") ==
        listOf("twfa" to "2FA", "впн" to "VPN", "эс эс эйч" to "SSH", "сиви" to "CVE", "сивиэсэс" to "CVSS", "овасп" to "OWASP",
            "сием" to "SIEM", "эдр" to "EDR")) { one("x").toString() }
    check(one("VPN, SSH, SIEM, EDR, TLS, DNS, SQL, API, 2FA, OWASP, CVE, CVSS, Wi-Fi, Bluetooth, Nmap, Wireshark").isEmpty())
    // Industrial control and embedded.
    check(pairs("Модбас, профинити, озернёт, кадисис, вихдель, юарт, джейтаг, фри ртос, ардуино.").map { it.second } ==
        listOf("Modbus", "PROFINET", "Ethernet", "CODESYS", "VHDL", "UART", "JTAG", "FreeRTOS", "Arduino")) { one("x").toString() }
    check(pairs("Для АСУ ТП и ПЛК нужен ФСТЭК, а ещё госсопках.").map { it.second } == listOf("ГосСОПКах"))
    // Ordinary Russian words that sit close to terms are left alone.
    check(one("Шел дождь, рестораны открыты, мы шли, даст ответ, она сок пила, ромб и кан, график, насос и пентхаус.").isEmpty())
    // Stems never swallow a canonical form that merely starts with the variant: «пентест» stays «пентест».
    check(one("Пентест, пентесты, фаззинг, фаззингом, эксплойтов, руткита.").isEmpty())
    try { Term("a*b", listOf("x")); error("Inner * accepted") } catch (_: IllegalArgumentException) { }
    // Already canonical: nothing to do.
    check(one("Пишу на Kotlin и JavaScript").isEmpty())

    // apply(): exact positions, several edits in one segment, stale edits ignored, raw untouched.
    val raw = listOf(seg("на котлине и свифте пишем"), seg("без терминов"))
    val edits = TermDictionary.suggest(raw, terms)
    check(edits.size == 2)
    val fixed = TermDictionary.apply(raw, edits)
    check(fixed[0].text == "на Kotlin-е и Swift-е пишем" && fixed[1] === raw[1] && raw[0].text == "на котлине и свифте пишем")
    val stale = edits.first().copy(original = "другое")
    check(TermDictionary.apply(raw, listOf(stale)) == raw)
    // User terms work the same way.
    val user = listOf(Term("sherpa-onnx", listOf("шерпа онникс", "шерпа оникс")))
    check(TermDictionary.suggest(listOf(seg("мы используем шерпа оникс")), user).single().replacement == "sherpa-onnx")
    check(TermDictionary.suggest(listOf(seg("нам помогал шерпа")), user).isEmpty())
    for (bad in listOf<() -> Unit>({ Term(" ", listOf("x")) }, { Term("X", emptyList()) }, { Term("X", listOf("Заглавная")) },
            { Term("X", listOf("a*b")) })) {
        try { bad(); error("Invalid term accepted") } catch (_: IllegalArgumentException) { }
    }
    println("PASS term dictionary: stems+endings, multi-word, longest match, ambiguous flag, common-word guards, apply/stale")
}
