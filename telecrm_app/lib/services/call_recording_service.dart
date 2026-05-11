// lib/services/call_recording_service.dart
import 'dart:async';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';
import 'package:dio/dio.dart';
import '../core/constants.dart';

const _recordingChannel = MethodChannel('com.telecrm.app/recording');

final callRecordingServiceProvider = Provider<CallRecordingService>((ref) {
  return CallRecordingService();
});

/// Tracks whether call recording is enabled (fetched from app config).
final recordingEnabledProvider = StateProvider<bool>((ref) => false);

/// Tracks whether a recording is currently in progress.
final isRecordingProvider = StateProvider<bool>((ref) => false);

class CallRecordingService {
  final _storage = const FlutterSecureStorage();
  bool _isRecording = false;
  String? _currentFilePath;

  bool get isRecording => _isRecording;

  /// Start recording the microphone audio.
  /// [callLogId] is used to name the file.
  Future<bool> startRecording(int callLogId) async {
    if (_isRecording) return false;
    try {
      final dir = await getTemporaryDirectory();
      final filePath =
          '${dir.path}/recording_call_${callLogId}_${DateTime.now().millisecondsSinceEpoch}.m4a';

      final result = await _recordingChannel.invokeMethod<String>('startRecording', {
        'filePath': filePath,
      });

      if (result != null) {
        _isRecording = true;
        _currentFilePath = result;
        return true;
      }
      return false;
    } on PlatformException catch (e) {
      _isRecording = false;
      return false;
    } catch (e) {
      _isRecording = false;
      return false;
    }
  }

  /// Stop the recording and upload to the server.
  /// Returns true if upload succeeded.
  Future<bool> stopAndUpload(int callLogId) async {
    if (!_isRecording) return false;
    try {
      final savedPath = await _recordingChannel.invokeMethod<String>('stopRecording');
      _isRecording = false;

      if (savedPath == null || !File(savedPath).existsSync()) {
        return false;
      }

      // Upload to server
      final uploaded = await _uploadRecording(callLogId, savedPath);

      // Clean up local file after upload
      try {
        File(savedPath).deleteSync();
      } catch (_) {}

      _currentFilePath = null;
      return uploaded;
    } on PlatformException {
      _isRecording = false;
      return false;
    } catch (e) {
      _isRecording = false;
      return false;
    }
  }

  /// Upload the recording file to the backend.
  Future<bool> _uploadRecording(int callLogId, String filePath) async {
    try {
      final token = await _storage.read(key: AppConstants.tokenKey);
      if (token == null) return false;

      final endpoint = AppConstants.baseUrl +
          AppConstants.uploadRecordingEndpoint.replaceAll('{id}', callLogId.toString());

      final dio = Dio();
      final formData = FormData.fromMap({
        'recording': await MultipartFile.fromFile(
          filePath,
          filename: 'recording_$callLogId.m4a',
        ),
      });

      final response = await dio.post(
        endpoint,
        data: formData,
        options: Options(
          headers: {'Authorization': 'Token $token'},
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 60),
        ),
      );

      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  /// Emergency stop if needed (e.g. app closing).
  Future<void> cancelRecording() async {
    if (!_isRecording) return;
    try {
      final savedPath = await _recordingChannel.invokeMethod<String>('stopRecording');
      _isRecording = false;
      // Delete local file without uploading
      if (savedPath != null) {
        try {
          File(savedPath).deleteSync();
        } catch (_) {}
      }
    } catch (_) {}
    _currentFilePath = null;
  }
}
