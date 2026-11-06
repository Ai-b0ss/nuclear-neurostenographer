package ru.neurostenographer.app

/**
 * Sample-by-index view of a recording journal for the full-recording C2 pass. Keeps two 8-second
 * blocks (the mel window and pre-emphasis look one sample back across a block edge), so an hour
 * of capture is read sequentially from disk instead of loaded as one array.
 */
class JournalBlocks(private val samples: Long, private val read: (Long, Int) -> FloatArray,
                    private val blockSize: Int = 16000 * 8) {
    private var currentStart = -1L
    private var current = FloatArray(0)
    private var previousStart = -1L
    private var previous = FloatArray(0)

    init { require(samples in 1..Int.MAX_VALUE.toLong() && blockSize > 0) }

    fun at(index: Int): Float {
        val start = index.toLong() / blockSize * blockSize
        if (start == currentStart) return current[(index - start).toInt()]
        if (start == previousStart) return previous[(index - start).toInt()]
        previousStart = currentStart; previous = current
        currentStart = start
        current = read(start, minOf(blockSize.toLong(), samples - start).toInt())
        return current[(index - start).toInt()]
    }
}
