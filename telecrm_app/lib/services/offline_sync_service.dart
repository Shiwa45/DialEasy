// lib/services/offline_sync_service.dart
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/api_client.dart';
import '../core/constants.dart';

final offlineSyncProvider = Provider<OfflineSyncService>((ref) {
  return OfflineSyncService(ref.read(apiClientProvider));
});

// ─────────────────────────────────────────────────────────
// PENDING ACTION MODEL
// ─────────────────────────────────────────────────────────
class PendingAction {
  final String id;
  final String type; // 'call_log' | 'follow_up' | 'lead_update'
  final Map<String, dynamic> data;
  final DateTime createdAt;

  PendingAction({
    required this.id,
    required this.type,
    required this.data,
    required this.createdAt,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'data': data,
        'createdAt': createdAt.toIso8601String(),
      };

  factory PendingAction.fromJson(Map<String, dynamic> json) => PendingAction(
        id: json['id'],
        type: json['type'],
        data: Map<String, dynamic>.from(json['data']),
        createdAt: DateTime.parse(json['createdAt']),
      );
}

// ─────────────────────────────────────────────────────────
// SERVICE
// ─────────────────────────────────────────────────────────
class OfflineSyncService {
  final ApiClient _client;
  static const _storageKey = 'offline_pending_actions';

  OfflineSyncService(this._client);

  /// Queue a call log to be synced later
  Future<void> queueCallLog({
    required int leadId,
    required String disposition,
    String? remarks,
    Duration? duration,
    String? leadStatus,
  }) async {
    await _enqueue(PendingAction(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      type: 'call_log',
      data: {
        'lead_id': leadId,
        'disposition': disposition,
        if (remarks != null) 'remarks': remarks,
        if (duration != null) 'duration_seconds': duration.inSeconds,
        if (leadStatus != null) 'lead_status': leadStatus,
        'call_date': DateTime.now().toIso8601String(),
      },
      createdAt: DateTime.now(),
    ));
  }

  /// Queue a follow-up to be synced later
  Future<void> queueFollowUp({
    required int leadId,
    required String followUpDate,
    required String followUpTime,
    String? remarks,
  }) async {
    await _enqueue(PendingAction(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      type: 'follow_up',
      data: {
        'lead_id': leadId,
        'follow_up_date': followUpDate,
        'follow_up_time': followUpTime,
        if (remarks != null) 'remarks': remarks,
      },
      createdAt: DateTime.now(),
    ));
  }

  /// Get count of pending offline actions
  Future<int> getPendingCount() async {
    final pending = await _loadPending();
    return pending.length;
  }

  /// Sync all pending actions to the server
  Future<SyncResult> syncAll() async {
    final pending = await _loadPending();
    if (pending.isEmpty) return SyncResult(synced: 0, failed: 0);

    int synced = 0;
    int failed = 0;
    final remaining = <PendingAction>[];

    // Build bulk payload
    final callLogs = <Map<String, dynamic>>[];
    final followUps = <Map<String, dynamic>>[];
    final leadUpdates = <Map<String, dynamic>>[];

    for (final action in pending) {
      switch (action.type) {
        case 'call_log':
          callLogs.add(action.data);
          break;
        case 'follow_up':
          followUps.add(action.data);
          break;
        case 'lead_update':
          leadUpdates.add(action.data);
          break;
      }
    }

    try {
      final response = await _client.dio.post(
        AppConstants.syncUploadEndpoint,
        data: {
          'call_logs': callLogs,
          'follow_ups': followUps,
          'lead_updates': leadUpdates,
        },
      );
      final results = response.data;
      synced = (results['call_logs']?['success'] ?? 0) +
          (results['follow_ups']?['success'] ?? 0) +
          (results['lead_updates']?['success'] ?? 0);
      failed = (results['call_logs']?['failed'] ?? 0) +
          (results['follow_ups']?['failed'] ?? 0) +
          (results['lead_updates']?['failed'] ?? 0);

      // Clear successfully synced
      if (failed == 0) {
        await _savePending([]);
      }
    } catch (e) {
      // Keep all pending if network fails
      failed = pending.length;
    }

    return SyncResult(synced: synced, failed: failed);
  }

  // ─────────────────────────────────────────────────────
  // Internal helpers
  // ─────────────────────────────────────────────────────
  Future<void> _enqueue(PendingAction action) async {
    final pending = await _loadPending();
    pending.add(action);
    await _savePending(pending);
  }

  Future<List<PendingAction>> _loadPending() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey);
    if (raw == null) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list.map((e) => PendingAction.fromJson(e)).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _savePending(List<PendingAction> actions) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
        _storageKey, jsonEncode(actions.map((a) => a.toJson()).toList()));
  }
}

class SyncResult {
  final int synced;
  final int failed;
  const SyncResult({required this.synced, required this.failed});
}
