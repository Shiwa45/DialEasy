// lib/services/activity_tracking_service.dart
import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../core/constants.dart';

// ─── Provider ────────────────────────────────────────────────────────────────

final activityTrackingServiceProvider = Provider<ActivityTrackingService>((ref) {
  return ActivityTrackingService();
});

/// Tracks the currently active session ID (null = no session).
final activeSessionIdProvider = StateProvider<int?>((ref) => null);

// ─── Event types ─────────────────────────────────────────────────────────────

enum ActivityEvent {
  sessionStart,
  sessionEnd,
  callStarted,
  callEnded,
  dispositionStarted,
  dispositionSubmitted,
}

extension ActivityEventExt on ActivityEvent {
  String get apiValue {
    switch (this) {
      case ActivityEvent.sessionStart:       return 'session_start';
      case ActivityEvent.sessionEnd:         return 'session_end';
      case ActivityEvent.callStarted:        return 'call_started';
      case ActivityEvent.callEnded:          return 'call_ended';
      case ActivityEvent.dispositionStarted: return 'disposition_started';
      case ActivityEvent.dispositionSubmitted: return 'disposition_submitted';
    }
  }
}

// ─── Service ─────────────────────────────────────────────────────────────────

class ActivityTrackingService {
  final _storage = const FlutterSecureStorage();
  int? _currentSessionId;

  int? get currentSessionId => _currentSessionId;

  Dio _dio() => Dio();

  Future<Options> _authOptions() async {
    final token = await _storage.read(key: AppConstants.tokenKey);
    return Options(
      headers: {'Authorization': 'Token $token'},
      sendTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
    );
  }

  String get _base => AppConstants.baseUrl;

  // ── Start a dialer session ────────────────────────────────────────────────

  /// Call when agent taps "Start Auto-Dial".
  /// Returns the session ID from the server.
  Future<int?> startSession() async {
    try {
      final response = await _dio().post(
        '$_base${AppConstants.startSessionEndpoint}',
        options: await _authOptions(),
      );
      final id = response.data['session_id'] as int?;
      _currentSessionId = id;
      return id;
    } catch (_) {
      return null;
    }
  }

  // ── Log an event ──────────────────────────────────────────────────────────

  /// Fire-and-forget event log. Safe to call without awaiting.
  Future<void> logEvent(
    ActivityEvent event, {
    int? sessionId,
    int? leadId,
    int? callLogId,
  }) async {
    final sid = sessionId ?? _currentSessionId;
    if (sid == null) return; // no active session — ignore silently
    try {
      final url = '$_base${AppConstants.logEventEndpoint}'.replaceAll(
        '{session_id}', sid.toString(),
      );
      await _dio().post(
        url,
        data: {
          'event_type': event.apiValue,
          if (leadId != null) 'lead_id': leadId,
          if (callLogId != null) 'call_log_id': callLogId,
        },
        options: await _authOptions(),
      );
    } catch (_) {
      // Best-effort — never crash the UI for a tracking event
    }
  }

  // ── End the session ───────────────────────────────────────────────────────

  /// Call when agent stops the dialer.
  Future<void> endSession({int? sessionId}) async {
    final sid = sessionId ?? _currentSessionId;
    if (sid == null) return;
    await logEvent(ActivityEvent.sessionEnd, sessionId: sid);
    _currentSessionId = null;
  }

  void clearSession() {
    _currentSessionId = null;
  }
}
