# TeleCRM — Architecture & Developer Guide

## Table of Contents
1. [Tech Stack](#tech-stack)
2. [Project Layout](#project-layout)
3. [State Management](#state-management)
4. [Auto-Dialer System](#auto-dialer-system)
5. [Offline Mode](#offline-mode)
6. [Notifications](#notifications)
7. [WhatsApp Integration](#whatsapp-integration)
8. [API Reference](#api-reference)
9. [Adding New Features](#adding-new-features)
10. [Troubleshooting](#troubleshooting)

---

## Tech Stack

| Concern | Package | Version |
|---|---|---|
| UI Framework | Flutter | ≥ 3.0 |
| State | flutter_riverpod | ^2.4.9 |
| HTTP | dio | ^5.4.0 |
| Direct calling | flutter_phone_direct_call | ^1.0.3 |
| Call state detection | phone_state | ^1.0.0 |
| Permissions | permission_handler | ^11.3.0 |
| Local notifications | flutter_local_notifications | ^17.2.1 |
| Offline storage | shared_preferences | ^2.2.2 |
| Animations | flutter_animate | ^4.5.0 |
| Charts | fl_chart | ^0.67.0 |
| WhatsApp / links | url_launcher | ^6.2.4 |
| Connectivity | connectivity_plus | ^6.0.3 |
| Typography | google_fonts | ^6.2.1 |

---

## Project Layout

```
lib/
├── core/                         # App-wide infrastructure
│   ├── theme.dart                # Colors, gradients, dark theme
│   ├── constants.dart            # API endpoints, WhatsApp templates
│   ├── api_client.dart           # Dio + Token auth interceptor
│   ├── app_router.dart           # Named routes
│   ├── app_config_provider.dart  # Live config from /utils/app-config/
│   └── app_extensions.dart       # String/Duration/DateTime extensions
│
├── models/
│   └── models.dart               # All data models (Lead, CallLog, etc.)
│
├── services/                     # Business logic + API calls
│   ├── auth_service.dart         # Login, logout, profile, token storage
│   ├── lead_service.dart         # Leads CRUD, call logs, follow-ups
│   ├── call_service.dart         # SIM calling + call state stream
│   ├── whatsapp_service.dart     # Device/Cloud WhatsApp sender
│   ├── notification_service.dart # Local follow-up reminders
│   ├── connectivity_service.dart # Online/offline detection
│   └── offline_sync_service.dart # Queue actions, bulk upload
│
├── screens/                      # 11 full screens
│   ├── splash_screen.dart
│   ├── login_screen.dart
│   ├── home_screen.dart          # Bottom nav shell + CallOverlay
│   ├── dashboard_screen.dart     # Stats, charts, targets
│   ├── dialer_screen.dart        # Auto-dialer with queue
│   ├── leads_screen.dart         # Lead list, filter, search
│   ├── lead_detail_screen.dart   # Full lead info + notes + history
│   ├── follow_ups_screen.dart    # Today / Overdue / Upcoming
│   ├── profile_screen.dart       # Agent stats + quick nav
│   ├── performance_screen.dart   # Charts: daily, dispositions
│   └── call_history_screen.dart  # All past calls + search
│
└── widgets/                      # 10 reusable widgets
    ├── agent_target_card.dart    # Circular progress ring + bar
    ├── call_overlay_widget.dart  # Floating call status pill
    ├── common_widgets.dart       # GradientButton, GlassCard, etc.
    ├── disposition_dialog.dart   # Post-call disposition bottom sheet
    ├── lead_search_delegate.dart # Search overlay with live results
    ├── lead_status_sheet.dart    # Quick status change grid
    ├── notes_sheet.dart          # Edit lead notes
    ├── sync_status_widget.dart   # Offline banner + sync button
    ├── whatsapp_bottom_sheet.dart# WhatsApp channel + template picker
    └── ...
```

---

## State Management

The app uses **Riverpod 2** throughout.

### Key Providers

```dart
// Auth
authProvider              → StateNotifierProvider<AuthNotifier, AuthState>

// Leads
leadsProvider             → StateNotifierProvider<LeadsNotifier, LeadsState>
dialerQueueProvider       → StateNotifierProvider<DialerQueueNotifier, DialerQueueState>

// Follow-ups
followUpsProvider         → StateNotifierProvider<FollowUpsNotifier, FollowUpsState>

// Dashboard
dashboardProvider         → FutureProvider.autoDispose<DashboardSummary>

// Call state
callStateProvider         → StateNotifierProvider<CallStateNotifier, CallStateModel>

// App config (choices, targets)
appConfigProvider         → StateNotifierProvider<AppConfigNotifier, AppConfig>

// Connectivity
isOnlineProvider          → Provider<bool>

// Offline sync
offlineSyncProvider       → Provider<OfflineSyncService>
```

### Data flow

```
User action
    │
    ▼
Screen (ConsumerWidget)
    │  ref.read(provider.notifier).method()
    ▼
StateNotifier / Service
    │  await dio.get/post(...)
    ▼
API (Django backend)
    │  JSON response
    ▼
Model.fromJson()
    │
    ▼
state = newState
    │  ref.watch triggers rebuild
    ▼
Widget rebuilds
```

---

## Auto-Dialer System

The dialer works in 3 phases:

### Phase 1 — Queue Loading
```dart
// DialerQueueNotifier.loadQueue()
// Fetches status=new + status=callback leads in parallel
// Stores in state.queue as List<Lead>
```

### Phase 2 — Direct SIM Call
```dart
// CallService.makeDirectCall(phone)
// Uses flutter_phone_direct_call (no native dialer popup)
// Requires CALL_PHONE permission
await FlutterPhoneDirectCall.callNumber(cleanedPhone);
```

### Phase 3 — Call State Detection
```dart
// CallService listens to PhoneState.stream
// PhoneStateStatus.CALL_STARTED  → CallStatus.active
// PhoneStateStatus.CALL_ENDED    → CallStatus.ended
// Timer ticks every second to track duration
```

### Phase 4 — Disposition
```dart
// When CallStatus.ended is detected:
// DispositionDialog pops automatically
// Agent picks disposition + optional remarks + optional follow-up
// Result saved via POST /api/leads/{id}/call/
// If offline: queued to SharedPreferences via OfflineSyncService
// Auto-advance to next lead after 2s delay
```

### Queue visual
```
[Prev] [████████░░░░] 6/10  ← progress bar
         ┌─────────────────────────────────┐
         │  ● John Doe                     │
         │    +91 98765 43210              │
         │    [Callback] · 2 prev calls    │
         └─────────────────────────────────┘
         [Skip]      [▶ Auto-Dial / Call Now]
```

---

## Offline Mode

When the device has no internet:

1. `isOnlineProvider` (from `ConnectivityService`) returns `false`
2. `SyncStatusWidget` shows an amber offline banner in the dialer
3. After a call is disposed, `OfflineSyncService.queueCallLog()` stores the action in `SharedPreferences` as JSON
4. When the device comes back online, the banner changes to "X actions ready to sync" with a **Sync Now** button
5. Tapping it calls `POST /api/sync/upload/` with all batched call logs + follow-ups

```dart
// Offline queue storage key: 'offline_pending_actions'
// Format: List<PendingAction> serialised to JSON
// Max batch: whatever is in the queue (no hard limit)
```

---

## Notifications

Follow-up reminders fire **15 minutes before** the scheduled follow-up time.

```dart
// Triggered automatically inside LeadService.createFollowUp()
await NotificationService().scheduleFollowUpReminder(
  followUpId: followUp.id,
  leadName: lead.name,
  followUpDateTime: DateTime(...),
);

// Android channel: 'telecrm_followup' (high importance)
// Uses AndroidScheduleMode.exactAllowWhileIdle
```

Permissions required:
- `POST_NOTIFICATIONS` (Android 13+)
- `SCHEDULE_EXACT_ALARM` — optional, add to manifest if exact timing needed

---

## WhatsApp Integration

Two modes are available on every lead:

### Device WhatsApp
Opens the WhatsApp app installed on the phone with a pre-filled message.
```dart
final url = 'https://wa.me/$phone?text=${Uri.encodeComponent(message)}';
await launchUrl(uri, mode: LaunchMode.externalApplication);
```

### Cloud WhatsApp
Calls `WhatsAppService.sendViaCloudWhatsApp()`. Currently opens the WhatsApp Business web link. To connect to the real **WhatsApp Business Cloud API**, replace the method body with an HTTP call to your backend:

```dart
// lib/services/whatsapp_service.dart
static Future<bool> sendViaCloudWhatsApp({...}) async {
  final resp = await Dio().post(
    '${AppConstants.baseUrl}/whatsapp/send/',
    data: {'phone': phone, 'message': message, 'template': templateName},
    options: Options(headers: {'Authorization': 'Token $yourToken'}),
  );
  return resp.statusCode == 200;
}
```

### Templates
5 built-in templates in `AppConstants.whatsappTemplates`. Each has `{name}` and `{company}` placeholders substituted automatically:

```dart
WhatsAppService.applyTemplate(template, name: lead.name, company: lead.company);
```

---

## API Reference

All endpoints from the Django backend. Auth header: `Authorization: Token <token>`.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login/` | Login, returns token |
| POST | `/auth/logout/` | Logout, deletes token |
| GET | `/auth/profile/` | Agent profile |
| GET | `/leads/my_leads/` | Paginated assigned leads |
| GET | `/search/leads/?q=` | Live search |
| PATCH | `/leads/{id}/` | Update status/notes |
| POST | `/leads/{id}/call/` | Create call log |
| POST | `/leads/{id}/follow-up/` | Schedule follow-up |
| GET | `/call-logs/` | All call logs |
| GET | `/follow-ups/today/` | Today's follow-ups |
| GET | `/follow-ups/overdue/` | Overdue follow-ups |
| GET | `/follow-ups/upcoming/` | Upcoming follow-ups |
| POST | `/follow-ups/{id}/complete/` | Mark complete |
| GET | `/agent/dashboard/` | Dashboard summary |
| GET | `/performance/summary/` | Performance metrics |
| GET | `/utils/app-config/` | Live config + choices |
| POST | `/sync/upload/` | Bulk offline sync |

---

## Adding New Features

### Add a new screen
1. Create `lib/screens/my_screen.dart`
2. Add a route to `lib/core/app_router.dart`:
   ```dart
   case '/my-route':
     return _slide(const MyScreen());
   ```
3. Navigate with: `Navigator.pushNamed(context, '/my-route')`

### Add a new API call
1. Add the endpoint constant to `lib/core/constants.dart`
2. Add a method to the relevant service in `lib/services/`
3. Create/update a Riverpod provider
4. Use `ref.watch(myProvider)` in the widget

### Add a WhatsApp template
Edit `AppConstants.whatsappTemplates` in `lib/core/constants.dart`:
```dart
{
  'name': 'My Template',
  'message': 'Hi {name}, ...',
},
```

### Change the primary colour
Edit `AppColors.primary` in `lib/core/theme.dart`:
```dart
static const Color primary = Color(0xFF6C3CE1); // ← change this
```

---

## Troubleshooting

### App can't connect to backend
- Check `baseUrl` in `lib/core/constants.dart`
- Android emulator: use `http://10.0.2.2:8000/api`
- Real device: use your machine's LAN IP, ensure firewall allows port 8000
- Check `android:usesCleartextTraffic="true"` in `AndroidManifest.xml` (already set)

### Direct call doesn't work
- Ensure `CALL_PHONE` permission is granted at runtime
- On Android 10+, first call triggers the permission dialog
- Check that `flutter_phone_direct_call` is on version `^1.0.3`

### Notifications not firing
- Check `POST_NOTIFICATIONS` permission (Android 13+)
- Verify the follow-up datetime is in the future
- The reminder fires 15 min before — test with a near-future time

### Offline sync not uploading
- Sync only triggers when `isOnlineProvider` returns `true`
- The `SyncStatusWidget` in the dialer shows the queue count
- Check `POST /api/sync/upload/` is accessible and auth token is valid

### Build fails: "assets not found"
Run from project root:
```bash
mkdir -p assets/images assets/animations assets/icons
```
Or just remove the asset entries from `pubspec.yaml` flutter section entirely.
