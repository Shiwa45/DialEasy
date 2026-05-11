// lib/widgets/agent_target_card.dart
//
// Shows an animated circular progress ring for a numeric target.
// Used on Dashboard and Profile screens.
//
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../core/theme.dart';

class AgentTargetCard extends StatelessWidget {
  final String title;
  final int current;
  final int target;
  final IconData icon;
  final Color color;
  final String? subtitle;

  const AgentTargetCard({
    super.key,
    required this.title,
    required this.current,
    required this.target,
    required this.icon,
    required this.color,
    this.subtitle,
  });

  double get progress => target > 0 ? (current / target).clamp(0.0, 1.0) : 0.0;
  bool get achieved => current >= target;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: achieved
              ? color.withOpacity(0.5)
              : AppColors.divider,
        ),
        boxShadow: achieved
            ? [
                BoxShadow(
                  color: color.withOpacity(0.2),
                  blurRadius: 20,
                  offset: const Offset(0, 6),
                )
              ]
            : null,
      ),
      child: Row(
        children: [
          // Ring chart
          SizedBox(
            width: 72,
            height: 72,
            child: CustomPaint(
              painter: _RingPainter(
                progress: progress,
                color: color,
                backgroundColor: color.withOpacity(0.12),
                strokeWidth: 7,
              ),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '${(progress * 100).toInt()}',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: color,
                      ),
                    ),
                    Text(
                      '%',
                      style: TextStyle(
                        fontSize: 9,
                        color: color.withOpacity(0.7),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ).animate().scale(
                begin: const Offset(0.5, 0.5),
                duration: 600.ms,
                curve: Curves.elasticOut,
              ),
          const SizedBox(width: 16),
          // Text content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(icon, color: color, size: 16),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        title,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                    if (achieved)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          '🎯 Done!',
                          style: TextStyle(
                              fontSize: 10,
                              color: color,
                              fontWeight: FontWeight.w700),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                // Progress bar
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: progress),
                    duration: const Duration(milliseconds: 900),
                    curve: Curves.easeOut,
                    builder: (_, val, __) => LinearProgressIndicator(
                      value: val,
                      backgroundColor: color.withOpacity(0.12),
                      valueColor: AlwaysStoppedAnimation<Color>(color),
                      minHeight: 6,
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '$current of $target',
                      style: TextStyle(
                        fontSize: 12,
                        color: color,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    Text(
                      subtitle ?? '${target - current > 0 ? target - current : 0} to go',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppColors.textHint,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// Custom ring painter
class _RingPainter extends CustomPainter {
  final double progress;
  final Color color;
  final Color backgroundColor;
  final double strokeWidth;

  const _RingPainter({
    required this.progress,
    required this.color,
    required this.backgroundColor,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (size.width - strokeWidth) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);

    // Background ring
    canvas.drawArc(
      rect,
      -math.pi / 2,
      2 * math.pi,
      false,
      Paint()
        ..color = backgroundColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round,
    );

    // Progress ring
    if (progress > 0) {
      canvas.drawArc(
        rect,
        -math.pi / 2,
        2 * math.pi * progress,
        false,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = strokeWidth
          ..strokeCap = StrokeCap.round,
      );
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.progress != progress || old.color != color;
}
