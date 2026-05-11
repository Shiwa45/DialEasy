# TeleCRM Flutter App

A full-featured Telecaller CRM app with **auto-dialing using the device SIM card** (no cloud telephony), WhatsApp integration, and real-time call disposition tracking.

---

## Features

| Feature | Description |
|---|---|
| 🔐 Auth | Token-based login/logout using your Django backend |
| 📞 Auto-Dialer | Direct SIM-card calling (no native dialer popup) using `flutter_phone_direct_call` |
| 📋 Leads | Assigned leads with search, status filter (tabs), slideable actions |
| 💬 WhatsApp | Device WhatsApp or Cloud WhatsApp, with 5 pre-built templates |
| 📅 Follow-ups | Today / Overdue / Upcoming with snooze & complete actions |
| 🏠 Dashboard | Stats cards, pie chart, recent calls, upcoming follow-ups |
| 👤 Profile | Agent info, targets, performance stats, settings |
| 📱 Call Disposition | Bottom sheet after every call — 8 dispositions + follow-up scheduling |

---

## Project Structure

```
lib/
├── core/
│   ├── theme.dart          # Dark purple/gradient design system
│   ├── constants.dart      # API endpoints & WhatsApp templates
│   └── api_client.dart     # Dio client with token interceptor
├── models/
│   └── models.dart         # AppUser, Lead, CallLog, FollowUp, DashboardSummary
├── services/
│   ├── auth_service.dart   # Login, logout, profile + Riverpod providers
│   ├── lead_service.dart   # Leads, follow-ups, dashboard, dialer queue
│   ├── call_service.dart   # Direct calling + phone state listener
│   └── whatsapp_service.dart
├── screens/
│   ├── splash_screen.dart
│   ├── login_screen.dart
│   ├── home_screen.dart    # Bottom nav (Dashboard|AutoDial|Leads|FollowUps|Profile)
│   ├── dashboard_screen.dart
│   ├── dialer_screen.dart  # ⭐ Auto-dialer — the core feature
│   ├── leads_screen.dart
│   ├── lead_detail_screen.dart
│   ├── follow_ups_screen.dart
│   └── profile_screen.dart
└── widgets/
    ├── disposition_dialog.dart   # Post-call bottom sheet
    └── whatsapp_bottom_sheet.dart
```

---

## Setup

### 1. Configure API URL

Edit `lib/core/constants.dart`:

```dart
// For Android emulator (host machine localhost)
static const String baseUrl = 'http://10.0.2.2:8000/api';

// For real device on same WiFi
static const String baseUrl = 'http://192.168.X.X:8000/api';

// For production
static const String baseUrl = 'https://your-domain.com/api';
```

### 2. Backend CORS

In your Django `settings.py`:

```python
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE.insert(0, 'corsheaders.middleware.CorsMiddleware')
CORS_ALLOW_ALL_ORIGINS = True   # Or restrict to your IP
```

```
pip install django-cors-headers
```

### 3. Install Flutter dependencies

```bash
flutter pub get
```

### 4. Run on Android

```bash
flutter run
```

> **iOS** — Direct calling (`flutter_phone_direct_call`) only works on Android. On iOS the app will fall back to `url_launcher`.

---

## Auto-Dialer Flow

```
Load Queue (new + callback leads)
        ↓
Agent taps "Start Auto-Dial"
        ↓
App calls lead directly via SIM (no native dialer popup)
        ↓
Phone state listener detects: dialing → ringing → active → ended
        ↓
Disposition bottom sheet appears automatically
        ↓
Agent selects disposition, adds remarks, optionally schedules follow-up
        ↓
Call log saved to backend via POST /api/leads/{id}/call/
        ↓
Auto-advances to next lead
```

---

## WhatsApp Integration

1. **Device WhatsApp** — opens wa.me link in the installed WhatsApp app  
2. **Cloud WhatsApp** — calls WhatsApp Business API (update `whatsapp_service.dart` with your API key)

Templates are stored in `lib/core/constants.dart` as `AppConstants.whatsappTemplates`. Use `{name}` and `{company}` as placeholders.

---

## Required Android Permissions

- `CALL_PHONE` — make direct calls
- `READ_PHONE_STATE` — detect call state (active/ended)
- `PROCESS_OUTGOING_CALLS` — intercept call state
- `RECORD_AUDIO` — microphone (for future call recording)
- `INTERNET` — API calls

---

## Adding Assets

Create these directories and add placeholder files:

```bash
mkdir -p assets/images assets/animations assets/icons assets/fonts
```

Download Poppins fonts from Google Fonts and place in `assets/fonts/`.

---

## Connecting Cloud WhatsApp API

Replace the `sendViaCloudWhatsApp` method in `lib/services/whatsapp_service.dart`:

```dart
static Future<bool> sendViaCloudWhatsApp({...}) async {
  final response = await http.post(
    Uri.parse('https://graph.facebook.com/v18.0/YOUR_PHONE_NUMBER_ID/messages'),
    headers: {
      'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
      'Content-Type': 'application/json',
    },
    body: jsonEncode({
      'messaging_product': 'whatsapp',
      'to': phone,
      'type': 'text',
      'text': {'body': message},
    }),
  );
  return response.statusCode == 200;
}
```
