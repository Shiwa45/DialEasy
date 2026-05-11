// lib/screens/leads_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/call_service.dart';
import '../services/lead_service.dart';
import '../widgets/lead_search_delegate.dart';
import '../widgets/lead_status_sheet.dart';
import '../widgets/whatsapp_bottom_sheet.dart';
import 'lead_detail_screen.dart';

class LeadsScreen extends ConsumerStatefulWidget {
  const LeadsScreen({super.key});

  @override
  ConsumerState<LeadsScreen> createState() => _LeadsScreenState();
}

class _LeadsScreenState extends ConsumerState<LeadsScreen>
    with SingleTickerProviderStateMixin {
  final _searchCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  late TabController _tabCtrl;
  bool _showSearch = false;

  static const _statusFilters = [
    {'label': 'All', 'value': null},
    {'label': 'New', 'value': 'new'},
    {'label': 'Interested', 'value': 'interested'},
    {'label': 'Callback', 'value': 'callback'},
    {'label': 'Contacted', 'value': 'contacted'},
    {'label': 'Converted', 'value': 'converted'},
    {'label': 'Not Interested', 'value': 'not_interested'},
  ];

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: _statusFilters.length, vsync: this);
    _scrollCtrl.addListener(_onScroll);
    _tabCtrl.addListener(() {
      if (!_tabCtrl.indexIsChanging) return;
      final val = _statusFilters[_tabCtrl.index]['value'] as String?;
      ref.read(leadsProvider.notifier).filterByStatus(val);
    });
  }

  void _onScroll() {
    if (_scrollCtrl.position.pixels >=
        _scrollCtrl.position.maxScrollExtent - 200) {
      ref.read(leadsProvider.notifier).loadLeads();
    }
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _scrollCtrl.dispose();
    _tabCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(leadsProvider);
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(
            children: [
              _buildHeader(state),
              _buildFilterTabs(),
              const SizedBox(height: 4),
              Expanded(child: _buildList(state)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(LeadsState state) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: AnimatedCrossFade(
        duration: const Duration(milliseconds: 250),
        crossFadeState:
            _showSearch ? CrossFadeState.showSecond : CrossFadeState.showFirst,
        firstChild: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Leads',
                      style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textPrimary)),
                  Text('${state.totalCount} assigned',
                      style: const TextStyle(
                          fontSize: 13, color: AppColors.textSecondary)),
                ],
              ),
            ),
            IconButton(
              onPressed: () async {
                final lead = await showSearch<Lead?>(
                  context: context,
                  delegate: LeadSearchDelegate(ref),
                );
                if (lead != null && context.mounted) {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                        builder: (_) => LeadDetailScreen(lead: lead)),
                  ).then((_) =>
                      ref.read(leadsProvider.notifier).loadLeads(refresh: true));
                }
              },
              icon: const Icon(Icons.search_rounded,
                  color: AppColors.textSecondary),
            ),
            IconButton(
              onPressed: () =>
                  ref.read(leadsProvider.notifier).loadLeads(refresh: true),
              icon: const Icon(Icons.refresh_rounded,
                  color: AppColors.textSecondary),
            ),
          ],
        ),
        secondChild: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _searchCtrl,
                autofocus: true,
                style: const TextStyle(color: AppColors.textPrimary),
                onChanged: (v) => ref.read(leadsProvider.notifier).search(v),
                decoration: const InputDecoration(
                  hintText: 'Search name, phone, company...',
                  prefixIcon:
                      Icon(Icons.search_rounded, color: AppColors.textHint),
                  contentPadding: EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () {
                setState(() => _showSearch = false);
                _searchCtrl.clear();
                ref.read(leadsProvider.notifier).search('');
              },
              child: const Text('Cancel',
                  style: TextStyle(color: AppColors.primaryLight, fontSize: 14)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterTabs() {
    return SizedBox(
      height: 38,
      child: TabBar(
        controller: _tabCtrl,
        isScrollable: true,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        indicatorSize: TabBarIndicatorSize.label,
        indicator: BoxDecoration(
          gradient: AppColors.primaryGradient,
          borderRadius: BorderRadius.circular(20),
        ),
        labelColor: Colors.white,
        unselectedLabelColor: AppColors.textHint,
        labelStyle:
            const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 12),
        dividerColor: Colors.transparent,
        tabAlignment: TabAlignment.start,
        tabs: _statusFilters
            .map((f) => Tab(text: f['label'] as String))
            .toList(),
      ),
    );
  }

  Widget _buildList(LeadsState state) {
    if (state.isLoading && state.leads.isEmpty) {
      return const Center(
          child:
              CircularProgressIndicator(color: AppColors.primaryLight));
    }
    if (state.error != null && state.leads.isEmpty) {
      return _ErrorState(
          onRetry: () =>
              ref.read(leadsProvider.notifier).loadLeads(refresh: true));
    }
    if (state.leads.isEmpty) {
      return _EmptyState(
          hasFilter: state.statusFilter != null ||
              state.searchQuery.isNotEmpty);
    }
    return RefreshIndicator(
      onRefresh: () =>
          ref.read(leadsProvider.notifier).loadLeads(refresh: true),
      color: AppColors.primaryLight,
      backgroundColor: AppColors.backgroundCard,
      child: ListView.builder(
        controller: _scrollCtrl,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        itemCount: state.leads.length + (state.isLoading ? 1 : 0),
        itemBuilder: (_, i) {
          if (i == state.leads.length) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(
                  child: CircularProgressIndicator(
                      color: AppColors.primaryLight, strokeWidth: 2)),
            );
          }
          return _LeadTile(
            key: ValueKey(state.leads[i].id),
            lead: state.leads[i],
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                  builder: (_) =>
                      LeadDetailScreen(lead: state.leads[i])),
            ).then((_) =>
                ref.read(leadsProvider.notifier).loadLeads(refresh: true)),
          )
              .animate(
                  delay: Duration(milliseconds: (i % 10) * 40))
              .slideX(begin: 0.1, duration: 300.ms)
              .fade();
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// LEAD TILE
// ─────────────────────────────────────────────────────────
class _LeadTile extends ConsumerWidget {
  final Lead lead;
  final VoidCallback onTap;
  const _LeadTile({super.key, required this.lead, required this.onTap});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final statusColor = AppColors.statusColor(lead.status);

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Slidable(
        key: ValueKey(lead.id),
        startActionPane: ActionPane(
          motion: const DrawerMotion(),
          extentRatio: 0.26,
          children: [
            SlidableAction(
              onPressed: (_) => showModalBottomSheet(
                context: context,
                isScrollControlled: true,
                backgroundColor: Colors.transparent,
                builder: (_) => LeadStatusSheet(lead: lead),
              ),
              backgroundColor: AppColors.primaryLight,
              foregroundColor: Colors.white,
              icon: Icons.label_rounded,
              label: 'Status',
              borderRadius: BorderRadius.circular(14),
            ),
          ],
        ),
        endActionPane: ActionPane(
          motion: const DrawerMotion(),
          extentRatio: 0.48,
          children: [
            SlidableAction(
              onPressed: (_) =>
                  ref.read(callStateProvider.notifier).call(lead.phone),
              backgroundColor: AppColors.success,
              foregroundColor: Colors.white,
              icon: Icons.phone_rounded,
              label: 'Call',
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(14),
                bottomLeft: Radius.circular(14),
              ),
            ),
            SlidableAction(
              onPressed: (_) => showModalBottomSheet(
                context: context,
                isScrollControlled: true,
                backgroundColor: Colors.transparent,
                builder: (_) => WhatsAppBottomSheet(lead: lead),
              ),
              backgroundColor: const Color(0xFF25D366),
              foregroundColor: Colors.white,
              icon: Icons.chat_rounded,
              label: 'WhatsApp',
              borderRadius: const BorderRadius.only(
                topRight: Radius.circular(14),
                bottomRight: Radius.circular(14),
              ),
            ),
          ],
        ),
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.backgroundCard,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.divider),
            ),
            child: Row(
              children: [
                // Avatar
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(colors: [
                      statusColor.withOpacity(0.3),
                      statusColor.withOpacity(0.1)
                    ]),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    lead.name.isNotEmpty
                        ? lead.name[0].toUpperCase()
                        : '?',
                    style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: statusColor),
                  ),
                ),
                const SizedBox(width: 14),
                // Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              lead.name,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 15,
                                  color: AppColors.textPrimary),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          _StatusBadge(
                              status: lead.status,
                              label: lead.statusDisplay),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.phone_rounded,
                              size: 13, color: AppColors.textHint),
                          const SizedBox(width: 4),
                          Text(lead.phone,
                              style: const TextStyle(
                                  fontSize: 13,
                                  color: AppColors.textSecondary)),
                          if (lead.company != null &&
                              lead.company!.isNotEmpty) ...[
                            const SizedBox(width: 6),
                            const Text('·',
                                style:
                                    TextStyle(color: AppColors.textHint)),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(lead.company!,
                                  style: const TextStyle(
                                      fontSize: 12,
                                      color: AppColors.textHint),
                                  overflow: TextOverflow.ellipsis),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          _InfoChip(
                              icon: Icons.phone_callback_rounded,
                              label: '${lead.callCount} calls'),
                          if (lead.followUpCount > 0) ...[
                            const SizedBox(width: 6),
                            _InfoChip(
                                icon: Icons.event_note_rounded,
                                label: '${lead.followUpCount} follow-ups',
                                color: AppColors.warning),
                          ],
                          const Spacer(),
                          // WhatsApp quick button
                          GestureDetector(
                            onTap: () => showModalBottomSheet(
                              context: context,
                              isScrollControlled: true,
                              backgroundColor: Colors.transparent,
                              builder: (_) =>
                                  WhatsAppBottomSheet(lead: lead),
                            ),
                            child: Container(
                              padding: const EdgeInsets.all(6),
                              decoration: BoxDecoration(
                                color: const Color(0xFF25D366)
                                    .withOpacity(0.12),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Icon(Icons.chat_rounded,
                                  color: Color(0xFF25D366), size: 16),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────
// SHARED SMALL WIDGETS
// ─────────────────────────────────────────────────────────
class _StatusBadge extends StatelessWidget {
  final String status, label;
  const _StatusBadge({required this.status, required this.label});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.statusColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
          color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
      child: Text(label,
          style: TextStyle(
              fontSize: 10, fontWeight: FontWeight.w600, color: color)),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  const _InfoChip(
      {required this.icon,
      required this.label,
      this.color = AppColors.textHint});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 11, color: color)),
        ],
      );
}

class _EmptyState extends StatelessWidget {
  final bool hasFilter;
  const _EmptyState({required this.hasFilter});

  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
                hasFilter
                    ? Icons.filter_list_off_rounded
                    : Icons.people_outline_rounded,
                color: AppColors.textHint,
                size: 60),
            const SizedBox(height: 16),
            Text(
              hasFilter
                  ? 'No leads match this filter'
                  : 'No leads assigned yet',
              style: const TextStyle(
                  color: AppColors.textSecondary, fontSize: 16),
            ),
          ],
        ),
      );
}

class _ErrorState extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorState({required this.onRetry});

  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off_rounded,
                color: AppColors.textHint, size: 60),
            const SizedBox(height: 16),
            const Text('Failed to load leads',
                style:
                    TextStyle(color: AppColors.textSecondary, fontSize: 16)),
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
