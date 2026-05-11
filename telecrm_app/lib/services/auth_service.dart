// lib/services/auth_service.dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

import '../core/api_client.dart';
import '../core/constants.dart';
import '../models/models.dart';

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref.read(apiClientProvider));
});

// Auth state
class AuthState {
  final AppUser? user;
  final AgentProfile? profile;
  final String? token;
  final bool isLoading;
  final String? error;

  const AuthState({
    this.user,
    this.profile,
    this.token,
    this.isLoading = false,
    this.error,
  });

  bool get isAuthenticated => token != null && token!.isNotEmpty;

  AuthState copyWith({
    AppUser? user,
    AgentProfile? profile,
    String? token,
    bool? isLoading,
    String? error,
    bool clearError = false,
    bool clearUser = false,
  }) =>
      AuthState(
        user: clearUser ? null : (user ?? this.user),
        profile: clearUser ? null : (profile ?? this.profile),
        token: clearUser ? null : (token ?? this.token),
        isLoading: isLoading ?? this.isLoading,
        error: clearError ? null : (error ?? this.error),
      );
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthService _authService;

  AuthNotifier(this._authService) : super(const AuthState()) {
    _loadFromStorage();
  }

  Future<void> _loadFromStorage() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(AppConstants.tokenKey);
    final userJson = prefs.getString(AppConstants.userKey);
    final profileJson = prefs.getString(AppConstants.agentProfileKey);

    if (token != null && userJson != null) {
      final user = AppUser.fromJson(jsonDecode(userJson));
      final profile = profileJson != null
          ? AgentProfile.fromJson(jsonDecode(profileJson))
          : null;
      state = state.copyWith(token: token, user: user, profile: profile);
    }
  }

  Future<bool> login(String username, String password) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _authService.login(username, password);
      final prefs = await SharedPreferences.getInstance();
      final user = result['user'] as AppUser;
      await prefs.setString(AppConstants.tokenKey, result['token']);
      await prefs.setString(AppConstants.userKey, jsonEncode(user.toJsonMap()));
      if (result['profile'] != null) {
        await prefs.setString(AppConstants.agentProfileKey, jsonEncode(result['profileRaw']));
      }
      state = state.copyWith(
        isLoading: false,
        token: result['token'],
        user: user,
        profile: result['profile'],
      );
      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: apiErrorMessage(e));
      return false;
    }
  }

  Future<void> logout() async {
    try {
      await _authService.logout();
    } catch (_) {}
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConstants.tokenKey);
    await prefs.remove(AppConstants.userKey);
    await prefs.remove(AppConstants.agentProfileKey);
    state = const AuthState();
  }

  Future<void> refreshProfile() async {
    try {
      final result = await _authService.getProfile();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConstants.agentProfileKey, jsonEncode(result['profileRaw']));
      state = state.copyWith(
        user: result['user'],
        profile: result['profile'],
      );
    } catch (_) {}
  }

  void clearError() => state = state.copyWith(clearError: true);
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.read(authServiceProvider));
});

// ─────────────────────────────────────────────────────────
// AUTH SERVICE
// ─────────────────────────────────────────────────────────
class AuthService {
  final ApiClient _client;
  AuthService(this._client);

  Future<Map<String, dynamic>> login(String username, String password) async {
    final response = await _client.dio.post(
      AppConstants.loginEndpoint,
      data: {'username': username, 'password': password},
    );
    final data = response.data;
    return {
      'token': data['token'],
      'user': AppUser.fromJson(data['user']),
      'profile': data['agent_profile'] != null
          ? AgentProfile.fromJson(data['agent_profile'])
          : null,
      'profileRaw': data['agent_profile'],
    };
  }

  Future<void> logout() async {
    await _client.dio.post(AppConstants.logoutEndpoint);
  }

  Future<Map<String, dynamic>> getProfile() async {
    final response = await _client.dio.get(AppConstants.profileEndpoint);
    final data = response.data;
    return {
      'user': AppUser.fromJson(data['user']),
      'profile': data['agent_profile'] != null
          ? AgentProfile.fromJson(data['agent_profile'])
          : null,
      'profileRaw': data['agent_profile'],
    };
  }
}

extension AppUserJson on AppUser {
  Map<String, dynamic> toJsonMap() => {
        'id': id,
        'username': username,
        'first_name': firstName,
        'last_name': lastName,
        'email': email,
        'full_name': fullName,
        'date_joined': dateJoined,
      };
}
