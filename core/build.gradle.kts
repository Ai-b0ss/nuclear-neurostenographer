plugins { id("org.jetbrains.kotlin.jvm") }
kotlin { jvmToolchain(17) }

tasks.register<JavaExec>("runCoreTests") {
    group = "verification"
    dependsOn(tasks.named("testClasses"))
    classpath = sourceSets.test.get().runtimeClasspath
    mainClass.set("ru.neurostenographer.core.TranscriptCoreTestKt")
}
