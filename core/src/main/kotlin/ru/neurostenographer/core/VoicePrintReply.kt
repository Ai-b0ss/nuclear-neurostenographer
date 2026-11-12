package ru.neurostenographer.core

/** Optional identity IPC must fail closed without dropping valid ASR/diarization. */
object VoicePrintReply {
    const val VERSION = 2
    fun decode(version: Int, ids: List<String>, speech: LongArray?, vectors: FloatArray?,
               early: FloatArray?, late: FloatArray?, earlyMs: LongArray?, lateMs: LongArray?,
               known: Set<String>, audioMs: Long, dim: Int = 192): List<VoicePrint> {
        if (version != VERSION || dim !in 2..4096 || ids.size !in 1..8 ||
            ids.distinct().size != ids.size || ids.any { it.isBlank() || it !in known } ||
            speech?.size != ids.size || earlyMs?.size != ids.size || lateMs?.size != ids.size ||
            vectors?.size != ids.size * dim || early?.size != ids.size * dim ||
            late?.size != ids.size * dim || vectors.any { !it.isFinite() } ||
            early.any { !it.isFinite() } || late.any { !it.isFinite() }) return emptyList()
        if (ids.indices.any { earlyMs[it] !in 3000L..16000L || lateMs[it] !in 3000L..16000L ||
                speech[it] != earlyMs[it] + lateMs[it] || speech[it] > audioMs }) return emptyList()
        return ids.indices.map { i ->
            VoicePrint(ids[i], vectors.copyOfRange(i * dim, (i + 1) * dim), speech[i],
                early.copyOfRange(i * dim, (i + 1) * dim), late.copyOfRange(i * dim, (i + 1) * dim),
                earlyMs[i], lateMs[i])
        }
    }
}
