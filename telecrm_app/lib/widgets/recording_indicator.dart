// lib/widgets/recording_indicator.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../core/theme.dart';

class RecordingIndicator extends StatelessWidget {
  const RecordingIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.error.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.error.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Pulsing red dot
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: AppColors.error,
              shape: BoxShape.circle,
            ),
          )
              .animate(onPlay: (c) => c.repeat())
              .fade(begin: 1, end: 0.2, duration: 700.ms, curve: Curves.easeInOut)
              .then()
              .fade(begin: 0.2, end: 1, duration: 700.ms, curve: Curves.easeInOut),
          const SizedBox(width: 6),
          const Text(
            'REC',
            style: TextStyle(
              color: AppColors.error,
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}
