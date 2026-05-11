// android/app/src/main/kotlin/com/telecrm/app/CallRecordingPlugin.kt
package com.telecrm.app

import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.io.File

class CallRecordingPlugin {

    private var mediaRecorder: MediaRecorder? = null
    private var currentFilePath: String? = null
    private val TAG = "CallRecordingPlugin"

    fun handleMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "startRecording" -> {
                val filePath = call.argument<String>("filePath")
                if (filePath == null) {
                    result.error("INVALID_ARGS", "filePath is required", null)
                    return
                }
                startRecording(filePath, result)
            }
            "stopRecording" -> {
                stopRecording(result)
            }
            "isRecording" -> {
                result.success(mediaRecorder != null)
            }
            else -> result.notImplemented()
        }
    }

    private fun startRecording(filePath: String, result: MethodChannel.Result) {
        try {
            // Stop any existing recording first
            stopMediaRecorder()

            // Ensure the directory exists
            val file = File(filePath)
            file.parentFile?.mkdirs()

            mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(/* context not needed for basic recording */)
            } else {
                @Suppress("DEPRECATION")
                MediaRecorder()
            }

            mediaRecorder!!.apply {
                // Use MIC source — this works on all Android versions without root
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioSamplingRate(44100)
                setAudioEncodingBitRate(96000)
                setOutputFile(filePath)
                prepare()
                start()
            }

            currentFilePath = filePath
            Log.d(TAG, "Recording started: $filePath")
            result.success(filePath)

        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording: ${e.message}")
            stopMediaRecorder()
            result.error("RECORDING_ERROR", "Failed to start recording: ${e.message}", null)
        }
    }

    private fun stopRecording(result: MethodChannel.Result) {
        val path = currentFilePath
        try {
            stopMediaRecorder()
            if (path != null && File(path).exists()) {
                Log.d(TAG, "Recording saved: $path")
                result.success(path)
            } else {
                result.success(null)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to stop recording: ${e.message}")
            result.error("RECORDING_ERROR", "Failed to stop recording: ${e.message}", null)
        }
    }

    private fun stopMediaRecorder() {
        try {
            mediaRecorder?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping MediaRecorder: ${e.message}")
        }
        try {
            mediaRecorder?.release()
        } catch (e: Exception) {
            Log.w(TAG, "Error releasing MediaRecorder: ${e.message}")
        }
        mediaRecorder = null
        currentFilePath = null
    }
}
