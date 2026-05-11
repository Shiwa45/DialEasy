// lib/screens/dashboard_screen.dart
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../core/app_config_provider.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/auth_service.dart';
import '../services/lead_service.dart';
import '../widgets/agent_target_card.dart';
import '../widgets/lead_search_delegate.dart';
import 'lead_detail_screen.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  @override
  Widget build(BuildContext context) {
    final dashAsync = ref.watch(dashboardProvider);
    final user = ref.watch(authProvider).user;

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: () => ref.refresh(dashboardProvider.future),
            color: AppColors.primaryLight,
            backgroundColor: AppColors.backgroundCard,
            child: CustomScrollView(
              slivers: [
                // Header
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                    child: _buildHeader(user),
                  ),
                ),
                // Content
                dashAsync.when(
                  loading: () => const SliverFillRemaining(child: _DashboardShimmer()),
                  error: (e, _) => SliverFillRemaining(
                    child: _ErrorView(message: e.toString(), onRetry: () => ref.refresh(dashboardProvider.future)),
                  ),
                  data: (dashboard) => _buildDashboardContent(dashboard),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(AppUser? user) {
    final hour = DateTime.now().hour;
    final greeting = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$greeting,',
                style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
              ),
              Text(
                user?.fullName ?? 'Agent',
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        // Global search button
        GestureDetector(
          onTap: () async {
            final lead = await showSearch<Lead?>(
              context: context,
              delegate: LeadSearchDelegate(ref),
            );
            if (lead != null && mounted) {
              Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) => LeadDetailScreen(lead: lead)),
              );
            }
          },
          child: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.backgroundCard,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.divider),
            ),
            child: const Icon(Icons.search_rounded,
                color: AppColors.textSecondary, size: 22),
          ),
        ),
        const SizedBox(width: 10),
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            gradient: AppColors.primaryGradient,
            borderRadius: BorderRadius.circular(14),
          ),
          alignment: Alignment.center,
          child: Text(
            user?.initials ?? 'A',
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
              fontSize: 18,
            ),
          ),
        ),
      ],
    ).animate().slideY(begin: -0.2, duration: 500.ms).fade();
  }

  SliverList _buildDashboardContent(DashboardSummary d) {
    return SliverList(
      delegate: SliverChildListDelegate([
        const SizedBox(height: 24),
        // Today's stats row
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: _buildTodayBanner(d),
        ).animate().slideY(begin: 0.2, duration: 400.ms, delay: 100.ms).fade(),
        const SizedBox(height: 20),
        // Stat cards row
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: _buildStatsGrid(d),
        ).animate().slideY(begin: 0.2, duration: 400.ms, delay: 200.ms).fade(),
        const SizedBox(height: 24),
        // Lead status breakdown
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: _buildStatusChart(d),
        ).animate().slideY(begin: 0.2, duration: 400.ms, delay: 300.ms).fade(),
        const SizedBox(height: 24),
        // Daily target progress
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: _buildTargetCards(d),
        ).animate().slideY(begin: 0.2, duration: 400.ms, delay: 350.ms).fade(),
        const SizedBox(height: 24),
        // Upcoming follow-ups
        if (d.upcomingFollowUps.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: _SectionHeader(title: 'Upcoming Follow-ups', icon: Icons.event_note_rounded),
          ),
          const SizedBox(height: 12),
          ...d.upcomingFollowUps.take(3).map(
                (f) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
                  child: _FollowUpTile(followUp: f),
                ),
              ),
          const SizedBox(height: 20),
        ],
        // Recent calls
        if (d.recentCalls.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: _SectionHeader(title: 'Recent Calls', icon: Icons.history_rounded),
          ),
          const SizedBox(height: 12),
          ...d.recentCalls.take(5).map(
                (c) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
                  child: _RecentCallTile(callLog: c),
                ),
              ),
          const SizedBox(height: 80),
        ],
      ]),
    );
  }

  Widget _buildTodayBanner(DashboardSummary d) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: AppColors.primaryGradient,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.3),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.today_rounded, color: Colors.white70, size: 16),
              const SizedBox(width: 6),
              Text(
                DateFormat('EEEE, MMM d').format(DateTime.now()),
                style: const TextStyle(color: Colors.white70, fontSize: 13),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _TodayStatItem(
                  label: 'Calls Today',
                  value: '${d.todayCalls}',
                  icon: Icons.phone_rounded,
                ),
              ),
              Container(width: 1, height: 40, color: Colors.white24),
              Expanded(
                child: _TodayStatItem(
                  label: 'Follow-ups',
                  value: '${d.todayFollowUps}',
                  icon: Icons.event_note_rounded,
                ),
              ),
              Container(width: 1, height: 40, color: Colors.white24),
              Expanded(
                child: _TodayStatItem(
                  label: 'Overdue',
                  value: '${d.overdueFollowUps}',
                  icon: Icons.warning_amber_rounded,
                  valueColor: d.overdueFollowUps > 0 ? AppColors.warning : Colors.white,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatsGrid(DashboardSummary d) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _SectionHeader(title: 'Lead Overview', icon: Icons.bar_chart_rounded),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _StatCard(label: 'Total Leads', value: '${d.totalLeads}', gradient: AppColors.primaryGradient, icon: Icons.people_alt_rounded)),
            const SizedBox(width: 12),
            Expanded(child: _StatCard(label: 'Converted', value: '${d.convertedLeads}', gradient: AppColors.successGradient, icon: Icons.check_circle_rounded)),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _StatCard(label: 'Interested', value: '${d.newLeads}', gradient: AppColors.accentGradient, icon: Icons.thumb_up_rounded)),
            const SizedBox(width: 12),
            Expanded(
              child: _StatCard(
                label: 'Conv. Rate',
                value: '${d.conversionRate.toStringAsFixed(1)}%',
                gradient: AppColors.cyanGradient,
                icon: Icons.trending_up_rounded,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildTargetCards(DashboardSummary d) {
    final config = ref.watch(appConfigProvider);
    final dailyTarget = config.dailyCallsTarget;
    final monthlyTarget = config.monthlyConversionsTarget;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _SectionHeader(title: 'Today\'s Targets', icon: Icons.flag_rounded),
        const SizedBox(height: 12),
        AgentTargetCard(
          title: 'Calls Today',
          current: d.todayCalls,
          target: dailyTarget,
          icon: Icons.phone_rounded,
          color: AppColors.primary,
        ),
        const SizedBox(height: 10),
        AgentTargetCard(
          title: 'Conversions (Month)',
          current: d.convertedLeads,
          target: monthlyTarget,
          icon: Icons.check_circle_rounded,
          color: AppColors.success,
        ),
      ],
    );
  }

  Widget _buildStatusChart(DashboardSummary d) {
    if (d.leadStatuses.isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: 'Lead Status Breakdown', icon: Icons.donut_large_rounded),
          const SizedBox(height: 20),
          SizedBox(
            height: 180,
            child: Row(
              children: [
                Expanded(
                  child: PieChart(
                    PieChartData(
                      sections: d.leadStatuses.map((s) {
                        final status = s['status'] as String? ?? '';
                        final count = (s['count'] as num?)?.toDouble() ?? 0;
                        return PieChartSectionData(
                          value: count,
                          color: AppColors.statusColor(status),
                          radius: 55,
                          showTitle: false,
                        );
                      }).toList(),
                      centerSpaceRadius: 36,
                      sectionsSpace: 2,
                    ),
                  ),
                ),
                const SizedBox(width: 20),
                Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: d.leadStatuses.take(6).map((s) {
                    final status = s['status'] as String? ?? '';
                    final label = s['label'] as String? ?? status;
                    final count = s['count'] ?? 0;
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          Container(
                            width: 10,
                            height: 10,
                            decoration: BoxDecoration(
                              color: AppColors.statusColor(status),
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '$label: $count',
                            style: TextStyle(
                              fontSize: 12,
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// HELPER WIDGETS
// ─────────────────────────────────────────────────────────
class _TodayStatItem extends StatelessWidget {
  final String label, value;
  final IconData icon;
  final Color? valueColor;
  const _TodayStatItem({required this.label, required this.value, required this.icon, this.valueColor});

  @override
  Widget build(BuildContext context) => Column(
        children: [
          Icon(icon, color: Colors.white70, size: 20),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: valueColor ?? Colors.white,
            ),
          ),
          Text(label, style: const TextStyle(color: Colors.white60, fontSize: 11)),
        ],
      );
}

class _StatCard extends StatelessWidget {
  final String label, value;
  final LinearGradient gradient;
  final IconData icon;
  const _StatCard({required this.label, required this.value, required this.gradient, required this.icon});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(18),
          boxShadow: [
            BoxShadow(
              color: gradient.colors.first.withOpacity(0.3),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: Colors.white70, size: 22),
            const SizedBox(height: 12),
            Text(value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: Colors.white)),
            Text(label, style: const TextStyle(fontSize: 12, color: Colors.white70)),
          ],
        ),
      );
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  const _SectionHeader({required this.title, required this.icon});

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Icon(icon, color: AppColors.primaryLight, size: 18),
          const SizedBox(width: 8),
          Text(title,
              style: const TextStyle(
                  fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
        ],
      );
}

class _FollowUpTile extends StatelessWidget {
  final FollowUp followUp;
  const _FollowUpTile({required this.followUp});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.backgroundCard,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: followUp.isOverdue
                ? AppColors.error.withOpacity(0.4)
                : followUp.isToday
                    ? AppColors.warning.withOpacity(0.4)
                    : AppColors.divider,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: followUp.isOverdue
                    ? AppColors.error.withOpacity(0.15)
                    : AppColors.primary.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.event_note_rounded,
                color: followUp.isOverdue ? AppColors.error : AppColors.primaryLight,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(followUp.leadName,
                      style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                          fontSize: 14)),
                  Text(followUp.formattedDatetime,
                      style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                ],
              ),
            ),
            if (followUp.isOverdue)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.error.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text('Overdue',
                    style: TextStyle(color: AppColors.error, fontSize: 11, fontWeight: FontWeight.w600)),
              )
            else if (followUp.isToday)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.warning.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text('Today',
                    style: TextStyle(color: AppColors.warning, fontSize: 11, fontWeight: FontWeight.w600)),
              ),
          ],
        ),
      );
}

class _RecentCallTile extends StatelessWidget {
  final CallLog callLog;
  const _RecentCallTile({required this.callLog});

  Color get _dispositionColor {
    switch (callLog.disposition) {
      case 'interested': return AppColors.success;
      case 'not_interested': return AppColors.error;
      case 'callback': return AppColors.warning;
      case 'not_reachable': case 'busy': return AppColors.textHint;
      default: return AppColors.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.backgroundCard,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.divider),
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.phone_rounded, color: AppColors.primaryLight, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    callLog.lead['name'] ?? 'Unknown',
                    style: const TextStyle(
                        fontWeight: FontWeight.w600, color: AppColors.textPrimary, fontSize: 14),
                  ),
                  Row(
                    children: [
                      Container(
                        width: 6,
                        height: 6,
                        margin: const EdgeInsets.only(right: 6),
                        decoration: BoxDecoration(
                          color: _dispositionColor,
                          shape: BoxShape.circle,
                        ),
                      ),
                      Text(
                        callLog.dispositionDisplay,
                        style: TextStyle(fontSize: 12, color: _dispositionColor),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (callLog.durationDisplay != null)
                  Text(
                    callLog.durationDisplay!,
                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  ),
              ],
            ),
          ],
        ),
      );
}

class _DashboardShimmer extends StatelessWidget {
  const _DashboardShimmer();

  @override
  Widget build(BuildContext context) => const Center(
        child: CircularProgressIndicator(
          color: AppColors.primaryLight,
          strokeWidth: 2.5,
        ),
      );
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off_rounded, color: AppColors.textHint, size: 60),
            const SizedBox(height: 16),
            const Text('Failed to load dashboard',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 16)),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
}
