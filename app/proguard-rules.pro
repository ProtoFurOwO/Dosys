# Reglas de ProGuard/R8 para D.O.S.Y.S
# (minify está desactivado por ahora, pero dejamos las reglas listas)

-keepattributes Signature, *Annotation*, InnerClasses, EnclosingMethod

-dontwarn okhttp3.**
-dontwarn retrofit2.**
-dontwarn kotlinx.serialization.**

# Modelos serializados con kotlinx.serialization
-keep class mx.unach.dosys.data.model.** { *; }
-keepclassmembers class mx.unach.dosys.data.model.** { *; }
