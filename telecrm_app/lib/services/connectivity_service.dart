// lib/services/connectivity_service.dart
import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';

// ─────────────────────────────────────────────────────────
// PROVIDER
// ─────────────────────────────────────────────────────────
final connectivityProvider =
    StreamProvider<bool>((ref) => ConnectivityService().isOnlineStream);

final isOnlineProvider = Provider<bool>((ref) {
  final conn = ref.watch(connectivityProvider);
  return conn.when(data: (v) => v, loading: () => true, error: (_, __) => true);
});

// ─────────────────────────────────────────────────────────
// SERVICE
// ─────────────────────────────────────────────────────────
class ConnectivityService {
  final Connectivity _connectivity = Connectivity();

  Stream<bool> get isOnlineStream => _connectivity.onConnectivityChanged
      .map((results) => results.any((r) => r != ConnectivityResult.none));

  Future<bool> get isOnline async {
    final results = await _connectivity.checkConnectivity();
    return results.any((r) => r != ConnectivityResult.none);
  }
}

// ─────────────────────────────────────────────────────────
// OFFLINE BANNER WIDGET
// Wrap any screen's body with this to show an offline notice
// ─────────────────────────────────────────────────────────
class OfflineBanner extends ConsumerWidget {
  final Widget child;
  const OfflineBanner({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider);
    return Column(
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 350),
          height: isOnline ? 0 : 36,
          color: AppColors.error,
          child: isOnline
              ? const SizedBox.shrink()
              : const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.wifi_off_rounded, color: Colors.white, size: 16),
                    SizedBox(width: 8),
                    Text(
                      'No internet connection',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
        ),
        Expanded(child: child),
      ],
    );
  }
}
