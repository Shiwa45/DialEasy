// lib/core/app_config_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_client.dart';
import 'constants.dart';

// ─────────────────────────────────────────────────────────
// MODEL
// ─────────────────────────────────────────────────────────
class AppConfig {
  final List<Map<String, String>> leadStatuses;
  final List<Map<String, String>> callDispositions;
  final Map<String, dynamic> agentTargets;
  final Map<String, dynamic> appSettings;

  const AppConfig({
    required this.leadStatuses,
    required this.callDispositions,
    required this.agentTargets,
    required this.appSettings,
  });

  factory AppConfig.fromJson(Map<String, dynamic> json) {
    List<Map<String, String>> _parseChoices(dynamic raw) {
      if (raw == null) return [];
      return (raw as List)
          .map((e) => {
                'value': (e['value'] ?? '').toString(),
                'label': (e['label'] ?? '').toString(),
              })
          .toList();
    }

    return AppConfig(
      leadStatuses: _parseChoices(json['lead_statuses']),
      callDispositions: _parseChoices(json['call_dispositions']),
      agentTargets: Map<String, dynamic>.from(json['agent_targets'] ?? {}),
      appSettings: Map<String, dynamic>.from(json['app_settings'] ?? {}),
    );
  }

  bool get autoDialEnabled => appSettings['auto_dial_enabled'] == true;
  bool get notificationsEnabled => appSettings['notification_enabled'] == true;
  bool get offlineModeEnabled => appSettings['offline_mode_enabled'] == true;
  int get dailyCallsTarget => (agentTargets['daily_calls'] as num?)?.toInt() ?? 50;
  int get monthlyConversionsTarget =>
      (agentTargets['monthly_conversions'] as num?)?.toInt() ?? 10;

  // Fallback static config used before API responds
  static AppConfig get defaults => AppConfig(
        leadStatuses: const [
          {'value': 'new', 'label': 'New'},
          {'value': 'contacted', 'label': 'Contacted'},
          {'value': 'interested', 'label': 'Interested'},
          {'value': 'not_interested', 'label': 'Not Interested'},
          {'value': 'callback', 'label': 'Callback Later'},
          {'value': 'wrong_number', 'label': 'Wrong Number'},
          {'value': 'not_reachable', 'label': 'Not Reachable'},
          {'value': 'converted', 'label': 'Converted'},
        ],
        callDispositions: const [
          {'value': 'interested', 'label': 'Interested'},
          {'value': 'not_interested', 'label': 'Not Interested'},
          {'value': 'callback', 'label': 'Callback Later'},
          {'value': 'not_reachable', 'label': 'Not Reachable'},
          {'value': 'busy', 'label': 'Busy'},
          {'value': 'wrong_number', 'label': 'Wrong Number'},
          {'value': 'voicemail', 'label': 'Voicemail'},
          {'value': 'follow_up', 'label': 'Follow-up Required'},
        ],
        agentTargets: const {
          'daily_calls': 50,
          'monthly_conversions': 10,
        },
        appSettings: const {
          'auto_dial_enabled': true,
          'notification_enabled': true,
          'offline_mode_enabled': true,
        },
      );
}

// ─────────────────────────────────────────────────────────
// PROVIDER
// ─────────────────────────────────────────────────────────
final appConfigProvider =
    StateNotifierProvider<AppConfigNotifier, AppConfig>((ref) {
  return AppConfigNotifier(ref.read(apiClientProvider));
});

class AppConfigNotifier extends StateNotifier<AppConfig> {
  final ApiClient _client;
  AppConfigNotifier(this._client) : super(AppConfig.defaults) {
    _load();
  }

  Future<void> _load() async {
    try {
      final response = await _client.dio.get(AppConstants.appConfigEndpoint);
      state = AppConfig.fromJson(response.data);
    } catch (_) {
      // Keep defaults on error
    }
  }

  Future<void> refresh() => _load();
}
