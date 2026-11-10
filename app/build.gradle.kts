import java.security.MessageDigest
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
val runtimeFile = file("libs/sherpa-onnx-1.12.20.aar")
val runtimeLock = Properties().apply {
    rootProject.file("tools/runtime/runtime.properties").inputStream().use { load(it) }
}
fun runtimeDigest(): String = if (!runtimeFile.isFile) "UNPROVISIONED" else {
    val digest = MessageDigest.getInstance("SHA-256")
    runtimeFile.inputStream().use { stream ->
        val buffer = ByteArray(65536)
        while (true) {
            val count = stream.read(buffer)
            if (count < 0) break
            digest.update(buffer, 0, count)
        }
    }
    digest.digest().joinToString("") { "%02x".format(it) }
}
val selectedRuntimeDigest = runtimeDigest()
val verifySherpaRuntime by tasks.registering {
    doLast {
        val expected = providers.gradleProperty("candidateRuntimeSha256").orNull
            ?: if (providers.gradleProperty("allowUpstreamRuntime").orNull == "true")
                runtimeLock.getProperty("upstream_sha256") else runtimeLock.getProperty("sha256")
        check(expected.matches(Regex("[0-9a-f]{64}")) && runtimeDigest() == expected) {
            "Unprovisioned/unapproved runtime. Run python tools/provision_asr.py; upstream requires explicit regression opt-in."
        }
    }
}
tasks.named("preBuild").configure { dependsOn(verifySherpaRuntime) }
// Research prototype of Nemotron 3 INT8. Ordinary builds contain none of it and keep C0.
val nemotronPrototype = providers.gradleProperty("nemotronPrototype").orNull == "true"
val nemotronProduct = providers.gradleProperty("nemotronProduct").orNull == "true"
val c2Candidate = providers.gradleProperty("c2Candidate").orNull == "true"
check(!(nemotronPrototype && nemotronProduct)) { "Prototype and product are separate variants" }
check(!c2Candidate || nemotronProduct) { "C2 candidate requires -PnemotronProduct=true" }
val nemotronEnabled = nemotronPrototype || nemotronProduct
// Separate test build with GigaAM v3 e2e RNNT (punctuation); never the RC1 applicationId.
val asrA3 = providers.gradleProperty("asrA3").orNull == "true"
val englishAuto = providers.gradleProperty("englishAuto").orNull == "true"
val fddtHybrid = providers.gradleProperty("fddtHybrid").orNull == "true"
val fddtQa = providers.gradleProperty("fddtQa").orNull == "true"
check(!fddtQa || fddtHybrid) { "FDDT QA requires -PfddtHybrid=true" }
check(!fddtHybrid || (asrA3 && nemotronProduct && !c2Candidate && !nemotronPrototype)) {
    "FDDT hybrid requires product A3 + C2; build as a separate QA app"
}
if (englishAuto) check(rootProject.file(".local/englishAssets/whisper-tiny.zip").isFile) {
    "English auto detection requires the pinned bundled .local/englishAssets/whisper-tiny.zip"
}
// Isolated physical-device acceptance; never replace the signed contest application.
val solHighAcceptance = providers.gradleProperty("solHighAcceptance").orNull == "true"
check(!solHighAcceptance || (asrA3 && nemotronProduct && !c2Candidate && !nemotronPrototype)) {
    "Sol High acceptance requires the A3+C2 product configuration"
}
// Live transcription is part of the product (A3 + C2) unless -Prealtime=false; -PrealtimeSideBySide=true keeps the
// former separate ".realtime" test package.
val realtimeSideBySide = providers.gradleProperty("realtimeSideBySide").orNull == "true"
val realtime = providers.gradleProperty("realtime").orNull?.toBoolean()
    ?: (realtimeSideBySide || (nemotronProduct && asrA3 && !solHighAcceptance && !c2Candidate && !nemotronPrototype))
check(!realtime || (asrA3 && nemotronProduct && !c2Candidate && !nemotronPrototype)) {
    "Realtime requires A3 + product C2 and its own application ID"
}
check(!realtime || (providers.gradleProperty("litertProbe").orNull != "true" &&
    providers.gradleProperty("asrSmoke").orNull != "true")) { "Realtime cannot share another experiment's manifest or applicationId" }
check(!(asrA3 && (c2Candidate || nemotronPrototype))) { "A3 test build is separate from C2 candidate/prototype" }
android {
    namespace = "ru.neurostenographer.app"
    compileSdk = 35
    buildToolsVersion = "35.0.0"
    defaultConfig {
        applicationId = "ru.neurostenographer.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 21
        versionName = "0.4.0"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "SHERPA_RUNTIME_SHA256", "\"$selectedRuntimeDigest\"")
        buildConfigField("boolean", "NEMOTRON_PROTOTYPE", nemotronEnabled.toString())
        buildConfigField("boolean", "ASR_A3", asrA3.toString())
        buildConfigField("boolean", "ENGLISH_AUTO", englishAuto.toString())
        buildConfigField("boolean", "REALTIME", realtime.toString())
        buildConfigField("boolean", "FDDT_HYBRID", fddtHybrid.toString())
        buildConfigField("boolean", "FDDT_WORD_RECOVERY",
            (providers.gradleProperty("fddtWordRecovery").orNull == "true").toString())
        manifestPlaceholders["appLabel"] = "Нейростенограф"
    }
    // Optional workspace-owned debug key for restricted local build environments.
    providers.gradleProperty("localDebugStore").orNull?.let { debugKeyRelativePath ->
        signingConfigs.getByName("debug") {
            storeFile = rootProject.file(debugKeyRelativePath)
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }
    // Release key lives outside the repository: -PreleaseStore=<path> -PreleaseStorePassword=... -PreleaseKeyAlias=...
    providers.gradleProperty("releaseStore").orNull?.let { store ->
        signingConfigs.create("release") {
            storeFile = file(store)
            storePassword = providers.gradleProperty("releaseStorePassword").get()
            keyAlias = providers.gradleProperty("releaseKeyAlias").get()
            keyPassword = providers.gradleProperty("releaseStorePassword").get()
        }
        buildTypes.getByName("release").signingConfig = signingConfigs.getByName("release")
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true; buildConfig = true }
    if (englishAuto) sourceSets.getByName("main").assets.srcDir(rootProject.file(".local/englishAssets"))
    if (providers.gradleProperty("checkpointQa").orNull == "true") {
        defaultConfig.applicationIdSuffix = ".checkpoint"
        defaultConfig.manifestPlaceholders["appLabel"] = "Нейростенограф проверка"
    }
    if (fddtHybrid) {
        check(providers.gradleProperty("checkpointQa").orNull != "true")
        if (fddtQa) {
            defaultConfig.applicationIdSuffix = ".fddtqa"
            defaultConfig.manifestPlaceholders["appLabel"] = "Нейростенограф проверка"
        }
        val fddtAssets = rootProject.file(".local/fddtAssets")
        for (file in listOf("encoder_fddt.int8.onnx", "decoder.onnx", "joint.onnx", "tokens.txt")) {
            check(fddtAssets.resolve(file).isFile) { "FDDT QA model asset missing: $file" }
        }
        sourceSets.getByName("main").assets.srcDir(fddtAssets)
    }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.15" }
    // QA uses only its named fixtures, never stale models/audio from prior test runs.
    sourceSets.getByName("androidTest").assets.srcDir(rootProject.file(
        if (solHighAcceptance) ".local/solHighTestAssets" else ".local/androidTestAssets"))
    if (englishAuto) sourceSets.getByName("androidTest").assets.srcDir(rootProject.file(".local/englishTestAssets"))
    // Separate opt-in evaluation class, not an implicit benchmark during UI QA.
    if (providers.gradleProperty("russianBenchmark").orNull == "true") {
        sourceSets.getByName("androidTest").java.srcDir("src/benchmarkTest/java")
    }
    // Explicit private cloud-test variant; ordinary builds never include model/audio assets.
    if (providers.gradleProperty("asrSmoke").orNull == "true") {
        sourceSets.getByName("debug").apply {
            java.srcDir("src/asrSmoke/java")
            assets.srcDir(rootProject.file(".local/androidTestAssets"))
            manifest.srcFile("src/asrSmoke/AndroidManifest.xml")
        }
    }
    // Side-by-side test install only; the product (A3 + C2) keeps the contest applicationId.
    if (providers.gradleProperty("a3SideBySide").orNull == "true") {
        defaultConfig.applicationIdSuffix = ".a3"
        defaultConfig.manifestPlaceholders["appLabel"] = "Нейростенограф A3"
    }
    if (solHighAcceptance) {
        check(providers.gradleProperty("a3SideBySide").orNull != "true")
        defaultConfig.applicationIdSuffix = ".solhigh"
        defaultConfig.manifestPlaceholders["appLabel"] = "Нейростенограф Sol QA"
    }
    packaging.jniLibs.excludes += setOf("**/libsherpa-onnx-c-api.so", "**/libsherpa-onnx-cxx-api.so")
    // FDDT helper Java sources compile in all variants, so ORT classes remain
    // a compile dependency. However, without Nemotron/FDDT, its standalone JNI
    // layer must NOT ship in the ordinary sherpa-only Android application.
    packaging.jniLibs.pickFirsts += "**/libonnxruntime.so"
    if (!nemotronEnabled) packaging.jniLibs.excludes += "**/libonnxruntime4j_jni.so"
    if (realtime) {
        if (realtimeSideBySide) {
            defaultConfig.applicationIdSuffix = ".realtime"
            defaultConfig.manifestPlaceholders["appLabel"] = "Нейростенограф realtime (эксперимент)"
        }
        check(rootProject.file(".local/realtimeAssets/silero_vad.onnx").isFile) {
            "Live mode needs .local/realtimeAssets/silero_vad.onnx (SHA-256 9e2449e1…1fd6), or build with -Prealtime=false"
        }
        sourceSets.getByName("main").apply {
            java.srcDir("src/realtime/java")
            assets.srcDir("src/realtime/assets")
            assets.srcDir(rootProject.file(".local/realtimeAssets"))
        }
        sourceSets.getByName("debug").manifest.srcFile("src/realtime/AndroidManifest.xml")
        sourceSets.getByName("release").manifest.srcFile("src/realtime/AndroidManifest.xml")
        sourceSets.getByName("androidTest").java.srcDir("src/realtimeTest/java")
    }
    if (nemotronEnabled) {
        // Research and candidate variants use distinct applicationIds.
        // The main product variant retains the contest applicationId.
        if (nemotronPrototype) {
            defaultConfig.applicationIdSuffix = ".c2"
            defaultConfig.manifestPlaceholders["appLabel"] = "Нейро-стенографист C2"
        }
        if (c2Candidate) {
            defaultConfig.applicationIdSuffix = ".c2candidate"
            defaultConfig.manifestPlaceholders["appLabel"] = "Нейро-стенографист C2 кандидат"
        }
        sourceSets.getByName("main").apply {
            java.srcDir("src/nemotron/java")
            assets.srcDir("src/nemotron/assets")
            if (nemotronProduct) assets.srcDir(rootProject.file(
                providers.gradleProperty("productAssetsDir").orNull ?: ".local/productAssets"))
        }
        sourceSets.getByName("androidTest").java.srcDir("src/nemotronTest/java")
        // ONNX Runtime duplicate handling is applied to all build types above.
    }
    // Comparison probe only; never part of a product build.
    if (providers.gradleProperty("litertProbe").orNull == "true") {
        check(!nemotronPrototype) { "Build the LiteRT probe and the C2 prototype separately" }
        defaultConfig.applicationIdSuffix = ".litert"
        sourceSets.getByName("androidTest").java.srcDirs("src/litertProbe/java", "src/litertProbeTest/java")
        kotlinOptions { freeCompilerArgs += "-Xskip-metadata-version-check" }
        androidResources { noCompress += "tflite" }
    }
}
dependencies {
    implementation(files("libs/sherpa-onnx-1.12.20.aar"))
    // Needed at compile time by FddtOnnxRecognizer.java even in default builds.
    // The unused JNI implementation is excluded when Nemotron is disabled.
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.17.1")
    if (providers.gradleProperty("litertProbe").orNull == "true") androidTestImplementation("com.google.ai.edge.litert:litert:2.2.0")
    implementation(project(":core"))
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
