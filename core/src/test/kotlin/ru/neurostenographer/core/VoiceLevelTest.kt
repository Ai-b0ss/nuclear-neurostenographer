package ru.neurostenographer.core
fun testVoiceLevel() {
    check(VoiceLevel.measure(ShortArray(160)) == 0f)
    check(VoiceLevel.measure(shortArrayOf(Short.MIN_VALUE)) == 1f)
    check(VoiceLevel.measure(shortArrayOf(0, 32767), 1) == 0f)
    val quiet = VoiceLevel.measure(ShortArray(160) { 1000 })
    val loud = VoiceLevel.measure(ShortArray(160) { 16000 })
    check(quiet > 0f && loud > quiet && loud <= 1f)
    println("PASS actual microphone PCM level: silence, loudness, bounds, valid samples")
}
