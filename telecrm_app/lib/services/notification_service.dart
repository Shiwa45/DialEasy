// lib/services/notification_service.dart
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static const _channelId = 'telecrm_followup';
  static const _channelName = 'Follow-up Reminders';
  static const _channelDesc = 'Reminders for scheduled follow-ups';

  Future<void> init() async {
    tz.initializeTimeZones();

    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    const initSettings = InitializationSettings(
      android: androidInit,
      iOS: iosInit,
    );

    await _plugin.initialize(initSettings,
        onDidReceiveNotificationResponse: _onNotificationTap);

    // Create Android notification channel
    const channel = AndroidNotificationChannel(
      _channelId,
      _channelName,
      description: _channelDesc,
      importance: Importance.high,
      playSound: true,
    );
    await _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);
  }

  void _onNotificationTap(NotificationResponse response) {
    // Navigation can be handled here via a global navigator key
    // For now, just log
  }

  /// Show an immediate notification (e.g. "Follow-up reminder!")
  Future<void> showNow({
    required int id,
    required String title,
    required String body,
  }) async {
    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription: _channelDesc,
        importance: Importance.high,
        priority: Priority.high,
        icon: '@mipmap/ic_launcher',
      ),
      iOS: DarwinNotificationDetails(),
    );
    await _plugin.show(id, title, body, details);
  }

  /// Schedule a notification at a specific date/time
  Future<void> schedule({
    required int id,
    required String title,
    required String body,
    required DateTime scheduledDate,
  }) async {
    final tzDate = tz.TZDateTime.from(scheduledDate, tz.local);
    if (tzDate.isBefore(tz.TZDateTime.now(tz.local))) return;

    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription: _channelDesc,
        importance: Importance.high,
        priority: Priority.high,
      ),
      iOS: DarwinNotificationDetails(),
    );

    await _plugin.zonedSchedule(
      id,
      title,
      body,
      tzDate,
      details,
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
    );
  }

  /// Cancel a specific notification
  Future<void> cancel(int id) => _plugin.cancel(id);

  /// Cancel all notifications
  Future<void> cancelAll() => _plugin.cancelAll();

  /// Schedule a follow-up reminder 15 minutes before the follow-up time
  Future<void> scheduleFollowUpReminder({
    required int followUpId,
    required String leadName,
    required DateTime followUpDateTime,
  }) async {
    final reminderTime =
        followUpDateTime.subtract(const Duration(minutes: 15));
    await schedule(
      id: followUpId,
      title: '🔔 Follow-up Reminder',
      body: 'You have a follow-up with $leadName in 15 minutes',
      scheduledDate: reminderTime,
    );
  }
}
