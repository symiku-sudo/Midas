plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
}

val customBuildRoot = providers.gradleProperty("midasBuildRoot").orNull
if (!customBuildRoot.isNullOrBlank()) {
    allprojects {
        val projectSegment = if (path == ":") "root" else path.removePrefix(":").replace(":", "/")
        layout.buildDirectory.set(file("$customBuildRoot/$projectSegment"))
    }
}
