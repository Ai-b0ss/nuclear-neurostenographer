package ru.neurostenographer.core
/** Batch workloads should block idle ORT workers rather than spend CPU spinning.
 * Supported by the pinned ONNX Runtime1.17.1. Thread count is deliberately unchanged.
 */
object BatchInferencePolicy {
    fun configure(add: (String,String) -> Unit) {
        add("session.intra_op.allow_spinning","0")
        add("session.inter_op.allow_spinning","0")
    }
}
