// lib/screens/performance_screen.dart
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../core/api_client.dart';
import '../core/constants.dart';
import '../core/theme.dart';
import '../widgets/common_widgets.dart';

// ─────────────────────────────────────────────────────────
// PROVIDER
// ─────────────────────────────────────────────────────────
final performanceProvider =
    FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final client = ref.read(apiClientProvider);
  final response = await client.dio
      .get(AppConstants.performanceSummaryEndpoint);
  return response.data as Map<String, dynamic>;
});

// ─────────────────────────────────────────────────────────
// SCREEN
// ─────────────────────────────────────────────────────────
class PerformanceScreen extends ConsumerStatefulWidget {
  const PerformanceScreen({super.key});

  @override
  ConsumerState<PerformanceScreen> createState() => _PerformanceScreenState();
}

class _PerformanceScreenState extends ConsumerState<PerformanceScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final perfAsync = ref.watch(performanceProvider);

    return Scaffold(
      body: Container(
        decoration:
            const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.arrow_back_ios_new_rounded,
                          color: AppColors.textPrimary, size: 20),
                    ),
                    const Expanded(
                      child: Text(
                        'My Performance',
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () =>
                          ref.refresh(performanceProvider),
                      icon: const Icon(Icons.refresh_rounded,
                          color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
              // Tabs
              TabBar(
                controller: _tabCtrl,
                indicatorColor: AppColors.primaryLight,
                labelColor: AppColors.primaryLight,
                unselectedLabelColor: AppColors.textHint,
                labelStyle: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600),
                dividerColor: AppColors.divider,
                tabs: const [
                  Tab(text: 'Overview'),
                  Tab(text: 'Daily'),
                  Tab(text: 'Dispositions'),
                ],
              ),
              // Content
              Expanded(
                child: perfAsync.when(
                  loading: () => const ShimmerList(count: 4),
                  error: (e, _) => EmptyState(
                    icon: Icons.wifi_off_rounded,
                    title: 'Failed to load performance',
                    subtitle: e.toString(),
                    actionLabel: 'Retry',
                    onAction: () => ref.refresh(performanceProvider),
                  ),
                  data: (data) => TabBarView(
                    controller: _tabCtrl,
                    children: [
                      _buildOverviewTab(data),
                      _buildDailyTab(data),
                      _buildDispositionsTab(data),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────
  // OVERVIEW TAB
  // ─────────────────────────────────────────────────────
  Widget _buildOverviewTab(Map<String, dynamic> data) {
    final totalCalls = data['total_calls'] ?? 0;
    final totalLeads = data['total_leads'] ?? 0;
    final totalConversions = data['total_conversions'] ?? 0;
    final conversionRate =
        (data['conversion_rate'] ?? 0.0).toDouble();
    final avgCallsPerDay =
        (data['avg_calls_per_day'] ?? 0.0).toDouble();
    final period = data['period'] ?? 'Last 30 days';
    final startDate = data['start_date'] ?? '';
    final endDate = data['end_date'] ?? '';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Period info
          Container(
            padding: const EdgeInsets.symmetric(
                horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                const Icon(Icons.date_range_rounded,
                    color: Colors.white70, size: 16),
                const SizedBox(width: 8),
                Text(
                  '$period  ·  $startDate → $endDate',
                  style: const TextStyle(
                      color: Colors.white, fontSize: 13),
                ),
              ],
            ),
          ).animate().slideY(begin: -0.1, duration: 400.ms).fade(),
          const SizedBox(height: 20),

          // Big metrics grid
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            mainAxisSpacing: 14,
            crossAxisSpacing: 14,
            childAspectRatio: 1.2,
            children: [
              MetricCard(
                label: 'Total Calls',
                value: '$totalCalls',
                icon: Icons.phone_rounded,
                color: AppColors.primary,
                subtitle: 'All Time',
              ),
              MetricCard(
                label: 'Total Leads',
                value: '$totalLeads',
                icon: Icons.people_alt_rounded,
                color: AppColors.secondary,
                subtitle: 'Assigned',
              ),
              MetricCard(
                label: 'Conversions',
                value: '$totalConversions',
                icon: Icons.check_circle_rounded,
                color: AppColors.success,
                subtitle: 'Closed',
              ),
              MetricCard(
                label: 'Conv. Rate',
                value: '${conversionRate.toStringAsFixed(1)}%',
                icon: Icons.trending_up_rounded,
                color: AppColors.accent,
                subtitle: 'Efficiency',
              ),
            ],
          ).animate().slideY(begin: 0.2, duration: 400.ms, delay: 100.ms).fade(),
          const SizedBox(height: 20),

          // Avg calls per day
          GlassCard(
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    gradient: AppColors.cyanGradient,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Icon(Icons.bar_chart_rounded,
                      color: Colors.white, size: 26),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Average Calls / Day',
                          style: TextStyle(
                              fontSize: 13,
                              color: AppColors.textSecondary)),
                      Text(
                        avgCallsPerDay.toStringAsFixed(1),
                        style: const TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.w800,
                          color: AppColors.secondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ).animate().slideY(begin: 0.2, duration: 400.ms, delay: 200.ms).fade(),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────
  // DAILY TAB — bar chart
  // ─────────────────────────────────────────────────────
  Widget _buildDailyTab(Map<String, dynamic> data) {
    final dailyList = (data['daily_performance'] as List? ?? [])
        .cast<Map<String, dynamic>>();

    if (dailyList.isEmpty) {
      return const EmptyState(
          icon: Icons.bar_chart_rounded, title: 'No daily data yet');
    }

    final recent = dailyList.length > 14
        ? dailyList.sublist(dailyList.length - 14)
        : dailyList;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: 'Daily Call Volume (last ${recent.length} days)',
            icon: Icons.bar_chart_rounded,
          ),
          const SizedBox(height: 16),
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: SizedBox(
              height: 220,
              child: BarChart(
                BarChartData(
                  alignment: BarChartAlignment.spaceAround,
                  maxY: recent
                          .map((d) => (d['calls'] as num?)?.toDouble() ?? 0)
                          .reduce((a, b) => a > b ? a : b) +
                      2,
                  barGroups: recent.asMap().entries.map((e) {
                    final calls =
                        (e.value['calls'] as num?)?.toDouble() ?? 0;
                    return BarChartGroupData(
                      x: e.key,
                      barRods: [
                        BarChartRodData(
                          toY: calls,
                          gradient: AppColors.primaryGradient,
                          width: 14,
                          borderRadius: const BorderRadius.vertical(
                              top: Radius.circular(6)),
                        ),
                      ],
                    );
                  }).toList(),
                  titlesData: FlTitlesData(
                    leftTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false)),
                    topTitles: const AxisTitles(
                        sideTitles: SideTitles(showTitles: false)),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (val, meta) {
                          final idx = val.toInt();
                          if (idx >= recent.length) {
                            return const SizedBox.shrink();
                          }
                          final dateStr =
                              recent[idx]['date'] as String? ?? '';
                          String label = '';
                          try {
                            final dt = DateTime.parse(dateStr);
                            label = DateFormat('d/M').format(dt);
                          } catch (_) {}
                          return Text(
                            label,
                            style: const TextStyle(
                                color: AppColors.textHint,
                                fontSize: 9),
                          );
                        },
                        reservedSize: 22,
                      ),
                    ),
                  ),
                  gridData: FlGridData(
                    show: true,
                    getDrawingHorizontalLine: (_) => FlLine(
                      color: AppColors.divider,
                      strokeWidth: 1,
                    ),
                    drawVerticalLine: false,
                  ),
                  borderData: FlBorderData(show: false),
                ),
              ),
            ),
          ).animate().slideY(begin: 0.2, duration: 500.ms).fade(),
          const SizedBox(height: 20),

          // Daily table
          SectionHeader(
              title: 'Day-by-Day Breakdown',
              icon: Icons.table_chart_rounded),
          const SizedBox(height: 12),
          ...recent.reversed.take(10).map(
                (d) => _DailyRow(data: d),
              ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────
  // DISPOSITIONS TAB — pie chart
  // ─────────────────────────────────────────────────────
  Widget _buildDispositionsTab(Map<String, dynamic> data) {
    final breakdown = (data['disposition_breakdown'] as List? ?? [])
        .cast<Map<String, dynamic>>();

    if (breakdown.isEmpty) {
      return const EmptyState(
          icon: Icons.donut_large_rounded,
          title: 'No disposition data yet');
    }

    final total = breakdown
        .fold<int>(0, (sum, d) => sum + ((d['count'] as num?)?.toInt() ?? 0));

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
              title: 'Disposition Breakdown',
              icon: Icons.donut_large_rounded),
          const SizedBox(height: 16),
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                SizedBox(
                  height: 200,
                  child: PieChart(
                    PieChartData(
                      sections: breakdown.map((d) {
                        final disp = d['disposition'] as String? ?? '';
                        final count =
                            (d['count'] as num?)?.toDouble() ?? 0;
                        return PieChartSectionData(
                          value: count,
                          color: _dispositionColor(disp),
                          radius: 65,
                          showTitle: false,
                        );
                      }).toList(),
                      centerSpaceRadius: 40,
                      sectionsSpace: 3,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  children: breakdown.map((d) {
                    final disp = d['disposition'] as String? ?? '';
                    final count =
                        (d['count'] as num?)?.toInt() ?? 0;
                    final pct =
                        total > 0 ? (count / total * 100).toStringAsFixed(1) : '0';
                    final color = _dispositionColor(disp);
                    return Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                            width: 10,
                            height: 10,
                            decoration: BoxDecoration(
                                color: color,
                                shape: BoxShape.circle)),
                        const SizedBox(width: 6),
                        Text(
                          '${_dispositionLabel(disp)}: $count ($pct%)',
                          style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textSecondary),
                        ),
                      ],
                    );
                  }).toList(),
                ),
              ],
            ),
          ).animate().slideY(begin: 0.2, duration: 500.ms).fade(),
          const SizedBox(height: 20),

          // Disposition list
          ...breakdown.map(
            (d) => _DispositionRow(
              data: d,
              total: total,
              color: _dispositionColor(d['disposition'] as String? ?? ''),
            ),
          ),
        ],
      ),
    );
  }

  Color _dispositionColor(String disp) {
    switch (disp) {
      case 'interested': return AppColors.success;
      case 'not_interested': return AppColors.error;
      case 'callback': return AppColors.warning;
      case 'not_reachable': return AppColors.textHint;
      case 'busy': return AppColors.secondary;
      case 'wrong_number': return AppColors.textSecondary;
      case 'voicemail': return AppColors.accent;
      case 'follow_up': return AppColors.primary;
      default: return AppColors.textHint;
    }
  }

  String _dispositionLabel(String disp) {
    switch (disp) {
      case 'interested': return 'Interested';
      case 'not_interested': return 'Not Interested';
      case 'callback': return 'Callback';
      case 'not_reachable': return 'Not Reachable';
      case 'busy': return 'Busy';
      case 'wrong_number': return 'Wrong Number';
      case 'voicemail': return 'Voicemail';
      case 'follow_up': return 'Follow-up';
      default: return disp;
    }
  }
}

// ─────────────────────────────────────────────────────────
// SUB-WIDGETS
// ─────────────────────────────────────────────────────────
class _DailyRow extends StatelessWidget {
  final Map<String, dynamic> data;
  const _DailyRow({required this.data});

  @override
  Widget build(BuildContext context) {
    String dateLabel = data['date'] ?? '';
    try {
      final dt = DateTime.parse(dateLabel);
      dateLabel = DateFormat('EEE, MMM d').format(dt);
    } catch (_) {}

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.divider),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(dateLabel,
                style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textPrimary)),
          ),
          _DataPill(
              label: '${data['calls'] ?? 0}',
              icon: Icons.phone_rounded,
              color: AppColors.primary),
          const SizedBox(width: 8),
          _DataPill(
              label: '${data['conversions'] ?? 0}',
              icon: Icons.check_rounded,
              color: AppColors.success),
        ],
      ),
    );
  }
}

class _DataPill extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  const _DataPill(
      {required this.label, required this.icon, required this.color});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          children: [
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 4),
            Text(label,
                style: TextStyle(
                    fontSize: 12,
                    color: color,
                    fontWeight: FontWeight.w600)),
          ],
        ),
      );
}

class _DispositionRow extends StatelessWidget {
  final Map<String, dynamic> data;
  final int total;
  final Color color;
  const _DispositionRow(
      {required this.data, required this.total, required this.color});

  @override
  Widget build(BuildContext context) {
    final disp = data['disposition'] as String? ?? '';
    final count = (data['count'] as num?)?.toInt() ?? 0;
    final pct = total > 0 ? count / total : 0.0;

    String label = disp
        .split('_')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label,
                  style: TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                      color: color)),
              Text(
                '$count calls  ·  ${(pct * 100).toStringAsFixed(1)}%',
                style: const TextStyle(
                    fontSize: 12, color: AppColors.textSecondary),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: pct,
              backgroundColor: AppColors.divider,
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }
}
