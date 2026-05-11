// lib/screens/call_history_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../core/api_client.dart';
import '../core/constants.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../widgets/common_widgets.dart';

// ─────────────────────────────────────────────────────────
// PROVIDER
// ─────────────────────────────────────────────────────────
final callHistoryProvider =
    FutureProvider.autoDispose<List<CallLog>>((ref) async {
  final client = ref.read(apiClientProvider);
  final response = await client.dio.get(
    AppConstants.callLogsEndpoint,
    queryParameters: {'page_size': 100},
  );
  final data = response.data;
  final list = data is Map ? (data['results'] ?? []) : data;
  return (list as List).map((e) => CallLog.fromJson(e)).toList();
});

// ─────────────────────────────────────────────────────────
// SCREEN
// ─────────────────────────────────────────────────────────
class CallHistoryScreen extends ConsumerStatefulWidget {
  const CallHistoryScreen({super.key});

  @override
  ConsumerState<CallHistoryScreen> createState() => _CallHistoryScreenState();
}

class _CallHistoryScreenState extends ConsumerState<CallHistoryScreen> {
  String? _filterDisposition;
  final _searchCtrl = TextEditingController();
  String _searchQuery = '';

  static const _dispositions = [
    {'value': null, 'label': 'All'},
    {'value': 'interested', 'label': 'Interested'},
    {'value': 'not_interested', 'label': 'Not Interested'},
    {'value': 'callback', 'label': 'Callback'},
    {'value': 'not_reachable', 'label': 'Not Reachable'},
    {'value': 'busy', 'label': 'Busy'},
    {'value': 'wrong_number', 'label': 'Wrong Number'},
    {'value': 'voicemail', 'label': 'Voicemail'},
    {'value': 'follow_up', 'label': 'Follow-up'},
  ];

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  List<CallLog> _filterLogs(List<CallLog> logs) {
    return logs.where((log) {
      final matchDisp = _filterDisposition == null ||
          log.disposition == _filterDisposition;
      final matchSearch = _searchQuery.isEmpty ||
          (log.lead['name'] as String? ?? '')
              .toLowerCase()
              .contains(_searchQuery.toLowerCase()) ||
          (log.lead['phone'] as String? ?? '').contains(_searchQuery);
      return matchDisp && matchSearch;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final histAsync = ref.watch(callHistoryProvider);

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildSearch(),
              _buildFilterChips(),
              Expanded(
                child: histAsync.when(
                  loading: () => const ShimmerList(count: 8),
                  error: (e, _) => EmptyState(
                    icon: Icons.wifi_off_rounded,
                    title: 'Failed to load call history',
                    actionLabel: 'Retry',
                    onAction: () => ref.refresh(callHistoryProvider),
                  ),
                  data: (logs) {
                    final filtered = _filterLogs(logs);
                    if (filtered.isEmpty) {
                      return const EmptyState(
                        icon: Icons.phone_missed_rounded,
                        title: 'No calls found',
                        subtitle: 'Try adjusting your filter',
                      );
                    }
                    return ListView.builder(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 8),
                      itemCount: filtered.length,
                      itemBuilder: (_, i) => _CallHistoryTile(
                        log: filtered[i],
                      ).animate(delay: Duration(milliseconds: i * 30)).slideX(begin: 0.1, duration: 300.ms).fade(),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() => Padding(
        padding: const EdgeInsets.fromLTRB(8, 12, 20, 4),
        child: Row(
          children: [
            IconButton(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.arrow_back_ios_new_rounded,
                  color: AppColors.textPrimary, size: 20),
            ),
            const Expanded(
              child: Text(
                'Call History',
                style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary),
              ),
            ),
            IconButton(
              onPressed: () => ref.refresh(callHistoryProvider),
              icon: const Icon(Icons.refresh_rounded,
                  color: AppColors.textSecondary),
            ),
          ],
        ),
      );

  Widget _buildSearch() => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        child: TextField(
          controller: _searchCtrl,
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
          onChanged: (v) => setState(() => _searchQuery = v),
          decoration: const InputDecoration(
            hintText: 'Search by name or phone...',
            prefixIcon: Icon(Icons.search_rounded, color: AppColors.textHint, size: 20),
            contentPadding: EdgeInsets.symmetric(vertical: 12),
          ),
        ),
      );

  Widget _buildFilterChips() => SizedBox(
        height: 44,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: _dispositions.length,
          separatorBuilder: (_, __) => const SizedBox(width: 8),
          itemBuilder: (_, i) {
            final d = _dispositions[i];
            final val = d['value'] as String?;
            final isSelected = _filterDisposition == val;
            return GestureDetector(
              onTap: () => setState(() => _filterDisposition = val),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  gradient: isSelected ? AppColors.primaryGradient : null,
                  color: isSelected ? null : AppColors.backgroundCard,
                  borderRadius: BorderRadius.circular(22),
                  border: Border.all(
                      color: isSelected ? Colors.transparent : AppColors.divider),
                ),
                child: Text(
                  d['label'] as String,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: isSelected ? FontWeight.w700 : FontWeight.w400,
                    color: isSelected ? Colors.white : AppColors.textSecondary,
                  ),
                ),
              ),
            );
          },
        ),
      );
}

// ─────────────────────────────────────────────────────────
// CALL LOG TILE
// ─────────────────────────────────────────────────────────
class _CallHistoryTile extends StatelessWidget {
  final CallLog log;
  const _CallHistoryTile({required this.log});

  Color get _color {
    switch (log.disposition) {
      case 'interested': return AppColors.success;
      case 'not_interested': return AppColors.error;
      case 'callback': return AppColors.warning;
      case 'busy': case 'not_reachable': return AppColors.textHint;
      case 'voicemail': return AppColors.accent;
      case 'wrong_number': return AppColors.textSecondary;
      default: return AppColors.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    String dateLabel = '';
    try {
      final dt = DateTime.parse(log.callDate).toLocal();
      dateLabel = DateFormat('MMM d, hh:mm a').format(dt);
    } catch (_) {}

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.divider),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: _color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(Icons.phone_rounded, color: _color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        log.lead['name'] as String? ?? 'Unknown',
                        style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    BadgeChip(label: log.dispositionDisplay, color: _color),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Icon(Icons.phone_rounded,
                        size: 12, color: AppColors.textHint),
                    const SizedBox(width: 4),
                    Text(
                      log.lead['phone'] as String? ?? '',
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textSecondary),
                    ),
                    const SizedBox(width: 10),
                    const Icon(Icons.access_time_rounded,
                        size: 12, color: AppColors.textHint),
                    const SizedBox(width: 4),
                    Text(dateLabel,
                        style: const TextStyle(
                            fontSize: 12, color: AppColors.textHint)),
                  ],
                ),
                if (log.remarks != null && log.remarks!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      log.remarks!,
                      style: const TextStyle(
                          fontSize: 11, color: AppColors.textHint),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
            ),
          ),
          if (log.durationDisplay != null)
            Padding(
              padding: const EdgeInsets.only(left: 8),
              child: CallDurationDisplay(
                duration: Duration(seconds: _parseDuration(log.durationDisplay!)),
                color: AppColors.textSecondary,
              ),
            ),
        ],
      ),
    );
  }

  int _parseDuration(String display) {
    // format: "MM:SS"
    try {
      final parts = display.split(':');
      return int.parse(parts[0]) * 60 + int.parse(parts[1]);
    } catch (_) {
      return 0;
    }
  }
}
