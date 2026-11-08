package ru.neurostenographer.core

fun testFddtOverlapPlan() {
    val turns = listOf(
        SpeakerTurn(1000,4000,"Speaker 1"),
        SpeakerTurn(2900,3900,"Speaker 2"),
        SpeakerTurn(6000,8000,"Speaker 2"),
        SpeakerTurn(9000,12000,"Speaker 3"))
    val regions = FddtOverlapPlan.regions(turns,14000)
    check(regions == listOf(FddtRegion(2900,3900,listOf("Speaker 1","Speaker 2")))) { regions.toString() }
    check(FddtOverlapPlan.regions(turns,14000,wholeTurns=true) ==
        listOf(FddtRegion(1000,4000,listOf("Speaker 1","Speaker 2"))))
    check(FddtOverlapPlan.regions(listOf(turns[0],turns[2]),14000).isEmpty())
    check(FddtOverlapPlan.regions(listOf(turns[0],SpeakerTurn(3910,4200,"Speaker 2")),14000).isEmpty())
    val mask = FddtOverlapPlan.mask(turns,"Speaker 1",0,16000*5)
    val n = FddtOverlapPlan.frameCount(80000)
    fun state(atMs: Int): Int {
        val index = atMs/40
        return (0..3).single { mask[it*n+index] == 1f }
    }
    check(state(0) == 0 && state(1800) == 1 && state(3200) == 3 && state(4600) == 0)
    for (i in 0 until n) check((0..3).sumOf { mask[it*n+i].toDouble() } == 1.0)
    check(FddtOverlapPlan.decodePieces(listOf("\u2581Пр","ивет",",","\u2581мир","!")) == "Привет, мир!")
    check(FddtOverlapPlan.canReplace(4,mapOf("Speaker 1" to "один два","Speaker 2" to "три четыре"),listOf("Speaker 1","Speaker 2")))
    check(!FddtOverlapPlan.canReplace(10,mapOf("Speaker 1" to "один","Speaker 2" to "два"),listOf("Speaker 1","Speaker 2")))
    check(!FddtOverlapPlan.canReplace(3,mapOf("Speaker 1" to "один","Speaker 2" to ""),listOf("Speaker 1","Speaker 2")))
    check(runCatching { FddtOverlapPlan.frameCount(0) }.isFailure)
    val onset = FddtOverlapPlan.mask(listOf(SpeakerTurn(1010,1990,"quiet")),"quiet",0,48000)
    val onsetFrames = FddtOverlapPlan.frameCount(48000)
    check(onset[onsetFrames+25] == 1f) // Python floor(1.010*25), not point sampling.
    val clipped = FddtOverlapPlan.mask(listOf(SpeakerTurn(0,4000,"quiet")),"quiet",1000,16000)
    val clippedFrames = FddtOverlapPlan.frameCount(16000)
    check(clipped[clippedFrames+24] == 1f && clipped[25] == 1f) // padded final frame is silence
    val perVoiceBase = listOf(TranscriptSegment(0,1000,"loud","слово ".repeat(30).trim()),
        TranscriptSegment(0,1000,"quiet","слово ".repeat(10).trim()))
    check(!FddtOverlapPlan.canReplace(perVoiceBase,
        mapOf("loud" to "слово ".repeat(29),"quiet" to "одно"),listOf("loud","quiet")))
    check(FddtOverlapPlan.canReplace(perVoiceBase,
        mapOf("loud" to "слово ".repeat(29),"quiet" to "слово ".repeat(9)),listOf("loud","quiet")))
    val left = FddtRegion(0,20000,listOf("loud","quiet"))
    val right = FddtRegion(20000,40000,listOf("loud","quiet"))
    val boundaryWord = RecognizedWord(20000,20240,"граница")
    check(!FddtOverlapPlan.owns(left,boundaryWord) && FddtOverlapPlan.owns(right,boundaryWord))
    val uncertain = TranscriptSegment(2000,2240,null,"Привет!",overlappingSpeech=true)
    val candidate = TranscriptSegment(1900,2300,"quiet","Привет, мир",overlappingSpeech=true)
    val attributed = FddtOverlapPlan.refineAttribution(listOf(uncertain),listOf(candidate)).single()
    check(attributed.speakerId == "quiet")
    check(attributed.text == uncertain.text && attributed.startMs == uncertain.startMs && attributed.endMs == uncertain.endMs)
    check(FddtOverlapPlan.refineAttribution(listOf(uncertain),listOf(candidate,candidate.copy(speakerId="loud"))).single() == uncertain)
    check(FddtOverlapPlan.refineAttribution(listOf(uncertain.copy(speakerId="known")),listOf(candidate)).single().speakerId == "known")
    check(FddtOverlapPlan.refineAttribution(listOf(uncertain.copy(text="два слова")),listOf(candidate)).single().speakerId == null)
    println("PASS FDDT hybrid overlap planning")
}
