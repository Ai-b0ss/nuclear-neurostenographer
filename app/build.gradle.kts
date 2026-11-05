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
val nativeAsrProbe = providers.gradleProperty("nativeAsrProbe").orNull == "true"
val nativeAsrCandidate = providers.gradleProperty("nativeAsrCandidate").orNull == "true"
val nemotronEnabled = nemotronPrototype || nemotronProduct
check(!(nemotronPrototype && nemotronProduct)) { "Prototype and product are separate variants" }
check(!c2Candidate || nemotronProduct) { "C2 candidate requires -PnemotronProduct=true" }
check(!nativeAsrProbe || nemotronPrototype) { "Native ASR parity probe requires -PnemotronPrototype=true" }
check(!nativeAsrCandidate || nemotronEnabled) { "Native ASR candidate requires a C2 variant" }
check(!(nativeAsrProbe && nativeAsrCandidate)) { "Choose either the isolated parity probe or candidate ASR" }
val nativeAsrEnabled = nativeAsrProbe || nativeAsrCandidate
android {
    namespace = "ru.neurostenographer.app"
    compileSdk = 35
    buildToolsVersion = "35.0.0"
    defaultConfig {
        applicationId = "ru.neurostenographer.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "0.2.0-contest"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "SHERPA_RUNTIME_SHA256", "\"$selectedRuntimeDigest\"")
        buildConfigField("boolean", "NEMOTRON_PROTOTYPE", nemotronEnabled.toString())
        buildConfigField("boolean", "NATIVE_ASR_CANDIDATE", nativeAsrCandidate.toString())
        manifestPlaceholders["appLabel"] = "Нейро-стенографист"
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
    composeOptions { kotlinCompilerExtensionVersion = "1.5.15" }
    sourceSets.getByName("androidTest").assets.srcDir(rootProject.file(".local/androidTestAssets"))
    // Separate opt-in evaluation class, not an implicit benchmark during UI QA.
    if (providers.gradleProperty("russianBenchmark").orNull == "true") {
        sourceSets.getByName("androidTest").java.srcDir("src/benchmarkTest/java")
    }
    if (providers.gradleProperty("windowPolicyProbe").orNull == "true") {
        sourceSets.getByName("androidTest").java.srcDir("src/windowPolicyProbe/java")
    }
    if (providers.gradleProperty("asrHeadProbe").orNull == "true") {
        check(nativeAsrCandidate) { "ASR head probe requires -PnativeAsrCandidate=true" }
        sourceSets.getByName("androidTest").java.srcDir("src/asrHeadProbe/java")
    }
    if (providers.gradleProperty("diarThresholdProbe").orNull == "true") {
        sourceSets.getByName("androidTest").java.srcDir("src/diarThresholdProbe/java")
    }
    // Explicit private cloud-test variant; ordinary builds never include model/audio assets.
    if (providers.gradleProperty("asrSmoke").orNull == "true") {
        sourceSets.getByName("debug").apply {
            java.srcDir("src/asrSmoke/java")
            assets.srcDir(rootProject.file(".local/androidTestAssets"))
            manifest.srcFile("src/asrSmoke/AndroidManifest.xml")
        }
    }
    packaging.jniLibs.excludes += "**/libsherpa-onnx-cxx-api.so"
    if (!nativeAsrEnabled) packaging.jniLibs.excludes += "**/libsherpa-onnx-c-api.so"
    if (nemotronEnabled) {
        ndkVersion = "26.1.10909125"
        externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt") } }
        if (nativeAsrEnabled) {
            defaultConfig.externalNativeBuild.cmake.arguments += "-DNATIVE_ASR_C_API=ON"
            sourceSets.getByName("main").jniLibs.srcDir(rootProject.file(".local/native-runtime/probe-jni"))
        }
        if (nativeAsrProbe) {
            defaultConfig.externalNativeBuild.cmake.arguments += "-DNATIVE_ASR_PROBE=ON"
            sourceSets.getByName("main").java.srcDir("src/nativeAsrProbe/java")
            sourceSets.getByName("androidTest").java.srcDir("src/nativeAsrProbeTest/java")
        }
        if (nativeAsrCandidate) {
            defaultConfig.externalNativeBuild.cmake.arguments += "-DNATIVE_ASR_CANDIDATE=ON"
            sourceSets.getByName("androidTest").java.srcDir("src/nativeAsrCandidateTest/java")
        }
        if (nativeAsrCandidate && providers.gradleProperty("diarThresholdProbe").orNull == "true") {
            defaultConfig.externalNativeBuild.cmake.arguments += "-DSILERO_GAP_PROBE=ON"
        }
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
        if (providers.gradleProperty("pageSizeProbe").orNull == "true") {
            defaultConfig.applicationIdSuffix = ".pageprobe"
        }
        sourceSets.getByName("main").apply {
            java.srcDir("src/nemotron/java")
            assets.srcDir("src/nemotron/assets")
            if (nemotronProduct) assets.srcDir(rootProject.file(".local/productAssets"))
        }
        sourceSets.getByName("androidTest").java.srcDir("src/nemotronTest/java")
        // The sherpa AAR already provides ONNX Runtime 1.17.1. C2 uses its native C API.
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
