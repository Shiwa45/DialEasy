# Flutter / Mobile API Migration Guide
# ─────────────────────────────────────────────────────────────────────────────
# Migrating from:  demo.dialeasy.easyian.com/api/  (subdomain-per-tenant)
# Migrating to:    api.dialeasy.easyian.com/mobile/ (single centralised domain)
#
# This guide covers:
#   1. New base URL and API constants
#   2. Updated login flow (tenant_slug field)
#   3. JWT token storage and refresh
#   4. Sending tenant context on every request
#   5. Feature flag reading from JWT
#   6. Backward compatibility during rollout
# ─────────────────────────────────────────────────────────────────────────────

## Overview

The mobile app no longer needs a wildcard SSL cert or subdomain per tenant.
All API traffic goes to one fixed HTTPS endpoint: `api.dialeasy.easyian.com`

```
OLD:  https://demo.dialeasy.easyian.com/api/leads/
NEW:  https://api.dialeasy.easyian.com/mobile/api/leads/
```

The tenant is identified by the `tenant_slug` sent during login, which gets
embedded into the JWT. Every subsequent request carries the JWT — no extra
headers needed after login.

---

## 1. Constants / Config (lib/config/api_config.dart)

```dart
// lib/config/api_config.dart

class ApiConfig {
  // ── Centralised API (new — for mobile) ────────────────────────────────────
  static const String centralBaseUrl = 'https://api.dialeasy.easyian.com/mobile';

  // ── Legacy subdomain API (old — kept for backward compatibility) ──────────
  // Remove this after all users have updated to the new app version.
  static String legacyBaseUrl(String tenantSlug) =>
      'https://$tenantSlug.dialeasy.easyian.com/api';

  // ── Feature flag: which base URL to use ───────────────────────────────────
  // Set to true to use the new centralised API, false for old subdomain API.
  // Flip this once you've tested the new endpoint in staging.
  static const bool useCentralApi = true;

  static String get baseUrl => useCentralApi ? centralBaseUrl : '';
}
```

---

## 2. Auth Service (lib/services/auth_service.dart)

```dart
// lib/services/auth_service.dart

import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class AuthService {
  static const _storage = FlutterSecureStorage();

  // ── Storage keys ──────────────────────────────────────────────────────────
  static const _keyAccessToken  = 'jwt_access_token';
  static const _keyRefreshToken = 'jwt_refresh_token';
  static const _keyTenantSlug   = 'tenant_slug';
  static const _keyTenantName   = 'tenant_name';
  static const _keyFeatures     = 'tenant_features';

  // ── Login ─────────────────────────────────────────────────────────────────
  /// Authenticates against the centralised API.
  /// [tenantSlug] is the workspace/company code the user enters on the login screen.
  static Future<AuthResult> login({
    required String username,
    required String password,
    required String tenantSlug,
  }) async {
    final response = await http.post(
      Uri.parse('${ApiConfig.centralBaseUrl}/auth/login/'),
      headers: {
        'Content-Type': 'application/json',
        // Also send as header — belt-and-suspenders
        'X-Tenant-Slug': tenantSlug,
      },
      body: jsonEncode({
        'username':    username,
        'password':    password,
        'tenant_slug': tenantSlug,   // accepted aliases: workspace, company_code
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      await _storeTokens(data);
      return AuthResult.success(data);
    } else {
      final error = jsonDecode(response.body);
      throw AuthException(error['detail'] ?? error.toString());
    }
  }

  // ── Store tokens after login ──────────────────────────────────────────────
  static Future<void> _storeTokens(Map<String, dynamic> data) async {
    await Future.wait([
      _storage.write(key: _keyAccessToken,  value: data['access']),
      _storage.write(key: _keyRefreshToken, value: data['refresh']),
      _storage.write(key: _keyTenantSlug,   value: data['tenant']['schema_name']),
      _storage.write(key: _keyTenantName,   value: data['tenant']['name']),
      _storage.write(
        key: _keyFeatures,
        value: jsonEncode(data['tenant']['features'] ?? []),
      ),
    ]);
  }

  // ── Refresh access token ──────────────────────────────────────────────────
  static Future<String?> refreshAccessToken() async {
    final refreshToken = await _storage.read(key: _keyRefreshToken);
    if (refreshToken == null) return null;

    final response = await http.post(
      Uri.parse('${ApiConfig.centralBaseUrl}/auth/refresh/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': refreshToken}),
    );

    if (response.statusCode == 200) {
      final data    = jsonDecode(response.body);
      final newAccess = data['access'] as String;
      await _storage.write(key: _keyAccessToken, value: newAccess);
      return newAccess;
    }
    return null; // Refresh expired → force re-login
  }

  // ── Get current access token (auto-refresh if expired) ───────────────────
  static Future<String?> getAccessToken() async {
    final token = await _storage.read(key: _keyAccessToken);
    if (token == null) return null;

    // Check if token is expired by decoding the payload
    if (_isTokenExpired(token)) {
      return await refreshAccessToken();
    }
    return token;
  }

  // ── Logout ────────────────────────────────────────────────────────────────
  static Future<void> logout() async {
    final refreshToken = await _storage.read(key: _keyRefreshToken);
    final accessToken  = await _storage.read(key: _keyAccessToken);

    // Tell the server to blacklist the refresh token
    if (refreshToken != null && accessToken != null) {
      await http.post(
        Uri.parse('${ApiConfig.centralBaseUrl}/auth/logout/'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $accessToken',
        },
        body: jsonEncode({'refresh': refreshToken}),
      ).catchError((_) {}); // Best-effort — still clear local storage
    }

    await _storage.deleteAll();
  }

  // ── Feature check ─────────────────────────────────────────────────────────
  static Future<bool> hasFeature(String featureSlug) async {
    final raw = await _storage.read(key: _keyFeatures);
    if (raw == null) return false;
    final features = List<String>.from(jsonDecode(raw) as List);
    return features.contains(featureSlug);
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  static bool _isTokenExpired(String token) {
    try {
      final parts   = token.split('.');
      final payload = utf8.decode(base64Url.decode(base64Url.normalize(parts[1])));
      final data    = jsonDecode(payload) as Map<String, dynamic>;
      final exp     = data['exp'] as int;
      return DateTime.now().millisecondsSinceEpoch / 1000 >= exp;
    } catch (_) {
      return true; // Treat malformed token as expired
    }
  }
}

class AuthResult {
  final Map<String, dynamic> data;
  AuthResult.success(this.data);
}

class AuthException implements Exception {
  final String message;
  AuthException(this.message);
  @override String toString() => message;
}
```

---

## 3. HTTP Client (lib/services/api_client.dart)

```dart
// lib/services/api_client.dart
// Centralised HTTP client that auto-attaches the Bearer token.
// No need to send X-Tenant-Slug after login — the JWT carries it.

import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import 'auth_service.dart';

class ApiClient {
  // ── Authenticated GET ─────────────────────────────────────────────────────
  static Future<http.Response> get(String path) async {
    final headers = await _authHeaders();
    return http.get(
      Uri.parse('${ApiConfig.baseUrl}$path'),
      headers: headers,
    );
  }

  // ── Authenticated POST ────────────────────────────────────────────────────
  static Future<http.Response> post(String path, Map<String, dynamic> body) async {
    final headers = await _authHeaders();
    return http.post(
      Uri.parse('${ApiConfig.baseUrl}$path'),
      headers: headers,
      body: jsonEncode(body),
    );
  }

  // ── Authenticated PATCH ───────────────────────────────────────────────────
  static Future<http.Response> patch(String path, Map<String, dynamic> body) async {
    final headers = await _authHeaders();
    return http.patch(
      Uri.parse('${ApiConfig.baseUrl}$path'),
      headers: headers,
      body: jsonEncode(body),
    );
  }

  // ── Auth headers ──────────────────────────────────────────────────────────
  static Future<Map<String, String>> _authHeaders() async {
    final token = await AuthService.getAccessToken();
    return {
      'Content-Type':  'application/json',
      'Authorization': 'Bearer $token',
      // tenant_slug is embedded in the JWT — no extra header needed
    };
  }
}
```

---

## 4. Login Screen Changes (lib/screens/login_screen.dart)

Add a **Workspace / Company Code** field:

```dart
// Add this TextFormField before the username field:
TextFormField(
  controller: _tenantSlugController,
  decoration: InputDecoration(
    labelText: 'Workspace Code',
    hintText: 'e.g.  demo',
    prefixIcon: Icon(Icons.business),
  ),
  validator: (v) => (v == null || v.isEmpty) ? 'Workspace code is required' : null,
),

// On login button press:
await AuthService.login(
  username:    _usernameController.text.trim(),
  password:    _passwordController.text,
  tenantSlug:  _tenantSlugController.text.trim().toLowerCase(),
);
```

**UX tip**: Pre-fill the workspace field from a deep link or QR code to improve
onboarding. Example deep link: `dialeasy://login?workspace=demo`

---

## 5. Example API Calls (no changes needed)

After the `ApiClient` is set up, all existing API call code stays the same —
just change the path prefix from `/api/` to `/api/`:

```dart
// OLD (subdomain-based, still works during transition)
// final resp = await http.get('https://demo.dialeasy.easyian.com/api/leads/');

// NEW (centralised — no subdomain, no wildcard SSL)
final resp = await ApiClient.get('/api/leads/');
final resp = await ApiClient.get('/api/agent/dashboard/');
final resp = await ApiClient.post('/api/leads/1/call/', { ... });
```

---

## 6. Tenant Info on Splash Screen

Before showing the login form, fetch tenant branding:

```dart
Future<Map<String, dynamic>> fetchTenantInfo(String tenantSlug) async {
  final resp = await http.get(
    Uri.parse('${ApiConfig.centralBaseUrl}/tenant/info/?tenant=$tenantSlug'),
  );
  return jsonDecode(resp.body);
}
// Returns: { name, logo, current_plan, features, is_active }
```

---

## 7. Migration Checklist

- [ ] Add `flutter_secure_storage` to `pubspec.yaml`
- [ ] Create `lib/config/api_config.dart`
- [ ] Create `lib/services/auth_service.dart`
- [ ] Create `lib/services/api_client.dart`
- [ ] Add **Workspace Code** field to login screen
- [ ] Replace direct `http.get/post` calls with `ApiClient.get/post`
- [ ] Test login → JWT received → leads load correctly
- [ ] Test token expiry → auto-refresh → seamless UX
- [ ] Test logout → server blacklists refresh token
- [ ] Set `useCentralApi = true` and ship new app version
- [ ] After all users update: remove legacy subdomain URL code

---

## 8. Backward Compatibility

During the transition period, both routes work simultaneously:

| Client          | Endpoint                                    | Auth         | Status      |
|-----------------|---------------------------------------------|--------------|-------------|
| Old Flutter app | `demo.dialeasy.easyian.com/api/`            | Token auth   | ✅ Works     |
| New Flutter app | `api.dialeasy.easyian.com/mobile/api/`      | JWT          | ✅ Works     |
| Web browser     | `demo.dialeasy.easyian.com/leads/`          | Session auth | ✅ Unchanged |
| Super admin     | `admin.dialeasy.easyian.com/admin/`         | Session auth | ✅ Unchanged |
