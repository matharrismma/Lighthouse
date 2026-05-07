# Concordance Launcher ProGuard rules

# Keep serialization models
-keepattributes *Annotation*
-keep class run.concordance.launcher.data.** { *; }

# OkHttp
-dontwarn okhttp3.**
-keep class okhttp3.** { *; }

# Kotlin serialization
-keepattributes RuntimeVisibleAnnotations
-keep @kotlinx.serialization.Serializable class * { *; }
