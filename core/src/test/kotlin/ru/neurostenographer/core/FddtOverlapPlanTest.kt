package ru.neurostenographer.core

fun testFddtOverlapPlan() {
    val turns = listOf(
        SpeakerTurn(1000,4000,"Speaker 1"),
        SpeakerTurn(2900,3900,"Speaker 2"),
        SpeakerTurn(6000,8000,"Speaker 2"),
        SpeakerTurn(9000,12000,"Speaker 3"))
    val regions = FddtOverlapPlan.regions(turns,14000)
    check(regions == listOf(FddtRegion(1000,4000,listOf("Speaker 1","Speaker 2")))) { regions.toString() }
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
    println("PASS FDDT hybrid overlap planning")
}
