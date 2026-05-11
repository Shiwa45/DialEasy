// lib/screens/home_screen.dart
import 'package:badges/badges.dart' as badges;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../services/connectivity_service.dart';
import '../services/lead_service.dart';
import '../widgets/call_overlay_widget.dart';
import 'dashboard_screen.dart';
import 'dialer_screen.dart';
import 'leads_screen.dart';
import 'follow_ups_screen.dart';
import 'profile_screen.dart';

final homeTabProvider = StateProvider<int>((ref) => 0);

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  static const _pages = [
    DashboardScreen(),
    DialerScreen(),
    LeadsScreen(),
    FollowUpsScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final tab = ref.watch(homeTabProvider);
    final followUps = ref.watch(followUpsProvider);
    final overdueCount = followUps.overdue.length;

    return Scaffold(
      body: CallOverlay(
        child: OfflineBanner(
          child: IndexedStack(index: tab, children: _pages),
        ),
      ),
      bottomNavigationBar: _CRMBottomNav(
        currentIndex: tab,
        overdueCount: overdueCount,
        onTap: (i) => ref.read(homeTabProvider.notifier).state = i,
      ),
    );
  }
}

class _CRMBottomNav extends StatelessWidget {
  final int currentIndex;
  final int overdueCount;
  final void Function(int) onTap;

  const _CRMBottomNav({
    required this.currentIndex,
    required this.overdueCount,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        border: Border(top: BorderSide(color: AppColors.divider, width: 1)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.4),
            blurRadius: 24,
            offset: const Offset(0, -8),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _NavItem(
                icon: Icons.dashboard_rounded,
                label: 'Dashboard',
                isActive: currentIndex == 0,
                onTap: () => onTap(0),
              ),
              _NavItem(
                icon: Icons.phone_forwarded_rounded,
                label: 'Auto-Dial',
                isActive: currentIndex == 1,
                onTap: () => onTap(1),
                isPrimary: true,
              ),
              _NavItem(
                icon: Icons.people_alt_rounded,
                label: 'Leads',
                isActive: currentIndex == 2,
                onTap: () => onTap(2),
              ),
              _NavItem(
                icon: Icons.event_note_rounded,
                label: 'Follow-ups',
                isActive: currentIndex == 3,
                onTap: () => onTap(3),
                badge: overdueCount,
              ),
              _NavItem(
                icon: Icons.person_rounded,
                label: 'Profile',
                isActive: currentIndex == 4,
                onTap: () => onTap(4),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final bool isPrimary;
  final int badge;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.onTap,
    this.isPrimary = false,
    this.badge = 0,
  });

  @override
  Widget build(BuildContext context) {
    if (isPrimary) {
      return GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
          decoration: BoxDecoration(
            gradient: isActive ? AppColors.primaryGradient : null,
            color: isActive ? null : AppColors.surface,
            borderRadius: BorderRadius.circular(20),
            boxShadow: isActive
                ? [
                    BoxShadow(
                      color: AppColors.primary.withOpacity(0.4),
                      blurRadius: 16,
                      spreadRadius: 2,
                    )
                  ]
                : null,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: Colors.white, size: 20),
              const SizedBox(width: 6),
              Text(
                label,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      );
    }

    Widget iconWidget = Icon(
      icon,
      color: isActive ? AppColors.primaryLight : AppColors.textHint,
      size: 24,
    );

    if (badge > 0) {
      iconWidget = badges.Badge(
        badgeContent: Text(
          badge > 9 ? '9+' : badge.toString(),
          style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
        ),
        badgeStyle: const badges.BadgeStyle(
          badgeColor: AppColors.error,
          padding: EdgeInsets.all(4),
        ),
        child: iconWidget,
      );
    }

    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: isActive ? AppColors.primary.withOpacity(0.15) : Colors.transparent,
              borderRadius: BorderRadius.circular(12),
            ),
            child: iconWidget,
          ),
          const SizedBox(height: 2),
          AnimatedDefaultTextStyle(
            duration: const Duration(milliseconds: 200),
            style: TextStyle(
              fontSize: 10,
              fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
              color: isActive ? AppColors.primaryLight : AppColors.textHint,
            ),
            child: Text(label),
          ),
        ],
      ),
    );
  }
}
