// android/app/src/main/kotlin/com/telecrm/app/MainActivity.kt
package com.telecrm.app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    private val CALL_CHANNEL = "com.telecrm.app/call"
    private val RECORDING_CHANNEL = "com.telecrm.app/recording"

    private val callRecordingPlugin = CallRecordingPlugin()

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Method channel for native call helpers
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CALL_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getSimInfo" -> {
                        result.success(mapOf("simCount" to 1))
                    }
                    else -> result.notImplemented()
                }
            }

        // Method channel for call recording
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, RECORDING_CHANNEL)
            .setMethodCallHandler { call, result ->
                callRecordingPlugin.handleMethodCall(call, result)
            }
    }
}
