// lib/screens/lead_detail_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/call_service.dart';
import '../services/lead_service.dart';
import '../widgets/disposition_dialog.dart';
import '../widgets/notes_sheet.dart';
import '../widgets/whatsapp_bottom_sheet.dart';

class LeadDetailScreen extends ConsumerStatefulWidget {
  final Lead lead;
  const LeadDetailScreen({super.key, required this.lead});

  @override
  ConsumerState<LeadDetailScreen> createState() => _LeadDetailScreenState();
}

class _LeadDetailScreenState extends ConsumerState<LeadDetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  late Lead _lead;
  List<CallLog> _callLogs = [];
  bool _loadingLogs = false;

  @override
  void initState() {
    super.initState();
    _lead = widget.lead;
    _tabCtrl = TabController(length: 3, vsync: this);
    _loadCallLogs();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadCallLogs() async {
    setState(() => _loadingLogs = true);
    try {
      final logs = await ref.read(leadServiceProvider).getCallLogs(leadId: _lead.id);
      if (mounted) setState(() { _callLogs = logs; _loadingLogs = false; });
    } catch (_) {
      if (mounted) setState(() => _loadingLogs = false);
    }
  }

  Future<void> _startCall() async {
    await ref.read(callStateProvider.notifier).call(_lead.phone);
    ref.listenManual(callStateProvider, (prev, next) async {
      if (next.status == CallStatus.ended && mounted) {
        await Future.delayed(const Duration(milliseconds: 500));
        if (mounted) _showDisposition(next.duration);
      }
    });
  }

  Future<void> _showDisposition(Duration? dur) async {
    final result = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DispositionDialog(lead: _lead, callDuration: dur),
    );
    if (result == null || !mounted) return;
    try {
      await ref.read(leadServiceProvider).createCallLog(
        _lead.id,
        disposition: result['disposition'],
        remarks: result['remarks'],
        duration: dur,
        leadStatus: result['leadStatus'],
      );
      if (result['scheduleFollowUp'] == true) {
        await ref.read(leadServiceProvider).createFollowUp(
          _lead.id,
          followUpDate: result['followUpDate'],
          followUpTime: result['followUpTime'],
          remarks: result['remarks'],
        );
      }
      ref.read(callStateProvider.notifier).reset();
      final updated = await ref.read(leadServiceProvider).getLead(_lead.id);
      if (mounted) setState(() => _lead = updated);
      await _loadCallLogs();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: AppColors.error),
        );
      }
    }
  }

  Future<void> _scheduleFollowUp() async {
    DateTime date = DateTime.now().add(const Duration(days: 1));
    TimeOfDay time = const TimeOfDay(hour: 10, minute: 0);
    final remarksCtrl = TextEditingController();

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
          child: Container(
            decoration: const BoxDecoration(
              color: AppColors.backgroundCard,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Schedule Follow-up',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                const SizedBox(height: 20),
                Row(children: [
                  Expanded(child: _PickerTile(
                    icon: Icons.calendar_today_rounded,
                    label: DateFormat('MMM d, yyyy').format(date),
                    onTap: () async {
                      final p = await showDatePicker(
                        context: ctx, initialDate: date,
                        firstDate: DateTime.now(), lastDate: DateTime.now().add(const Duration(days: 365)),
                      );
                      if (p != null) setS(() => date = p);
                    },
                  )),
                  const SizedBox(width: 10),
                  Expanded(child: _PickerTile(
                    icon: Icons.access_time_rounded,
                    label: time.format(ctx),
                    onTap: () async {
                      final p = await showTimePicker(context: ctx, initialTime: time);
                      if (p != null) setS(() => time = p);
                    },
                  )),
                ]),
                const SizedBox(height: 14),
                TextField(
                  controller: remarksCtrl,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    hintText: 'Add follow-up notes...',
                    prefixIcon: Icon(Icons.notes_rounded, color: AppColors.textHint),
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity, height: 50,
                  child: ElevatedButton(
                    onPressed: () async {
                      Navigator.pop(ctx);
                      try {
                        await ref.read(leadServiceProvider).createFollowUp(
                          _lead.id,
                          followUpDate: DateFormat('yyyy-MM-dd').format(date),
                          followUpTime: '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}',
                          remarks: remarksCtrl.text.trim(),
                        );
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Follow-up scheduled!'), backgroundColor: AppColors.success),
                          );
                          final updated = await ref.read(leadServiceProvider).getLead(_lead.id);
                          setState(() => _lead = updated);
                        }
                      } catch (e) {
                        if (mounted) ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Error: $e'), backgroundColor: AppColors.error),
                        );
                      }
                    },
                    child: const Text('Schedule'),
                  ),
                ),
                const SizedBox(height: 8),
              ],
            ),
          ),
        ),
      ),
    );
    remarksCtrl.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = AppColors.statusColor(_lead.status);
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: SafeArea(
          child: Column(children: [
            _buildAppBar(),
            _buildHeroCard(statusColor),
            _buildTabBar(),
            Expanded(child: _buildTabViews()),
          ]),
        ),
      ),
      bottomNavigationBar: _buildBottomActions(),
    );
  }

  Widget _buildAppBar() => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(children: [
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back_ios_new_rounded, color: AppColors.textPrimary, size: 20),
          ),
          const Expanded(child: Text('Lead Details',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: AppColors.textPrimary))),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert_rounded, color: AppColors.textSecondary),
            color: AppColors.backgroundElevated,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            onSelected: (v) async {
              if (v == 'whatsapp') {
                showModalBottomSheet(context: context, isScrollControlled: true,
                    backgroundColor: Colors.transparent, builder: (_) => WhatsAppBottomSheet(lead: _lead));
              } else if (v == 'edit_notes') {
                final updated = await showModalBottomSheet<Lead>(
                  context: context,
                  isScrollControlled: true,
                  backgroundColor: Colors.transparent,
                  builder: (_) => NotesSheet(lead: _lead),
                );
                if (updated != null && mounted) setState(() => _lead = updated);
              } else if (v == 'copy_phone') {
                await Clipboard.setData(ClipboardData(text: _lead.phone));
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Phone copied'), backgroundColor: AppColors.success),
                );
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'whatsapp', child: Row(children: [
                Icon(Icons.chat_rounded, color: Color(0xFF25D366), size: 18),
                SizedBox(width: 10), Text('Send WhatsApp', style: TextStyle(color: AppColors.textPrimary)),
              ])),
              const PopupMenuItem(value: 'edit_notes', child: Row(children: [
                Icon(Icons.notes_rounded, color: AppColors.primaryLight, size: 18),
                SizedBox(width: 10), Text('Edit Notes', style: TextStyle(color: AppColors.textPrimary)),
              ])),
              const PopupMenuItem(value: 'copy_phone', child: Row(children: [
                Icon(Icons.copy_rounded, color: AppColors.textSecondary, size: 18),
                SizedBox(width: 10), Text('Copy Phone', style: TextStyle(color: AppColors.textPrimary)),
              ])),
            ],
          ),
        ]),
      );

  Widget _buildHeroCard(Color statusColor) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [statusColor.withOpacity(0.2), statusColor.withOpacity(0.05)]),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: statusColor.withOpacity(0.3)),
          ),
          child: Row(children: [
            Container(
              width: 60, height: 60,
              decoration: BoxDecoration(color: statusColor.withOpacity(0.25), borderRadius: BorderRadius.circular(18)),
              alignment: Alignment.center,
              child: Text(
                _lead.name.isNotEmpty ? _lead.name[0].toUpperCase() : '?',
                style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: statusColor),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_lead.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
              const SizedBox(height: 4),
              Text(_lead.phone, style: const TextStyle(fontSize: 14, color: AppColors.textSecondary)),
              if (_lead.company != null)
                Text(_lead.company!, style: const TextStyle(fontSize: 13, color: AppColors.textHint)),
            ])),
            Column(children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(color: statusColor.withOpacity(0.2), borderRadius: BorderRadius.circular(10)),
                child: Text(_lead.statusDisplay, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: statusColor)),
              ),
              const SizedBox(height: 6),
              Text('${_lead.callCount} calls', style: const TextStyle(fontSize: 11, color: AppColors.textHint)),
            ]),
          ]),
        ).animate().slideY(begin: 0.1, duration: 400.ms).fade(),
      );

  Widget _buildTabBar() => Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: TabBar(
          controller: _tabCtrl,
          indicatorColor: AppColors.primaryLight,
          labelColor: AppColors.primaryLight,
          unselectedLabelColor: AppColors.textHint,
          labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          dividerColor: AppColors.divider,
          tabs: const [Tab(text: 'Info'), Tab(text: 'Call History'), Tab(text: 'Follow-ups')],
        ),
      );

  Widget _buildTabViews() => TabBarView(
        controller: _tabCtrl,
        children: [_buildInfoTab(), _buildCallHistoryTab(), _buildFollowUpsTab()],
      );

  Widget _buildInfoTab() => SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Column(children: [
          _InfoRow(icon: Icons.email_rounded, label: 'Email', value: _lead.email ?? 'Not provided'),
          _InfoRow(icon: Icons.source_rounded, label: 'Source', value: _lead.source ?? 'Unknown'),
          _InfoRow(icon: Icons.calendar_today_rounded, label: 'Created', value: _formatDate(_lead.createdAt)),
          _InfoRow(icon: Icons.update_rounded, label: 'Last Updated', value: _formatDate(_lead.updatedAt)),
          if (_lead.nextFollowUp != null)
            _InfoRow(icon: Icons.event_note_rounded, label: 'Next Follow-up',
                value: '${_lead.nextFollowUp!['date']} at ${_lead.nextFollowUp!['time']}',
                valueColor: AppColors.warning),
          if (_lead.notes != null && _lead.notes!.isNotEmpty)
            _InfoRow(icon: Icons.notes_rounded, label: 'Notes', value: _lead.notes!, multiline: true),
          const SizedBox(height: 80),
        ]),
      );

  Widget _buildCallHistoryTab() {
    if (_loadingLogs) return const Center(child: CircularProgressIndicator(color: AppColors.primaryLight));
    if (_callLogs.isEmpty) return const Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.phone_missed_rounded, color: AppColors.textHint, size: 50),
        SizedBox(height: 12),
        Text('No calls yet', style: TextStyle(color: AppColors.textSecondary)),
      ]),
    );
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: _callLogs.length,
      itemBuilder: (_, i) => _CallLogTile(log: _callLogs[i]),
    );
  }

  Widget _buildFollowUpsTab() {
    final nfu = _lead.nextFollowUp;
    if (nfu == null) return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.event_available_rounded, color: AppColors.textHint, size: 50),
        const SizedBox(height: 12),
        const Text('No follow-ups scheduled', style: TextStyle(color: AppColors.textSecondary)),
        const SizedBox(height: 20),
        ElevatedButton.icon(onPressed: _scheduleFollowUp, icon: const Icon(Icons.add_rounded), label: const Text('Schedule Follow-up')),
      ]),
    );
    return ListView(padding: const EdgeInsets.symmetric(horizontal: 20), children: [
      Container(
        margin: const EdgeInsets.only(bottom: 10, top: 4),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.backgroundCard, borderRadius: BorderRadius.circular(14), border: Border.all(color: AppColors.warning.withOpacity(0.3)),
        ),
        child: Row(children: [
          const Icon(Icons.event_note_rounded, color: AppColors.warning, size: 20),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${nfu['date']} at ${nfu['time']}',
                style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
            if (nfu['remarks'] != null && (nfu['remarks'] as String).isNotEmpty)
              Text(nfu['remarks'], style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          ])),
        ]),
      ),
      OutlinedButton.icon(
        onPressed: _scheduleFollowUp, icon: const Icon(Icons.add_rounded), label: const Text('Add Another'),
        style: OutlinedButton.styleFrom(foregroundColor: AppColors.primaryLight, side: const BorderSide(color: AppColors.primaryLight)),
      ),
    ]);
  }

  Widget _buildBottomActions() => Container(
        decoration: const BoxDecoration(color: AppColors.backgroundCard, border: Border(top: BorderSide(color: AppColors.divider))),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Row(children: [
              GestureDetector(
                onTap: () => showModalBottomSheet(context: context, isScrollControlled: true,
                    backgroundColor: Colors.transparent, builder: (_) => WhatsAppBottomSheet(lead: _lead)),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF25D366).withOpacity(0.15), borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: const Color(0xFF25D366).withOpacity(0.3)),
                  ),
                  child: const Icon(Icons.chat_rounded, color: Color(0xFF25D366), size: 22),
                ),
              ),
              const SizedBox(width: 10),
              GestureDetector(
                onTap: _scheduleFollowUp,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withOpacity(0.15), borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.warning.withOpacity(0.3)),
                  ),
                  child: const Icon(Icons.event_note_rounded, color: AppColors.warning, size: 22),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient, borderRadius: BorderRadius.circular(14),
                    boxShadow: [BoxShadow(color: AppColors.primary.withOpacity(0.4), blurRadius: 16, offset: const Offset(0, 4))],
                  ),
                  child: ElevatedButton.icon(
                    onPressed: _startCall,
                    icon: const Icon(Icons.phone_rounded, size: 20),
                    label: const Text('Call Now', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent, shadowColor: Colors.transparent,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    ),
                  ),
                ),
              ),
            ]),
          ),
        ),
      );

  String _formatDate(String iso) {
    try {
      return DateFormat('MMM d, yyyy hh:mm a').format(DateTime.parse(iso).toLocal());
    } catch (_) { return iso; }
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label, value;
  final Color? valueColor;
  final bool multiline;
  const _InfoRow({required this.icon, required this.label, required this.value, this.valueColor, this.multiline = false});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(crossAxisAlignment: multiline ? CrossAxisAlignment.start : CrossAxisAlignment.center, children: [
          Container(width: 36, height: 36, decoration: BoxDecoration(color: AppColors.surface, borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: AppColors.textSecondary, size: 18)),
          const SizedBox(width: 14),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textHint)),
            const SizedBox(height: 2),
            Text(value, style: TextStyle(fontSize: 14, color: valueColor ?? AppColors.textPrimary)),
          ])),
        ]),
      );
}

class _CallLogTile extends StatelessWidget {
  final CallLog log;
  const _CallLogTile({required this.log});

  Color get _color {
    switch (log.disposition) {
      case 'interested': return AppColors.success;
      case 'not_interested': return AppColors.error;
      case 'callback': return AppColors.warning;
      default: return AppColors.textHint;
    }
  }

  @override
  Widget build(BuildContext context) {
    String date = '';
    try { date = DateFormat('MMM d, hh:mm a').format(DateTime.parse(log.callDate).toLocal()); } catch (_) {}
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: AppColors.backgroundCard, borderRadius: BorderRadius.circular(14), border: Border.all(color: AppColors.divider)),
      child: Row(children: [
        Container(width: 40, height: 40,
            decoration: BoxDecoration(color: _color.withOpacity(0.15), borderRadius: BorderRadius.circular(12)),
            child: Icon(Icons.phone_rounded, color: _color, size: 18)),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(log.dispositionDisplay, style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: _color)),
          if (log.remarks != null && log.remarks!.isNotEmpty)
            Text(log.remarks!, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary), maxLines: 2, overflow: TextOverflow.ellipsis),
        ])),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(date, style: const TextStyle(fontSize: 11, color: AppColors.textHint)),
          if (log.durationDisplay != null)
            Text(log.durationDisplay!, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
        ]),
      ]),
    );
  }
}

class _PickerTile extends StatelessWidget {
  final IconData icon; final String label; final VoidCallback onTap;
  const _PickerTile({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          decoration: BoxDecoration(color: AppColors.backgroundElevated, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.divider)),
          child: Row(children: [
            Icon(icon, color: AppColors.primaryLight, size: 16),
            const SizedBox(width: 8),
            Flexible(child: Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textPrimary))),
          ]),
        ),
      );
}
