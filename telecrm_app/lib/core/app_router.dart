// lib/core/app_router.dart
import 'package:flutter/material.dart';
import '../models/models.dart';
import '../screens/call_history_screen.dart';
import '../screens/home_screen.dart';
import '../screens/lead_detail_screen.dart';
import '../screens/login_screen.dart';
import '../screens/performance_screen.dart';
import '../screens/splash_screen.dart';

class AppRoutes {
  static const splash = '/';
  static const login = '/login';
  static const home = '/home';
  static const leadDetail = '/lead-detail';
  static const performance = '/performance';
  static const callHistory = '/call-history';
}

class AppRouter {
  static Route<dynamic> generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case AppRoutes.splash:
        return _fade(const SplashScreen());
      case AppRoutes.login:
        return _fade(const LoginScreen());
      case AppRoutes.home:
        return _fade(const HomeScreen());
      case AppRoutes.leadDetail:
        final lead = settings.arguments as Lead;
        return _slide(LeadDetailScreen(lead: lead));
      case AppRoutes.performance:
        return _slide(const PerformanceScreen());
      case AppRoutes.callHistory:
        return _slide(const CallHistoryScreen());
      default:
        return _fade(const SplashScreen());
    }
  }

  static PageRoute _fade(Widget page) => PageRouteBuilder(
        pageBuilder: (_, __, ___) => page,
        transitionsBuilder: (_, animation, __, child) =>
            FadeTransition(opacity: animation, child: child),
        transitionDuration: const Duration(milliseconds: 300),
      );

  static PageRoute _slide(Widget page) => PageRouteBuilder(
        pageBuilder: (_, __, ___) => page,
        transitionsBuilder: (_, animation, __, child) => SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(1, 0),
            end: Offset.zero,
          ).animate(CurvedAnimation(parent: animation, curve: Curves.easeOut)),
          child: child,
        ),
        transitionDuration: const Duration(milliseconds: 300),
      );
}
