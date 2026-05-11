// lib/screens/permission_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/theme.dart';
import 'login_screen.dart';

class PermissionScreen extends StatefulWidget {
  const PermissionScreen({super.key});

  @override
  State<PermissionScreen> createState() => _PermissionScreenState();
}

class _PermissionScreenState extends State<PermissionScreen> {
  bool _isRequesting = false;

  final List<Map<String, dynamic>> _permissions = [
    {
      'permission': Permission.phone,
      'title': 'Phone Access',
      'desc': 'Required to make automated calls to your leads directly from the app.',
      'icon': Icons.phone_android_rounded,
      'color': AppColors.primary,
    },
    {
      'permission': Permission.microphone,
      'title': 'Microphone',
      'desc': 'Used for high-quality call recording for training and audit purposes.',
      'icon': Icons.mic_rounded,
      'color': AppColors.accent,
    },
    {
      'permission': Permission.notification,
      'title': 'Notifications',
      'desc': 'Get timely reminders for your scheduled follow-ups and meetings.',
      'icon': Icons.notifications_active_rounded,
      'color': AppColors.secondary,
    },
  ];

  Future<void> _requestAll() async {
    setState(() => _isRequesting = true);

    Map<Permission, PermissionStatus> statuses = await [
      Permission.phone,
      Permission.microphone,
      Permission.notification,
    ].request();

    setState(() => _isRequesting = false);

    // If all critical permissions (phone, mic) are granted, move forward
    if (statuses[Permission.phone]!.isGranted &&
        statuses[Permission.microphone]!.isGranted) {
      _finish();
    } else {
      // Show error or warning if mandatory ones are missing
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Phone and Microphone permissions are mandatory for TeleCRM.'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }

  Future<void> _finish() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('permissions_requested', true);

    if (mounted) {
      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          pageBuilder: (_, __, ___) => const LoginScreen(),
          transitionsBuilder: (_, animation, __, child) =>
              FadeTransition(opacity: animation, child: child),
          transitionDuration: const Duration(milliseconds: 500),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F0E1A),
      body: Stack(
        children: [
          // Background blobs
          Positioned(
            top: -100,
            left: -100,
            child: _buildBlurCircle(AppColors.primary.withOpacity(0.15), 300),
          ),
          Positioned(
            bottom: -50,
            right: -50,
            child: _buildBlurCircle(AppColors.accent.withOpacity(0.1), 250),
          ),

          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 40),
                  // Header
                  const Text(
                    'Let\'s Get\nStarted',
                    style: TextStyle(
                      fontSize: 40,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      height: 1.1,
                    ),
                  ).animate().fade(duration: 600.ms).slideX(begin: -0.2),
                  const SizedBox(height: 12),
                  Text(
                    'To provide the best tele-calling experience, we need a few permissions.',
                    style: TextStyle(
                      fontSize: 16,
                      color: AppColors.textSecondary,
                    ),
                  ).animate(delay: 200.ms).fade(),

                  const SizedBox(height: 40),

                  // Permission list
                  Expanded(
                    child: ListView.separated(
                      itemCount: _permissions.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 20),
                      itemBuilder: (context, index) {
                        final p = _permissions[index];
                        return _buildPermissionItem(p, index);
                      },
                    ),
                  ),

                  // Footer button
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 30),
                    child: Column(
                      children: [
                        Container(
                          width: double.infinity,
                          height: 56,
                          decoration: BoxDecoration(
                            gradient: AppColors.primaryGradient,
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(
                                color: AppColors.primary.withOpacity(0.3),
                                blurRadius: 20,
                                offset: const Offset(0, 10),
                              ),
                            ],
                          ),
                          child: ElevatedButton(
                            onPressed: _isRequesting ? null : _requestAll,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.transparent,
                              shadowColor: Colors.transparent,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                            child: _isRequesting
                                ? const SizedBox(
                                    width: 24,
                                    height: 24,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                    ),
                                  )
                                : const Text(
                                    'Grant Permissions',
                                    style: TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w700,
                                      color: Colors.white,
                                    ),
                                  ),
                          ),
                        ).animate(delay: 1000.ms).scale().fade(),
                        const SizedBox(height: 16),
                        Text(
                          'Your data is encrypted and never shared.',
                          style: TextStyle(
                            fontSize: 12,
                            color: AppColors.textHint,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBlurCircle(Color color, double size) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [color, Colors.transparent],
        ),
      ),
    );
  }

  Widget _buildPermissionItem(Map<String, dynamic> p, int index) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: (p['color'] as Color).withOpacity(0.15),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(p['icon'], color: p['color'], size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  p['title'],
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  p['desc'],
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ).animate(delay: (400 + (index * 150)).ms).fade().slideX(begin: 0.1);
  }
}
