package ru.neurostenographer.core

private fun seg(text: String) = TranscriptSegment(0, 1000, "Говорящий 1", text)

fun testTopicTitle() {
    // Too little speech: no invented topic.
    check(TopicTitle.suggest(listOf(seg("Привет, как дела."))) == null)
    check(TopicTitle.suggest(emptyList()) == null)
    // Nothing repeats: no reliable topic.
    check(TopicTitle.suggest(listOf(seg("Сегодня хорошая погода и завтра будет дождь над городом после обеда"))) == null)
    // Repeated meaningful words win; filler and function words never do; forms of one word are one topic word.
    val title = TopicTitle.suggest(listOf(
        seg("Давайте обсудим сервер. Сервер падает каждый вечер, нужно смотреть логи сервера."),
        seg("Логи показывают ошибку базы данных. Ошибка повторяется, база данных перегружена.")))
    checkNotNull(title)
    check(title.startsWith("Сервер")) { title }
    check("ошибк" in title.lowercase() || "логи" in title.lowercase()) { title }
    check(!title.lowercase().contains("давайте") && !title.lowercase().contains("нужно")) { title }
    check(title.split(", ").size <= 3) { title }
    // Greetings are not topics.
    check(TopicTitle.suggest(listOf(seg("Здорово, здорово! Привет, привет. Как дела? Привет, чего не спишь, привет"))) == null)
    // Same input, same title.
    check(TopicTitle.suggest(listOf(seg("сервер сервер сервер логи логи ошибка ошибка ошибка ошибка"))) ==
        TopicTitle.suggest(listOf(seg("сервер сервер сервер логи логи ошибка ошибка ошибка ошибка"))))
    println("PASS topic title")
}
