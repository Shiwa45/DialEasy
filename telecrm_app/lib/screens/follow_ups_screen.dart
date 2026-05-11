// lib/screens/follow_ups_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/call_service.dart';
import '../services/lead_service.dart';
import '../widgets/whatsapp_bottom_sheet.dart';

class FollowUpsScreen extends ConsumerStatefulWidget {
  const FollowUpsScreen({super.key});
  @override
  ConsumerState<FollowUpsScreen> createState() => _FollowUpsScreenState();
}

class _FollowUpsScreenState extends ConsumerState<FollowUpsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() { _tabCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(followUpsProvider);
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
              child: Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('Follow-ups', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                  if (state.overdue.isNotEmpty)
                    Text('${state.overdue.length} overdue', style: const TextStyle(fontSize: 13, color: AppColors.error)),
                ])),
                IconButton(
                  onPressed: () => ref.read(followUpsProvider.notifier).loadAll(),
                  icon: const Icon(Icons.refresh_rounded, color: AppColors.textSecondary),
                ),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(children: [
                _SummaryChip(label: 'Today', count: state.today.length, color: AppColors.primary, icon: Icons.today_rounded),
                const SizedBox(width: 10),
                _SummaryChip(label: 'Overdue', count: state.overdue.length, color: AppColors.error, icon: Icons.warning_amber_rounded),
                const SizedBox(width: 10),
                _SummaryChip(label: 'Upcoming', count: state.upcoming.length, color: AppColors.success, icon: Icons.upcoming_rounded),
              ]),
            ),
            const SizedBox(height: 12),
            TabBar(
              controller: _tabCtrl,
              indicatorColor: AppColors.primaryLight,
              labelColor: AppColors.primaryLight,
              unselectedLabelColor: AppColors.textHint,
              labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
              dividerColor: AppColors.divider,
              tabs: [
                Tab(text: 'Today (${state.today.length})'),
                Tab(text: 'Overdue (${state.overdue.length})'),
                Tab(text: 'Upcoming (${state.upcoming.length})'),
              ],
            ),
            Expanded(
              child: state.isLoading
                  ? const Center(child: CircularProgressIndicator(color: AppColors.primaryLight))
                  : TabBarView(
                      controller: _tabCtrl,
                      children: [
                        _buildList(state.today, isOverdueTab: false),
                        _buildList(state.overdue, isOverdueTab: true),
                        _buildList(state.upcoming, isOverdueTab: false),
                      ],
                    ),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _buildList(List<FollowUp> items, {required bool isOverdueTab}) {
    if (items.isEmpty) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(isOverdueTab ? Icons.check_circle_rounded : Icons.event_available_rounded,
            color: isOverdueTab ? AppColors.success : AppColors.textHint, size: 60),
        const SizedBox(height: 12),
        Text(isOverdueTab ? 'No overdue follow-ups 🎉' : 'Nothing here',
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 16)),
      ]));
    }
    return RefreshIndicator(
      onRefresh: () => ref.read(followUpsProvider.notifier).loadAll(),
      color: AppColors.primaryLight,
      backgroundColor: AppColors.backgroundCard,
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemCount: items.length,
        itemBuilder: (_, i) => _FollowUpCard(
          followUp: items[i],
          onComplete: () async {
            final ok = await ref.read(followUpsProvider.notifier).complete(items[i].id);
            if (ok && mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Follow-up completed!'), backgroundColor: AppColors.success),
              );
            }
          },
        ).animate(delay: Duration(milliseconds: i * 50)).slideX(begin: 0.1, duration: 300.ms).fade(),
      ),
    );
  }
}

class _SummaryChip extends StatelessWidget {
  final String label; final int count; final Color color; final IconData icon;
  const _SummaryChip({required this.label, required this.count, required this.color, required this.icon});

  @override
  Widget build(BuildContext context) => Expanded(
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 12),
          decoration: BoxDecoration(
            color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(14),
            border: Border.all(color: color.withOpacity(0.25)),
          ),
          child: Row(children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 8),
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('$count', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: color)),
              Text(label, style: TextStyle(fontSize: 10, color: color.withOpacity(0.8))),
            ]),
          ]),
        ),
      );
}

class _FollowUpCard extends ConsumerWidget {
  final FollowUp followUp;
  final VoidCallback onComplete;
  const _FollowUpCard({required this.followUp, required this.onComplete});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOverdue = followUp.isOverdue;
    final isToday = followUp.isToday;
    final color = isOverdue ? AppColors.error : isToday ? AppColors.warning : AppColors.primary;

    final fakeLead = Lead(
      id: followUp.leadId, name: followUp.leadName, phone: followUp.leadPhone,
      status: 'callback', statusDisplay: 'Callback', createdAt: '', updatedAt: '', callCount: 0, followUpCount: 0,
    );

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.backgroundCard, borderRadius: BorderRadius.circular(18),
          border: Border.all(color: color.withOpacity(0.3)),
          boxShadow: [BoxShadow(color: color.withOpacity(0.08), blurRadius: 16, offset: const Offset(0, 4))],
        ),
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
            child: Row(children: [
              Container(
                width: 46, height: 46,
                decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(14)),
                alignment: Alignment.center,
                child: Text(
                  followUp.leadName.isNotEmpty ? followUp.leadName[0].toUpperCase() : '?',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: color),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(followUp.leadName,
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: AppColors.textPrimary),
                      overflow: TextOverflow.ellipsis)),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
                    child: Text(
                      isOverdue ? 'OVERDUE' : isToday ? 'TODAY' : 'UPCOMING',
                      style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: color),
                    ),
                  ),
                ]),
                const SizedBox(height: 3),
                Row(children: [
                  const Icon(Icons.access_time_rounded, size: 13, color: AppColors.textHint),
                  const SizedBox(width: 4),
                  Text(followUp.formattedDatetime, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                ]),
                if (followUp.remarks != null && followUp.remarks!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(followUp.remarks!, style: const TextStyle(fontSize: 12, color: AppColors.textHint),
                        maxLines: 2, overflow: TextOverflow.ellipsis),
                  ),
              ])),
            ]),
          ),
          Container(height: 1, color: AppColors.divider),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(children: [
              _ActionBtn(icon: Icons.phone_rounded, label: 'Call', color: AppColors.success,
                  onTap: () => ref.read(callStateProvider.notifier).call(followUp.leadPhone)),
              const SizedBox(width: 8),
              _ActionBtn(icon: Icons.chat_rounded, label: 'WhatsApp', color: const Color(0xFF25D366),
                  onTap: () => showModalBottomSheet(context: context, isScrollControlled: true,
                      backgroundColor: Colors.transparent, builder: (_) => WhatsAppBottomSheet(lead: fakeLead))),
              const Spacer(),
              ElevatedButton.icon(
                onPressed: onComplete,
                icon: const Icon(Icons.check_rounded, size: 16),
                label: const Text('Done', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: color, padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _ActionBtn extends StatelessWidget {
  final IconData icon; final String label; final Color color; final VoidCallback onTap;
  const _ActionBtn({required this.icon, required this.label, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
          child: Row(children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
          ]),
        ),
      );
}
