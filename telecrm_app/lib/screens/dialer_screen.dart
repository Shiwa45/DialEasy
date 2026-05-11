// lib/screens/dialer_screen.dart
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/activity_tracking_service.dart';
import '../services/call_recording_service.dart';
import '../services/call_service.dart';
import '../services/connectivity_service.dart';
import '../services/lead_service.dart';
import '../services/offline_sync_service.dart';
import '../widgets/disposition_dialog.dart';
import '../widgets/recording_indicator.dart';
import '../widgets/sync_status_widget.dart';

class DialerScreen extends ConsumerStatefulWidget {
  const DialerScreen({super.key});

  @override
  ConsumerState<DialerScreen> createState() => _DialerScreenState();
}

class _DialerScreenState extends ConsumerState<DialerScreen>
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  bool _showedDisposition = false;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    // Load dialer queue
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(dialerQueueProvider.notifier).loadQueue();
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _startCall(Lead lead) async {
    _showedDisposition = false;

    final activitySvc = ref.read(activityTrackingServiceProvider);

    // Start a new tracking session on the very first call of this dialer session
    if (!ref.read(dialerQueueProvider).isActive) {
      final sessionId = await activitySvc.startSession();
      if (sessionId != null) {
        ref.read(activeSessionIdProvider.notifier).state = sessionId;
      }
    }

    ref.read(dialerQueueProvider.notifier).startDialing();
    ref.read(dialerQueueProvider.notifier).setDialing(true);
    // Store leadId on call state for activity tracking
    ref.read(callStateProvider.notifier).setLeadId(lead.id);
    final callNotifier = ref.read(callStateProvider.notifier);
    final success = await callNotifier.call(lead.phone);
    if (!success && mounted) {
      _showSnackbar('Could not make call. Check permissions.', isError: true);
      ref.read(dialerQueueProvider.notifier).setDialing(false);
      ref.read(dialerQueueProvider.notifier).stopDialing();
    }
  }

  void _listenCallState(CallStateModel callState, DialerQueueState queue) {
    if (callState.status == CallStatus.ended && !_showedDisposition) {
      _showedDisposition = true;
      final lead = queue.currentLead;
      if (lead != null && mounted) {
        Future.delayed(const Duration(milliseconds: 500), () {
          if (mounted) _showDispositionDialog(lead, callState.duration);
        });
      }
    }
  }

  Future<void> _showDispositionDialog(Lead lead, Duration? duration) async {
    // Activity: disposition started (dialog opened)
    unawaited(ref.read(activityTrackingServiceProvider).logEvent(
      ActivityEvent.dispositionStarted,
      leadId: lead.id,
    ));

    final result = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DispositionDialog(lead: lead, callDuration: duration),
    );

    if (result != null && mounted) {
      if (result['stopCalling'] == true) {
        // Activity: session ended by agent
        unawaited(ref.read(activityTrackingServiceProvider).endSession());
        ref.read(callStateProvider.notifier).reset();
        ref.read(dialerQueueProvider.notifier).stopDialing();
        return;
      }

      // Activity: disposition submitted
      unawaited(ref.read(activityTrackingServiceProvider).logEvent(
        ActivityEvent.dispositionSubmitted,
        leadId: lead.id,
      ));

      final isOnline = ref.read(isOnlineProvider);
      try {
        if (isOnline) {
          // Online: save directly to API
          final callLog = await ref.read(leadServiceProvider).createCallLog(
            lead.id,
            disposition: result['disposition'],
            remarks: result['remarks'],
            duration: duration,
            leadStatus: result['leadStatus'],
          );
          // Link call log ID so recording can be uploaded
          if (callLog != null) {
            ref.read(callStateProvider.notifier).setCallLogId(callLog.id);
          }
          // Schedule follow-up if requested
          if (result['scheduleFollowUp'] == true) {
            await ref.read(leadServiceProvider).createFollowUp(
              lead.id,
              followUpDate: result['followUpDate'],
              followUpTime: result['followUpTime'],
              remarks: result['remarks'],
            );
          }
        } else {
          // Offline: queue for later sync
          await ref.read(offlineSyncProvider).queueCallLog(
            leadId: lead.id,
            disposition: result['disposition'],
            remarks: result['remarks'],
            duration: duration,
            leadStatus: result['leadStatus'],
          );
          if (result['scheduleFollowUp'] == true) {
            await ref.read(offlineSyncProvider).queueFollowUp(
              leadId: lead.id,
              followUpDate: result['followUpDate'],
              followUpTime: result['followUpTime'],
              remarks: result['remarks'],
            );
          }
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Row(children: [
                  Icon(Icons.cloud_off_rounded, color: Colors.white, size: 16),
                  SizedBox(width: 8),
                  Text('Saved offline — will sync when back online'),
                ]),
                backgroundColor: AppColors.warning,
                behavior: SnackBarBehavior.floating,
              ),
            );
          }
        }
      } catch (e) {
        // Fallback to offline queue on API error
        await ref.read(offlineSyncProvider).queueCallLog(
          leadId: lead.id,
          disposition: result['disposition'],
          remarks: result['remarks'],
          duration: duration,
        );
      }

      ref.read(callStateProvider.notifier).reset();
      ref.read(dialerQueueProvider.notifier).nextLead();

      // Auto-dial next if session is still active
      final queue = ref.read(dialerQueueProvider);
      if (queue.isActive && queue.currentLead != null) {
        await Future.delayed(const Duration(seconds: 2));
        if (mounted) _startCall(queue.currentLead!);
      }
    }
  }

  void _showSnackbar(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? AppColors.error : AppColors.success,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final queue = ref.watch(dialerQueueProvider);
    final callState = ref.watch(callStateProvider);

    // Side effect: listen for call state changes
    ref.listen(callStateProvider, (prev, next) {
      _listenCallState(next, ref.read(dialerQueueProvider));
    });

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(
            children: [
              _buildTopBar(queue),
              const SyncStatusWidget(),
              Expanded(
                child: queue.isLoading
                    ? const Center(child: CircularProgressIndicator(color: AppColors.primaryLight))
                    : queue.queue.isEmpty
                        ? _buildEmptyState()
                        : _buildDialerContent(queue, callState),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar(DialerQueueState queue) {
    final callState = ref.watch(callStateProvider);
    final isRecording = ref.watch(isRecordingProvider);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Auto Dialer',
                    style: TextStyle(
                        fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                Text('${queue.remaining} leads remaining',
                    style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
              ],
            ),
          ),
          // REC badge shown during active recording
          if (isRecording && callState.status == CallStatus.active) ...[
            const RecordingIndicator(),
            const SizedBox(width: 10),
          ],
          if (!queue.isLoading && queue.queue.isNotEmpty)
            IconButton(
              onPressed: () => ref.read(dialerQueueProvider.notifier).loadQueue(),
              icon: const Icon(Icons.refresh_rounded, color: AppColors.textSecondary),
            ),
        ],
      ),
    );
  }

  Widget _buildDialerContent(DialerQueueState queue, CallStateModel callState) {
    final lead = queue.currentLead;
    if (lead == null) return _buildCompletedState();

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          const SizedBox(height: 16),
          // Progress bar
          _buildProgressBar(queue),
          const SizedBox(height: 28),
          // Current lead card
          _buildLeadCard(lead, queue, callState),
          const SizedBox(height: 24),
          // Call status
          _buildCallStatus(callState),
          const SizedBox(height: 24),
          // Action buttons
          _buildActionButtons(queue, callState, lead),
          const SizedBox(height: 24),
          // Queue preview
          _buildQueuePreview(queue),
          const SizedBox(height: 80),
        ],
      ),
    );
  }

  Widget _buildProgressBar(DialerQueueState queue) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Progress', style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
            Text('${queue.currentIndex} / ${queue.queue.length}',
                style: TextStyle(
                    fontSize: 13,
                    color: AppColors.primaryLight,
                    fontWeight: FontWeight.w600)),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(
            value: queue.progress,
            backgroundColor: AppColors.divider,
            valueColor: const AlwaysStoppedAnimation<Color>(AppColors.primaryLight),
            minHeight: 6,
          ),
        ),
      ],
    );
  }

  Widget _buildLeadCard(Lead lead, DialerQueueState queue, CallStateModel callState) {
    final isActive = callState.status == CallStatus.active;
    final isDialing = callState.status == CallStatus.dialing ||
        callState.status == CallStatus.ringing;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: isActive
            ? AppColors.successGradient
            : isDialing
                ? AppColors.primaryGradient
                : AppColors.cardGradient,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: isActive
              ? AppColors.success.withOpacity(0.5)
              : isDialing
                  ? AppColors.primaryLight.withOpacity(0.5)
                  : AppColors.divider,
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: isActive
                ? AppColors.success.withOpacity(0.25)
                : isDialing
                    ? AppColors.primary.withOpacity(0.3)
                    : Colors.black.withOpacity(0.3),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        children: [
          // Avatar with pulse animation
          Stack(
            alignment: Alignment.center,
            children: [
              if (isDialing || isActive)
                AnimatedBuilder(
                  animation: _pulseController,
                  builder: (_, __) => Container(
                    width: 90 + _pulseController.value * 20,
                    height: 90 + _pulseController.value * 20,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.white.withOpacity(0.05 + _pulseController.value * 0.05),
                    ),
                  ),
                ),
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Text(
                  lead.name.isNotEmpty ? lead.name[0].toUpperCase() : '?',
                  style: const TextStyle(
                      fontSize: 32, fontWeight: FontWeight.w800, color: Colors.white),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            lead.name,
            style: const TextStyle(
                fontSize: 22, fontWeight: FontWeight.w700, color: Colors.white),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.phone_rounded, color: Colors.white70, size: 16),
              const SizedBox(width: 6),
              Text(
                lead.phone,
                style: const TextStyle(fontSize: 16, color: Colors.white70),
              ),
            ],
          ),
          if (lead.company != null && lead.company!.isNotEmpty) ...[
            const SizedBox(height: 4),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.business_rounded, color: Colors.white54, size: 14),
                const SizedBox(width: 6),
                Text(
                  lead.company!,
                  style: const TextStyle(fontSize: 13, color: Colors.white54),
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          // Status chip
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: AppColors.statusColor(lead.status),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  lead.statusDisplay,
                  style: const TextStyle(
                      color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                ),
                if (lead.callCount > 0) ...[
                  const SizedBox(width: 8),
                  Text('· ${lead.callCount} prev calls',
                      style: const TextStyle(color: Colors.white60, fontSize: 11)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCallStatus(CallStateModel callState) {
    if (callState.status == CallStatus.idle) return const SizedBox.shrink();

    String label;
    Color color;
    IconData icon;

    switch (callState.status) {
      case CallStatus.dialing:
        label = 'Dialing...';
        color = AppColors.primary;
        icon = Icons.phone_forwarded_rounded;
        break;
      case CallStatus.ringing:
        label = 'Ringing...';
        color = AppColors.secondary;
        icon = Icons.ring_volume_rounded;
        break;
      case CallStatus.active:
        final d = callState.duration ?? Duration.zero;
        label =
            'In call · ${d.inMinutes.toString().padLeft(2, '0')}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';
        color = AppColors.success;
        icon = Icons.phone_in_talk_rounded;
        break;
      case CallStatus.ended:
        label = 'Call ended';
        color = AppColors.warning;
        icon = Icons.phone_callback_rounded;
        break;
      case CallStatus.failed:
        label = 'Call failed';
        color = AppColors.error;
        icon = Icons.phone_disabled_rounded;
        break;
      case CallStatus.permissionDenied:
        label = 'Permission denied';
        color = AppColors.error;
        icon = Icons.no_sim_rounded;
        break;
      default:
        return const SizedBox.shrink();
    }

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Text(label,
              style: TextStyle(color: color, fontSize: 15, fontWeight: FontWeight.w600)),
        ],
      ),
    ).animate(key: ValueKey(callState.status)).fade(duration: 300.ms);
  }

  Widget _buildActionButtons(DialerQueueState queue, CallStateModel callState, Lead lead) {
    final isIdle = callState.status == CallStatus.idle ||
        callState.status == CallStatus.failed ||
        callState.status == CallStatus.permissionDenied;
    final isInCall = callState.status == CallStatus.active ||
        callState.status == CallStatus.ringing ||
        callState.status == CallStatus.dialing;

    if (isInCall) {
      return Column(
        children: [
          const Text(
            'Call is in progress',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => _showDispositionDialog(lead, callState.duration),
              icon: const Icon(Icons.edit_note_rounded, color: AppColors.warning),
              label: const Text('Dispose Early', style: TextStyle(color: AppColors.warning)),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: AppColors.warning),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
        ],
      );
    }

    if (callState.status == CallStatus.ended) {
      return Column(
        children: [
          const Text('Call ended — add disposition',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 14)),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => _showDispositionDialog(lead, callState.duration),
              icon: const Icon(Icons.edit_note_rounded),
              label: const Text('Add Disposition'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accent,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
          ),
        ],
      );
    }

    return Row(
      children: [
        // Skip button
        Expanded(
          child: OutlinedButton.icon(
            onPressed: queue.isActive
                ? () => ref.read(dialerQueueProvider.notifier).skipLead()
                : null,
            icon: const Icon(Icons.skip_next_rounded, size: 20),
            label: const Text('Skip'),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.textSecondary,
              side: const BorderSide(color: AppColors.divider),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
          ),
        ),
        const SizedBox(width: 12),
        // Main call / start button
        Expanded(
          flex: 2,
          child: Container(
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(14),
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withOpacity(0.4),
                  blurRadius: 20,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: ElevatedButton.icon(
              onPressed: isIdle ? () => _startCall(lead) : null,
              icon: Icon(queue.isActive ? Icons.phone_rounded : Icons.play_arrow_rounded,
                  size: 22),
              label: Text(queue.isActive ? 'Call Now' : 'Start Auto-Dial',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.transparent,
                shadowColor: Colors.transparent,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildQueuePreview(DialerQueueState queue) {
    final upcoming = queue.queue
        .skip(queue.currentIndex + 1)
        .take(3)
        .toList();
    if (upcoming.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Up Next', style: TextStyle(fontSize: 14, color: AppColors.textSecondary)),
        const SizedBox(height: 10),
        ...upcoming.map(
          (lead) => Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.backgroundCard,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.divider),
            ),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    lead.name.isNotEmpty ? lead.name[0].toUpperCase() : '?',
                    style: const TextStyle(
                        fontWeight: FontWeight.w700, color: AppColors.textSecondary),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(lead.name,
                          style: const TextStyle(
                              color: AppColors.textPrimary,
                              fontWeight: FontWeight.w500,
                              fontSize: 13)),
                      Text(lead.phone,
                          style: TextStyle(color: AppColors.textHint, fontSize: 12)),
                    ],
                  ),
                ),
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: AppColors.statusColor(lead.status),
                    shape: BoxShape.circle,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(28),
            ),
            child: const Icon(Icons.check_circle_rounded, color: Colors.white, size: 52),
          ).animate().scale(duration: 600.ms, curve: Curves.elasticOut),
          const SizedBox(height: 24),
          const Text('No Leads to Dial',
              style: TextStyle(
                  fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
          const SizedBox(height: 8),
          Text(
            'All leads have been processed.\nCheck back later for new assignments.',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => ref.read(dialerQueueProvider.notifier).loadQueue(),
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Refresh Queue'),
          ),
        ],
      ),
    );
  }

  Widget _buildCompletedState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              gradient: AppColors.successGradient,
              borderRadius: BorderRadius.circular(28),
            ),
            child: const Icon(Icons.celebration_rounded, color: Colors.white, size: 52),
          ).animate().scale(duration: 600.ms, curve: Curves.elasticOut),
          const SizedBox(height: 24),
          const Text('Queue Completed! 🎉',
              style: TextStyle(
                  fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
          const SizedBox(height: 8),
          Text(
            'You\'ve called all assigned leads.',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => ref.read(dialerQueueProvider.notifier).loadQueue(),
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Reload Queue'),
          ),
        ],
      ),
    );
  }
}
