// lib/screens/profile_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/app_config_provider.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/auth_service.dart';
import '../services/lead_service.dart';
import '../widgets/agent_target_card.dart';
import 'call_history_screen.dart';
import 'login_screen.dart';
import 'performance_screen.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final user = auth.user;
    final profile = auth.profile;
    final dashAsync = ref.watch(dashboardProvider);

    return Scaffold(
      body: Container(
        decoration:
            const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Column(children: [
              const SizedBox(height: 20),
              _buildHeader(user, profile)
                  .animate()
                  .slideY(begin: -0.2, duration: 500.ms)
                  .fade(),
              const SizedBox(height: 24),
              dashAsync.when(
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
                data: (d) => _buildStats(d)
                    .animate()
                    .slideY(begin: 0.2, duration: 400.ms, delay: 100.ms)
                    .fade(),
              ),
              const SizedBox(height: 20),
              if (profile != null)
                _buildTargets(profile, ref)
                    .animate()
                    .slideY(begin: 0.2, duration: 400.ms, delay: 200.ms)
                    .fade(),
              const SizedBox(height: 20),
              _buildQuickNav(context)
                  .animate()
                  .slideY(begin: 0.2, duration: 400.ms, delay: 250.ms)
                  .fade(),
              const SizedBox(height: 20),
              _buildInfo(user, profile)
                  .animate()
                  .slideY(begin: 0.2, duration: 400.ms, delay: 300.ms)
                  .fade(),
              const SizedBox(height: 20),
              _buildActions(context, ref)
                  .animate()
                  .slideY(begin: 0.2, duration: 400.ms, delay: 400.ms)
                  .fade(),
              const SizedBox(height: 80),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(AppUser? user, AgentProfile? profile) =>
      Column(children: [
        Container(
          width: 90, height: 90,
          decoration: BoxDecoration(
            gradient: AppColors.primaryGradient,
            borderRadius: BorderRadius.circular(26),
            boxShadow: [BoxShadow(color: AppColors.primary.withOpacity(0.4), blurRadius: 24, spreadRadius: 4)],
          ),
          alignment: Alignment.center,
          child: Text(user?.initials ?? 'A',
              style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w800, color: Colors.white)),
        ),
        const SizedBox(height: 16),
        Text(user?.fullName ?? 'Agent',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
        const SizedBox(height: 4),
        Text(user?.email ?? '', style: const TextStyle(fontSize: 14, color: AppColors.textSecondary)),
        const SizedBox(height: 8),
        if (profile?.department != null && profile!.department.isNotEmpty)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(gradient: AppColors.primaryGradient, borderRadius: BorderRadius.circular(20)),
            child: Text(profile.department,
                style: const TextStyle(fontSize: 13, color: Colors.white, fontWeight: FontWeight.w600)),
          ),
      ]);

  Widget _buildStats(DashboardSummary d) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('My Performance',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: _StatBox(label: 'Total Leads', value: '${d.totalLeads}', gradient: AppColors.primaryGradient)),
            const SizedBox(width: 10),
            Expanded(child: _StatBox(label: 'Week Calls', value: '${d.weekCalls}', gradient: AppColors.accentGradient)),
            const SizedBox(width: 10),
            Expanded(child: _StatBox(label: 'Converted', value: '${d.convertedLeads}', gradient: AppColors.successGradient)),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: _StatBox(label: "Today's Calls", value: '${d.todayCalls}', gradient: AppColors.cyanGradient)),
            const SizedBox(width: 10),
            Expanded(child: _StatBox(label: 'Pending FU', value: '${d.pendingFollowUps}',
                gradient: const LinearGradient(colors: [Color(0xFFFFB800), Color(0xFFFF8C00)]))),
            const SizedBox(width: 10),
            Expanded(child: _StatBox(label: 'Conv. Rate', value: '${d.conversionRate.toStringAsFixed(1)}%',
                gradient: const LinearGradient(colors: [Color(0xFF9B6DFF), Color(0xFF6C3CE1)]))),
          ]),
        ],
      );

  Widget _buildTargets(AgentProfile profile, WidgetRef ref) {
    final config = ref.watch(appConfigProvider);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: AppColors.backgroundCard, borderRadius: BorderRadius.circular(18), border: Border.all(color: AppColors.divider)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Row(children: [
          Icon(Icons.flag_rounded, color: AppColors.accent, size: 18), SizedBox(width: 8),
          Text('My Targets', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
        ]),
        const SizedBox(height: 16),
        AgentTargetCard(
          title: 'Daily Calls Target',
          current: 0,
          target: config.dailyCallsTarget,
          icon: Icons.phone_rounded,
          color: AppColors.primary,
        ),
        const SizedBox(height: 10),
        AgentTargetCard(
          title: 'Monthly Conversions',
          current: 0,
          target: config.monthlyConversionsTarget,
          icon: Icons.check_circle_rounded,
          color: AppColors.success,
        ),
      ]),
    );
  }

  Widget _buildQuickNav(BuildContext context) => Row(children: [
        Expanded(child: _NavCard(
          icon: Icons.bar_chart_rounded, label: 'Performance',
          gradient: AppColors.primaryGradient,
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const PerformanceScreen())),
        )),
        const SizedBox(width: 12),
        Expanded(child: _NavCard(
          icon: Icons.history_rounded, label: 'Call History',
          gradient: AppColors.accentGradient,
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const CallHistoryScreen())),
        )),
      ]);

  Widget _buildInfo(AppUser? user, AgentProfile? profile) => Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(color: AppColors.backgroundCard, borderRadius: BorderRadius.circular(18), border: Border.all(color: AppColors.divider)),
        child: Column(children: [
          _InfoTile(icon: Icons.person_rounded, label: 'Username', value: user?.username ?? ''),
          const Divider(height: 20),
          _InfoTile(icon: Icons.email_rounded, label: 'Email', value: user?.email ?? ''),
          if (profile?.phone != null && profile!.phone.isNotEmpty) ...[
            const Divider(height: 20),
            _InfoTile(icon: Icons.phone_rounded, label: 'Phone', value: profile.phone),
          ],
          if (profile?.hireDate != null) ...[
            const Divider(height: 20),
            _InfoTile(icon: Icons.work_history_rounded, label: 'Hire Date', value: profile!.hireDate!),
          ],
        ]),
      );

  Widget _buildActions(BuildContext context, WidgetRef ref) => Container(
        decoration: BoxDecoration(color: AppColors.backgroundCard, borderRadius: BorderRadius.circular(18), border: Border.all(color: AppColors.divider)),
        child: Column(children: [
          _ActionTile(icon: Icons.refresh_rounded, label: 'Refresh Profile',
              onTap: () => ref.read(authProvider.notifier).refreshProfile()),
          const Divider(height: 1),
          _ActionTile(icon: Icons.info_outline_rounded, label: 'App Version',
              trailing: const Text('1.0.0', style: TextStyle(color: AppColors.textHint, fontSize: 13)), onTap: () {}),
          const Divider(height: 1),
          _ActionTile(
            icon: Icons.logout_rounded, label: 'Sign Out', color: AppColors.error,
            onTap: () async {
              final confirm = await showDialog<bool>(
                context: context,
                builder: (_) => AlertDialog(
                  backgroundColor: AppColors.backgroundCard,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  title: const Text('Sign Out', style: TextStyle(color: AppColors.textPrimary)),
                  content: const Text('Are you sure?', style: TextStyle(color: AppColors.textSecondary)),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                    ElevatedButton(onPressed: () => Navigator.pop(context, true),
                        style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
                        child: const Text('Sign Out')),
                  ],
                ),
              );
              if (confirm == true && context.mounted) {
                await ref.read(authProvider.notifier).logout();
                Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(builder: (_) => const LoginScreen()), (_) => false,
                );
              }
            },
          ),
        ]),
      );
}

// ─────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────
class _NavCard extends StatelessWidget {
  final IconData icon; final String label; final LinearGradient gradient; final VoidCallback onTap;
  const _NavCard({required this.icon, required this.label, required this.gradient, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 16),
          decoration: BoxDecoration(
            gradient: gradient, borderRadius: BorderRadius.circular(16),
            boxShadow: [BoxShadow(color: gradient.colors.first.withOpacity(0.3), blurRadius: 14, offset: const Offset(0, 5))],
          ),
          child: Row(children: [
            Icon(icon, color: Colors.white, size: 22),
            const SizedBox(width: 10),
            Text(label, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w700)),
          ]),
        ),
      );
}

class _StatBox extends StatelessWidget {
  final String label, value; final LinearGradient gradient;
  const _StatBox({required this.label, required this.value, required this.gradient});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        decoration: BoxDecoration(gradient: gradient, borderRadius: BorderRadius.circular(14),
            boxShadow: [BoxShadow(color: gradient.colors.first.withOpacity(0.25), blurRadius: 12, offset: const Offset(0, 4))]),
        child: Column(children: [
          Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: Colors.white)),
          Text(label, style: const TextStyle(fontSize: 10, color: Colors.white70), textAlign: TextAlign.center),
        ]),
      );
}

class _InfoTile extends StatelessWidget {
  final IconData icon; final String label, value;
  const _InfoTile({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) => Row(children: [
        Container(width: 34, height: 34,
            decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10)),
            child: Icon(icon, color: AppColors.textSecondary, size: 16)),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textHint)),
          Text(value, style: const TextStyle(fontSize: 14, color: AppColors.textPrimary)),
        ])),
      ]);
}

class _ActionTile extends StatelessWidget {
  final IconData icon; final String label; final VoidCallback onTap; final Color? color; final Widget? trailing;
  const _ActionTile({required this.icon, required this.label, required this.onTap, this.color, this.trailing});

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap, borderRadius: BorderRadius.circular(18),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
          child: Row(children: [
            Icon(icon, color: color ?? AppColors.textSecondary, size: 20), const SizedBox(width: 14),
            Expanded(child: Text(label, style: TextStyle(fontSize: 15, color: color ?? AppColors.textPrimary))),
            trailing ?? const Icon(Icons.chevron_right_rounded, color: AppColors.textHint, size: 20),
          ]),
        ),
      );
}
