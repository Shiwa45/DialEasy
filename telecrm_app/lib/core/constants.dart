// lib/core/constants.dart
class AppConstants {
  // ─── API BASE URL ──────────────────────────────────────────────────────────
  // Change this to your production server URL
  static const String baseUrl = 'http://192.168.1.5:8000/api'; // Local LAN IP for mobile testing
  // static const String baseUrl = 'http://10.0.2.2:8000/api'; // Android emulator

  // ─── AUTH ──────────────────────────────────────────────────────────────────
  static const String loginEndpoint = '/auth/login/';
  static const String logoutEndpoint = '/auth/logout/';
  static const String profileEndpoint = '/auth/profile/';

  // ─── LEADS ─────────────────────────────────────────────────────────────────
  static const String leadsEndpoint = '/leads/';
  static const String myLeadsEndpoint = '/leads/my_leads/';
  static const String searchLeadsEndpoint = '/search/leads/';
  static const String bulkUpdateLeadsEndpoint = '/leads/bulk-update/';

  // ─── CALL LOGS ─────────────────────────────────────────────────────────────
  static const String callLogsEndpoint = '/call-logs/';
  static const String uploadRecordingEndpoint = '/call-logs/{id}/upload-recording/';

  // ─── ACTIVITY TRACKING ─────────────────────────────────────────────────────
  static const String startSessionEndpoint = '/activity/session/start/';
  static const String logEventEndpoint = '/activity/session/{session_id}/event/';

  // ─── FOLLOW-UPS ────────────────────────────────────────────────────────────
  static const String followUpsEndpoint = '/follow-ups/';
  static const String todayFollowUpsEndpoint = '/follow-ups/today/';
  static const String overdueFollowUpsEndpoint = '/follow-ups/overdue/';
  static const String upcomingFollowUpsEndpoint = '/follow-ups/upcoming/';
  static const String followUpStatsEndpoint = '/follow-ups/stats/';
  static const String followUpDashboardEndpoint = '/follow-ups/dashboard/';

  // ─── DASHBOARD ─────────────────────────────────────────────────────────────
  static const String dashboardEndpoint = '/agent/dashboard/';
  static const String agentStatsEndpoint = '/agent/stats/';
  static const String performanceSummaryEndpoint = '/performance/summary/';

  // ─── UTILS ─────────────────────────────────────────────────────────────────
  static const String leadStatusChoicesEndpoint = '/utils/lead-status-choices/';
  static const String callDispositionChoicesEndpoint = '/utils/call-disposition-choices/';
  static const String appConfigEndpoint = '/utils/app-config/';

  // ─── SYNC ──────────────────────────────────────────────────────────────────
  static const String syncUploadEndpoint = '/sync/upload/';
  static const String syncDownloadEndpoint = '/sync/download/';

  // ─── LOCAL STORAGE KEYS ────────────────────────────────────────────────────
  static const String tokenKey = 'auth_token';
  static const String userKey = 'user_data';
  static const String agentProfileKey = 'agent_profile';
  static const String appConfigKey = 'app_config';

  // ─── APP ───────────────────────────────────────────────────────────────────
  static const String appName = 'TeleCRM';
  static const int pageSize = 20;
  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 30);

  // ─── WHATSAPP TEMPLATES ────────────────────────────────────────────────────
  static const List<Map<String, String>> whatsappTemplates = [
    {
      'name': 'Introduction',
      'message':
          'Hello {name}, I am calling from our team regarding your inquiry. I would love to connect with you. Please let me know a convenient time to talk.',
    },
    {
      'name': 'Follow-up',
      'message':
          'Hi {name}, Just following up on our earlier conversation. I wanted to check if you had any questions or if you\'re ready to proceed. Looking forward to hearing from you!',
    },
    {
      'name': 'Callback Request',
      'message':
          'Dear {name}, I tried reaching you but couldn\'t connect. Could you please call back at your convenience or let me know a good time to reach you? Thank you.',
    },
    {
      'name': 'Product Info',
      'message':
          'Hi {name}, Thank you for showing interest in our product/service. I would like to share more details with you. Please feel free to reach out if you have any questions.',
    },
    {
      'name': 'Closing',
      'message':
          'Hello {name}, It was great speaking with you. As discussed, I\'ll send over the details shortly. Feel free to reach out anytime. Have a great day!',
    },
  ];
}
