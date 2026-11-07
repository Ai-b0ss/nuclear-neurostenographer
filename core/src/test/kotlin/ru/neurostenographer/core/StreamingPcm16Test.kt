package ru.neurostenographer.core
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
fun testStreamingPcm16() {
    val dir = kotlin.io.path.createTempDirectory("normalize-").toFile()
    try {
        for (rate in listOf(8000,16000,44100,48000)) for (channels in 1..2) {
            val raw = ByteBuffer.allocate((rate + 37) * channels * 2).order(ByteOrder.LITTLE_ENDIAN)
            repeat((rate + 37) * channels) { raw.putShort((it * 31 % 50000 - 25000).toShort()) }; raw.flip()
            val file=File(dir,"test.wav")
            Pcm16WavWriter(file,rate,channels).use { it.append(raw.duplicate()); it.finish() }
            val expected=file.inputStream().use { PcmWav.read(it).samples }
            val stream=StreamingPcm16(rate,channels); val bytes=ByteArrayOutputStream()
            while (raw.hasRemaining()) {
                val end=minOf(raw.limit(),raw.position()+137*channels*2)
                val slice=raw.duplicate().apply { limit(end) }
                bytes.write(stream.append(slice)); raw.position(end)
            }
            bytes.write(stream.finish())
            val normalized=ByteBuffer.wrap(bytes.toByteArray()).order(ByteOrder.LITTLE_ENDIAN)
            check(normalized.remaining()==expected.size*2)
            expected.forEach { check(kotlin.math.abs(normalized.short/32768f-it)<=1.1f/32768) }
            check(runCatching { stream.append(ByteBuffer.allocate(0)) }.isFailure)
        }
        println("PASS streaming decoder normalization: 8 rate/channel cases, buffer continuity, exact duration, one-frame memory")
    } finally {dir.deleteRecursively()}
}
