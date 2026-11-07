package ru.neurostenographer.core

/**
 * A short label for what a conversation was about: the most repeated meaningful words.
 *
 * This is deliberately NOT a language model. It counts words (Russian forms are grouped by a crude stem), drops
 * filler and function words, and needs a word to occur at least twice, so a short or empty recording gets no
 * topic instead of a random one. It runs instantly and fully offline.
 */
object TopicTitle {
    private val ENDINGS = listOf("ировать", "ование", "ования", "ованию", "ованием", "ями", "ами", "ого", "его", "ому", "ему",
        "ыми", "ими", "ать", "ять", "ить", "ает", "ают", "ует", "уют", "ешь", "ете", "ый", "ий", "ой", "ая", "яя", "ое", "ее",
        "ые", "ие", "ых", "их", "ов", "ев", "ом", "ем", "ам", "ям", "ах", "ях", "ую", "юю", "ей", "ию", "ия", "а", "я", "у",
        "ю", "ы", "и", "е", "о").sortedByDescending { it.length }

    private val STOP = (
        "это этот эта эти этого этой этом этим того тоже также очень просто вообще короче значит типа блин сейчас потом тогда " +
        "когда чтобы если есть было была были будет будем будут может можно нужно надо здесь тут вот как так что чего который " +
        "которая которые которое свой своё своя свои наш наша наши ваш ваша ваши весь вся всё все всех всем себя себе меня " +
        "тебя тебе мной нас вас них ему него неё ней нём они она оно мне при про для без над под между через после перед ещё " +
        "уже даже только всегда никогда иногда опять снова более менее самый самая самое другой другая другое другие каждый " +
        "какой какая какое какие такой такая такое такие разве хотя пока либо ладно хорошо спасибо привет здравствуйте давай " +
        "давайте смотри смотрите слушай говорить говорит говорю говорим сказал сказала скажи сказать делать делает делаю " +
        "сделать сделал нужен нужна нужны быть буду будешь были бывает бывало кстати вроде почти совсем конечно наверное " +
        "например итак допустим словом общем целом самом деле зачем почему потому откуда куда туда сюда отсюда оттуда где " +
        "кого кому кем чему чем ничего ничто никто нечего некого один одна одно одни раз два три четыре пять шесть семь " +
        "восемь девять десять первый первая второй вторая третий"
        ).split(" ").toSet()

    private fun stem(word: String): String {
        for (ending in ENDINGS) if (word.endsWith(ending) && word.length - ending.length >= 4) return word.dropLast(ending.length)
        return word
    }

    /** At most [maxWords] topic words, e.g. «Тестирование, расшифровка»; null when there is nothing reliable to say. */
    fun suggest(segments: List<TranscriptSegment>, maxWords: Int = 3): String? {
        val tokens = Regex("\\p{L}{4,}").findAll(segments.joinToString(" ") { it.text }.lowercase()).map { it.value }.toList()
        if (tokens.size < 8) return null
        val groups = LinkedHashMap<String, MutableList<String>>()
        for (token in tokens) if (token !in STOP) groups.getOrPut(stem(token)) { mutableListOf() }.add(token)
        val ranked = groups.values.filter { it.size >= 2 }
            .sortedWith(compareByDescending<List<String>> { it.size }.thenByDescending { it.first().length })
        if (ranked.isEmpty()) return null
        val words = ranked.take(maxWords).map { forms -> forms.groupingBy { it }.eachCount().entries
            .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key.length }.thenBy { it.key }).first().key }
        return words.joinToString(", ").replaceFirstChar { it.uppercase() }
    }
}
