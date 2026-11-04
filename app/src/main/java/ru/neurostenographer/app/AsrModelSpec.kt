package ru.neurostenographer.app

/** Which ASR bundle this build accepts. Ordinary and RC1 builds use the GigaAM v3 CTC bundle;
 * the separate `-PasrA3=true` test build (applicationId suffix .a3) uses GigaAM v3 e2e RNNT, which emits
 * punctuation and capitals. Its int8 encoder is the Smirnov75 file with unused opset imports removed
 * (tools/asr_20261104/strip_unused_opsets.py): the original declares ai.onnx.ml v5 and ONNX Runtime 1.17.1 refuses it.
 */
data class AsrModelSpec(
    val id: String, val revision: String, val zipName: String, val label: String, val sizeLabel: String,
    val files: Map<String, Pair<String, Long>>, // name -> sha256, max bytes
    val ctcModel: String? = null, val encoder: String? = null, val decoder: String? = null,
    val joiner: String? = null, val tokens: String,
) {
    companion object {
        val CTC = AsrModelSpec(
            id = "sherpa-onnx-1.12.20/gigaam-v3-ctc-int8", revision = "32a4c7cc81809bd132e2d935ab99e9e6ab47fbec",
            zipName = "gigaam-v3.zip", label = "GigaAM v3", sizeLabel = "225 МБ",
            files = linkedMapOf(
                "model.int8.onnx" to ("f86ebfa0429ced91be6054fc344827e9c6c2572f3c318416cd974b06f66437ec" to 224_721_476L),
                "tokens.txt" to ("17cc514451bcceac9c280068c71502f8448f99e9fb1456b8d0761651fd0392f2" to 4096L),
                "LICENSE" to ("f00de6715714c7a63d08639cdbfaa40224eefc407302614bd19f1a8b98c875aa" to 4096L)),
            ctcModel = "model.int8.onnx", tokens = "tokens.txt")

        val E2E_RNNT = AsrModelSpec(
            id = "sherpa-onnx-1.12.20/gigaam-v3-e2e-rnnt-int8-opsetfix",
            revision = "Smirnov75/GigaAM-v3-sherpa-onnx@6888903da215c7735f51101d939f3bfa679fb2b8+opsetfix",
            zipName = "gigaam-v3-e2e-rnnt.zip", label = "GigaAM v3 e2e (с пунктуацией)", sizeLabel = "326 МБ",
            files = linkedMapOf(
                "gigaam_v3_e2e_rnnt_encoder_int8.onnx" to ("75e93f387fa3cf5743e2b702dbc3108214b9769fdf4ae131f4e4c6d6087571ac" to 318_995_831L),
                "gigaam_v3_e2e_rnnt_decoder.onnx" to ("781971998e6a355d6a714f6932a30eab295e7ba0d14fd7e0f78c83b87e811860" to 4_600_058L),
                "gigaam_v3_e2e_rnnt_joint.onnx" to ("602ff7017a93311aad34df1437c8d7f49911353c13d6eae7a6ee7b041339465c" to 2_712_896L),
                "gigaam_v3_e2e_rnnt_tokens.txt" to ("7ddf22514c42c531358182c81446a8159771e9921019f09ae743ea622d40221d" to 13_353L)),
            encoder = "gigaam_v3_e2e_rnnt_encoder_int8.onnx", decoder = "gigaam_v3_e2e_rnnt_decoder.onnx",
            joiner = "gigaam_v3_e2e_rnnt_joint.onnx", tokens = "gigaam_v3_e2e_rnnt_tokens.txt")

        val ACTIVE: AsrModelSpec = if (BuildConfig.ASR_A3) E2E_RNNT else CTC
    }
}
