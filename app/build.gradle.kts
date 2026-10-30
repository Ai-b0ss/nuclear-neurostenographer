plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
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
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.15" }
    sourceSets.getByName("androidTest").assets.srcDir(rootProject.file(".local/androidTestAssets"))
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
