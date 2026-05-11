// lib/screens/splash_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/theme.dart';
import '../services/auth_service.dart';
import 'home_screen.dart';
import 'login_screen.dart';
import 'permission_screen.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 2000));
    _controller.forward();
    Future.delayed(const Duration(milliseconds: 2800), _navigate);
  }

  Future<void> _navigate() async {
    if (!mounted) return;
    
    final prefs = await SharedPreferences.getInstance();
    final permissionsRequested = prefs.getBool('permissions_requested') ?? false;
    
    final auth = ref.read(authProvider);
    
    Widget nextScreen;
    if (!permissionsRequested) {
      nextScreen = const PermissionScreen();
    } else {
      nextScreen = auth.isAuthenticated ? const HomeScreen() : const LoginScreen();
    }

    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => nextScreen,
        transitionsBuilder: (_, animation, __, child) =>
            FadeTransition(opacity: animation, child: child),
        transitionDuration: const Duration(milliseconds: 500),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF0F0E1A), Color(0xFF2A1060), Color(0xFF0F0E1A)],
            stops: [0.0, 0.5, 1.0],
          ),
        ),
        child: Stack(
          children: [
            // Animated background circles
            Positioned(
              top: -80,
              right: -80,
              child: Container(
                width: 300,
                height: 300,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      AppColors.primary.withOpacity(0.3),
                      Colors.transparent,
                    ],
                  ),
                ),
              )
                  .animate()
                  .scale(begin: const Offset(0.5, 0.5), duration: 2000.ms, curve: Curves.easeOut),
            ),
            Positioned(
              bottom: -100,
              left: -100,
              child: Container(
                width: 350,
                height: 350,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      AppColors.accent.withOpacity(0.2),
                      Colors.transparent,
                    ],
                  ),
                ),
              )
                  .animate()
                  .scale(begin: const Offset(0.3, 0.3), duration: 2000.ms, curve: Curves.easeOut),
            ),
            // Center content
            Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Logo icon
                  Container(
                    width: 110,
                    height: 110,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(24),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.3),
                          blurRadius: 30,
                          spreadRadius: 2,
                        ),
                      ],
                    ),
                    child: Image.asset(
                      'assets/icons/icon.png',
                      fit: BoxFit.contain,
                    ),
                  )
                      .animate()
                      .scale(begin: const Offset(0, 0), duration: 600.ms, curve: Curves.elasticOut)
                      .fade(duration: 400.ms),
                  const SizedBox(height: 28),
                  // App name
                  ShaderMask(
                    shaderCallback: (bounds) => AppColors.primaryGradient.createShader(bounds),
                    child: const Text(
                      'TeleCRM',
                      style: TextStyle(
                        fontSize: 42,
                        fontWeight: FontWeight.w800,
                        color: Colors.white,
                        letterSpacing: -1,
                      ),
                    ),
                  )
                      .animate(delay: 400.ms)
                      .slideY(begin: 0.3, duration: 600.ms, curve: Curves.easeOut)
                      .fade(duration: 600.ms),
                  const SizedBox(height: 10),
                  Text(
                    'Smart Calling · Smart Selling',
                    style: TextStyle(
                      fontSize: 15,
                      color: AppColors.textSecondary,
                      letterSpacing: 0.5,
                    ),
                  )
                      .animate(delay: 600.ms)
                      .fade(duration: 600.ms),
                  const SizedBox(height: 60),
                  // Loading indicator
                  SizedBox(
                    width: 160,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        backgroundColor: AppColors.divider,
                        valueColor: AlwaysStoppedAnimation<Color>(AppColors.primaryLight),
                        minHeight: 3,
                      ),
                    ),
                  )
                      .animate(delay: 800.ms)
                      .fade(duration: 400.ms),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
