plugins { id("org.jetbrains.kotlin.jvm") }
kotlin { jvmToolchain(17) }

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
