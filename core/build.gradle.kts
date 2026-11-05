plugins { id("org.jetbrains.kotlin.jvm") }
kotlin { jvmToolchain(17) }
// Pure Kotlin C2 arithmetic is exercised on the host without adding it to ordinary core binaries.
sourceSets.test.get().kotlin.srcDir("../app/src/nemotron/java/ru/neurostenographer/core")
tasks.named<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>("compileTestKotlin") {
    // This adapter is JVM-only: test the actual disk/ring/recovery implementation without Android.
    source(rootProject.file("app/src/realtime/java/ru/neurostenographer/app/RealtimeJournal.kt"))
}

tasks.register<JavaExec>("runCoreTests") {
    group = "verification"
    dependsOn(tasks.named("testClasses"))
    classpath = sourceSets.test.get().runtimeClasspath
    mainClass.set("ru.neurostenographer.core.TranscriptCoreTestKt")
}

tasks.register<JavaExec>("runTermEval") {
    group = "verification"
    description = "Apply BuiltinTerms to a TSV of ASR hypotheses (tools/term_dictionary/eval.py)"
    dependsOn(tasks.named("testClasses"))
    classpath = sourceSets.test.get().runtimeClasspath
    mainClass.set("ru.neurostenographer.core.TermEvalMain")
    args((project.findProperty("termEvalArgs") as String? ?: "").split(" ").filter { it.isNotBlank() })
}
