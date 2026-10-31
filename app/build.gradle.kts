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
android {
    namespace = "ru.neurostenographer.app"
    compileSdk = 35
    buildToolsVersion = "35.0.0"
    defaultConfig {
        applicationId = "ru.neurostenographer.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-alpha"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "SHERPA_RUNTIME_SHA256", "\"$selectedRuntimeDigest\"")
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
    // Explicit private cloud-test variant; ordinary builds never include model/audio assets.
    if (providers.gradleProperty("asrSmoke").orNull == "true") {
        sourceSets.getByName("debug").apply {
            java.srcDir("src/asrSmoke/java")
            assets.srcDir(rootProject.file(".local/androidTestAssets"))
            manifest.srcFile("src/asrSmoke/AndroidManifest.xml")
        }
    }
    packaging.jniLibs.excludes += setOf("**/libsherpa-onnx-c-api.so", "**/libsherpa-onnx-cxx-api.so")
}
dependencies {
    implementation(files("libs/sherpa-onnx-1.12.20.aar"))
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
