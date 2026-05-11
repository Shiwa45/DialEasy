// lib/widgets/common_widgets.dart
import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../core/theme.dart';

// ─────────────────────────────────────────────────────────
// GRADIENT BUTTON
// ─────────────────────────────────────────────────────────
class GradientButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onTap;
  final LinearGradient gradient;
  final double height;
  final double borderRadius;
  final bool isLoading;

  const GradientButton({
    super.key,
    required this.label,
    this.icon,
    this.onTap,
    this.gradient = AppColors.primaryGradient,
    this.height = 52,
    this.borderRadius = 14,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      width: double.infinity,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: onTap == null
              ? LinearGradient(
                  colors: gradient.colors
                      .map((c) => c.withOpacity(0.5))
                      .toList())
              : gradient,
          borderRadius: BorderRadius.circular(borderRadius),
          boxShadow: onTap != null
              ? [
                  BoxShadow(
                    color: gradient.colors.first.withOpacity(0.35),
                    blurRadius: 18,
                    offset: const Offset(0, 6),
                  )
                ]
              : null,
        ),
        child: ElevatedButton(
          onPressed: isLoading ? null : onTap,
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.transparent,
            shadowColor: Colors.transparent,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(borderRadius)),
          ),
          child: isLoading
              ? const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(
                      color: Colors.white, strokeWidth: 2.5),
                )
              : Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (icon != null) ...[
                      Icon(icon, color: Colors.white, size: 20),
                      const SizedBox(width: 8),
                    ],
                    Text(
                      label,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                        letterSpacing: 0.3,
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// GLASS CARD
// A frosted-glass-style card
// ─────────────────────────────────────────────────────────
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final double borderRadius;
  final Color? borderColor;

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.borderRadius = 18,
    this.borderColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(
          color: borderColor ?? AppColors.divider,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.2),
            blurRadius: 20,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }
}

// ─────────────────────────────────────────────────────────
// STATUS DOT
// ─────────────────────────────────────────────────────────
class StatusDot extends StatelessWidget {
  final String status;
  final double size;

  const StatusDot({super.key, required this.status, this.size = 10});

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: AppColors.statusColor(status),
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: AppColors.statusColor(status).withOpacity(0.5),
              blurRadius: 4,
              spreadRadius: 1,
            ),
          ],
        ),
      );
}

// ─────────────────────────────────────────────────────────
// SECTION HEADER
// ─────────────────────────────────────────────────────────
class SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  const SectionHeader({
    super.key,
    required this.title,
    required this.icon,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppColors.primaryLight, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
          ),
          if (actionLabel != null && onAction != null)
            GestureDetector(
              onTap: onAction,
              child: Text(
                actionLabel!,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.primaryLight,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
        ],
      );
}

// ─────────────────────────────────────────────────────────
// SHIMMER LIST (loading placeholder)
// ─────────────────────────────────────────────────────────
class ShimmerList extends StatelessWidget {
  final int count;
  const ShimmerList({super.key, this.count = 6});

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: AppColors.backgroundCard,
      highlightColor: AppColors.backgroundElevated,
      child: ListView.builder(
        itemCount: count,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemBuilder: (_, __) => Container(
          margin: const EdgeInsets.only(bottom: 10),
          height: 88,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// METRIC CARD (used on dashboard / performance)
// ─────────────────────────────────────────────────────────
class MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final String? subtitle;
  final IconData icon;
  final Color color;
  final LinearGradient? gradient;

  const MetricCard({
    super.key,
    required this.label,
    required this.value,
    this.subtitle,
    required this.icon,
    required this.color,
    this.gradient,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: gradient ??
            LinearGradient(
              colors: [color.withOpacity(0.2), color.withOpacity(0.05)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 18),
              ),
              if (subtitle != null)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    subtitle!,
                    style:
                        TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// EMPTY STATE
// ─────────────────────────────────────────────────────────
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;
  final Color? iconColor;

  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color:
                      (iconColor ?? AppColors.textHint).withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  icon,
                  color: iconColor ?? AppColors.textHint,
                  size: 40,
                ),
              ),
              const SizedBox(height: 20),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 8),
                Text(
                  subtitle!,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppColors.textSecondary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
              if (actionLabel != null && onAction != null) ...[
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: onAction,
                  icon: const Icon(Icons.refresh_rounded),
                  label: Text(actionLabel!),
                ),
              ],
            ],
          ),
        ),
      );
}

// ─────────────────────────────────────────────────────────
// CALL DURATION DISPLAY
// ─────────────────────────────────────────────────────────
class CallDurationDisplay extends StatelessWidget {
  final Duration duration;
  final Color color;
  const CallDurationDisplay(
      {super.key, required this.duration, this.color = AppColors.success});

  String get _formatted {
    final m = duration.inMinutes.toString().padLeft(2, '0');
    final s = (duration.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.timer_rounded, color: color, size: 16),
          const SizedBox(width: 4),
          Text(
            _formatted,
            style: TextStyle(
              color: color,
              fontSize: 14,
              fontWeight: FontWeight.w700,
              fontFamily: 'monospace',
            ),
          ),
        ],
      );
}

// ─────────────────────────────────────────────────────────
// BADGE CHIP
// ─────────────────────────────────────────────────────────
class BadgeChip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;

  const BadgeChip({
    super.key,
    required this.label,
    required this.color,
    this.icon,
  });

  @override
  Widget build(BuildContext context) => Container(
        padding:
            const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: color.withOpacity(0.15),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, color: color, size: 12),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      );
}

// ─────────────────────────────────────────────────────────
// ANIMATED COUNT (number rolls up on appear)
// ─────────────────────────────────────────────────────────
class AnimatedCount extends StatelessWidget {
  final int value;
  final TextStyle? style;

  const AnimatedCount({super.key, required this.value, this.style});

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value.toDouble()),
      duration: const Duration(milliseconds: 800),
      curve: Curves.easeOut,
      builder: (_, val, __) => Text(
        val.toInt().toString(),
        style: style ??
            const TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
      ),
    );
  }
}
