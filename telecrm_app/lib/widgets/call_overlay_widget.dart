// lib/widgets/call_overlay_widget.dart
//
// Usage: Wrap your page content with CallOverlay() to show a
// floating "Call in progress" pill whenever a call is active.
//
// Example in HomeScreen:
//   body: CallOverlay(child: IndexedStack(…))
//
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../services/call_service.dart';
import '../services/lead_service.dart';

class CallOverlay extends ConsumerWidget {
  final Widget child;
  const CallOverlay({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final callState = ref.watch(callStateProvider);
    final isVisible = callState.status == CallStatus.active ||
        callState.status == CallStatus.dialing ||
        callState.status == CallStatus.ringing;

    return Stack(
      children: [
        child,
        if (isVisible)
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            left: 20,
            right: 20,
            child: _CallPill(state: callState),
          ),
      ],
    );
  }
}

class _CallPill extends ConsumerStatefulWidget {
  final CallStateModel state;
  const _CallPill({required this.state});

  @override
  ConsumerState<_CallPill> createState() => _CallPillState();
}

class _CallPillState extends ConsumerState<_CallPill> {
  Timer? _timer;
  Duration _elapsed = Duration.zero;

  @override
  void initState() {
    super.initState();
    _startTimer();
  }

  void _startTimer() {
    _timer?.cancel();
    if (widget.state.status == CallStatus.active) {
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() => _elapsed += const Duration(seconds: 1));
      });
    }
  }

  Future<void> _disposeCurrentCall(WidgetRef ref, BuildContext context) async {
    final queue = ref.read(dialerQueueProvider);
    final wasAutoDialing = queue.isActive;

    ref.read(callStateProvider.notifier).reset();

    if (!wasAutoDialing) return;

    ref.read(dialerQueueProvider.notifier).nextLead();
    final nextLead = ref.read(dialerQueueProvider).currentLead;
    if (nextLead != null) {
      await ref.read(callStateProvider.notifier).call(nextLead.phone);
    }
  }

  @override
  void didUpdateWidget(_CallPill old) {
    super.didUpdateWidget(old);
    if (old.state.status != widget.state.status) {
      if (widget.state.status == CallStatus.active) {
        _elapsed = Duration.zero;
        _startTimer();
      } else {
        _timer?.cancel();
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  String get _timeLabel {
    final m = _elapsed.inMinutes.toString().padLeft(2, '0');
    final s = (_elapsed.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final isActive = widget.state.status == CallStatus.active;
    final isDialing = widget.state.status == CallStatus.dialing ||
        widget.state.status == CallStatus.ringing;

    final bgColor = isActive ? AppColors.success : AppColors.primary;
    final label = isActive
        ? '📞  In Call · $_timeLabel'
        : widget.state.status == CallStatus.dialing
            ? '📲  Dialing…'
            : '🔔  Ringing…';

    return Material(
      color: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(30),
          boxShadow: [
            BoxShadow(
              color: bgColor.withOpacity(0.5),
              blurRadius: 20,
              spreadRadius: 2,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            // Pulsing dot
            _PulsingDot(color: Colors.white),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.2,
                ),
              ),
            ),
            // End call hint
            if (isDialing || isActive)
              GestureDetector(
                onTap: () async => await _disposeCurrentCall(ref, context),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    'Dispose',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
          ],
        ),
      )
          .animate()
          .slideY(begin: -1.0, duration: 350.ms, curve: Curves.easeOut)
          .fade(duration: 300.ms),
    );
  }
}

class _PulsingDot extends StatefulWidget {
  final Color color;
  const _PulsingDot({required this.color});

  @override
  State<_PulsingDot> createState() => _PulsingDotState();
}

class _PulsingDotState extends State<_PulsingDot>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    _anim = Tween<double>(begin: 0.4, end: 1.0).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _anim,
        builder: (_, __) => Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: widget.color.withOpacity(_anim.value),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: widget.color.withOpacity(_anim.value * 0.6),
                blurRadius: 6,
                spreadRadius: 2,
              ),
            ],
          ),
        ),
      );
}
