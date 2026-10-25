plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Optional stable signing configured with GitHub Actions secrets.
 // A missing secret intentionally falls back to the normal ephemeral debug signature.
val signingFile = providers.environmentVariable("BTCAUD_KEYSTORE_PATH").orNull
val signingStorePassword = providers.environmentVariable("BTCAUD_KEYSTORE_PASSWORD").orNull
val signingAlias = providers.environmentVariable("BTCAUD_KEY_ALIAS").orNull
val signingKeyPassword = providers.environmentVariable("BTCAUD_KEY_PASSWORD").orNull
val stableSigning = listOf(signingFile, signingStorePassword, signingAlias, signingKeyPassword)
    .all { !it.isNullOrBlank() }

android {
    signingConfigs {
        if (stableSigning) create("privatePersistentDebug") {
            storeFile = file(signingFile!!)
            storePassword = signingStorePassword
            keyAlias = signingAlias
            keyPassword = signingKeyPassword
        }
    }
    namespace = "com.btcaud.paper"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.btcaud.paper"
        minSdk = 26
        targetSdk = 35
        versionCode = 16
        versionName = "0.16.0-paper"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildTypes {
        getByName("debug") {
            if (stableSigning) signingConfig = signingConfigs.getByName("privatePersistentDebug")
        }
        release { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("androidx.glance:glance-appwidget:1.1.1")
    implementation("androidx.glance:glance-material3:1.1.1")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
}
