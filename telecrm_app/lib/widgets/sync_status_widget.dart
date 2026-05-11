// lib/widgets/sync_status_widget.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../services/connectivity_service.dart';
import '../services/offline_sync_service.dart';

// Provider to expose pending count reactively
final pendingCountProvider = FutureProvider.autoDispose<int>((ref) async {
  final svc = ref.read(offlineSyncProvider);
  return svc.getPendingCount();
});

class SyncStatusWidget extends ConsumerWidget {
  const SyncStatusWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider);
    final pendingAsync = ref.watch(pendingCountProvider);

    final pendingCount = pendingAsync.valueOrNull ?? 0;

    // Only show when offline OR when there are pending items to sync
    final showOfflineBadge = !isOnline;
    final showSyncBadge = isOnline && pendingCount > 0;

    if (!showOfflineBadge && !showSyncBadge) return const SizedBox.shrink();

    if (showOfflineBadge) {
      return Container(
        margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.warning.withOpacity(0.15),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.warning.withOpacity(0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded,
                color: AppColors.warning, size: 16),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                pendingCount > 0
                    ? 'Offline · $pendingCount action${pendingCount > 1 ? 's' : ''} queued'
                    : 'Offline mode — actions will sync when reconnected',
                style: const TextStyle(
                    color: AppColors.warning,
                    fontSize: 12,
                    fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ).animate().slideY(begin: -0.5, duration: 300.ms).fade();
    }

    // Online + pending: show sync button
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.success.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.success.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_upload_rounded,
              color: AppColors.success, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '$pendingCount offline action${pendingCount > 1 ? 's' : ''} ready to sync',
              style: const TextStyle(
                  color: AppColors.success,
                  fontSize: 12,
                  fontWeight: FontWeight.w600),
            ),
          ),
          GestureDetector(
            onTap: () => _syncNow(context, ref),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.success,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Sync Now',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w700),
              ),
            ),
          ),
        ],
      ),
    ).animate().slideY(begin: -0.5, duration: 300.ms).fade();
  }

  Future<void> _syncNow(BuildContext context, WidgetRef ref) async {
    final result = await ref.read(offlineSyncProvider).syncAll();
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(children: [
            Icon(
              result.failed == 0
                  ? Icons.check_circle_rounded
                  : Icons.warning_rounded,
              color: Colors.white,
              size: 16,
            ),
            const SizedBox(width: 8),
            Text(result.failed == 0
                ? 'Synced ${result.synced} actions successfully!'
                : 'Synced ${result.synced}, ${result.failed} failed'),
          ]),
          backgroundColor:
              result.failed == 0 ? AppColors.success : AppColors.warning,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      );
      // Refresh count
      ref.invalidate(pendingCountProvider);
    }
  }
}
