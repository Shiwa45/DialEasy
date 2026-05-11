// lib/widgets/lead_status_sheet.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/lead_service.dart';

class LeadStatusSheet extends ConsumerStatefulWidget {
  final Lead lead;
  const LeadStatusSheet({super.key, required this.lead});

  @override
  ConsumerState<LeadStatusSheet> createState() => _LeadStatusSheetState();
}

class _LeadStatusSheetState extends ConsumerState<LeadStatusSheet> {
  late String _selected;
  bool _saving = false;

  static const _statuses = [
    {'value': 'new', 'label': 'New', 'icon': Icons.fiber_new_rounded},
    {'value': 'contacted', 'label': 'Contacted', 'icon': Icons.phone_callback_rounded},
    {'value': 'interested', 'label': 'Interested', 'icon': Icons.thumb_up_rounded},
    {'value': 'not_interested', 'label': 'Not Interested', 'icon': Icons.thumb_down_rounded},
    {'value': 'callback', 'label': 'Callback Later', 'icon': Icons.schedule_rounded},
    {'value': 'wrong_number', 'label': 'Wrong Number', 'icon': Icons.wrong_location_rounded},
    {'value': 'not_reachable', 'label': 'Not Reachable', 'icon': Icons.phone_disabled_rounded},
    {'value': 'converted', 'label': 'Converted ✓', 'icon': Icons.check_circle_rounded},
  ];

  @override
  void initState() {
    super.initState();
    _selected = widget.lead.status;
  }

  Future<void> _save() async {
    if (_selected == widget.lead.status) {
      Navigator.pop(context);
      return;
    }
    setState(() => _saving = true);
    try {
      final updated = await ref.read(leadServiceProvider).updateLead(
            widget.lead.id,
            status: _selected,
          );
      ref.read(leadsProvider.notifier).updateLeadLocally(updated);
      if (mounted) Navigator.pop(context, updated);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Handle
          Container(
            margin: const EdgeInsets.only(top: 12, bottom: 8),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
                color: AppColors.divider,
                borderRadius: BorderRadius.circular(2)),
          ),
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.label_rounded,
                      color: Colors.white, size: 18),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Update Status',
                          style: TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w700,
                              color: AppColors.textPrimary)),
                      Text(widget.lead.name,
                          style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textSecondary)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          // Status grid
          Padding(
            padding: const EdgeInsets.all(16),
            child: GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                childAspectRatio: 2.8,
              ),
              itemCount: _statuses.length,
              itemBuilder: (_, i) {
                final s = _statuses[i];
                final val = s['value'] as String;
                final isSelected = _selected == val;
                final color = AppColors.statusColor(val);
                return GestureDetector(
                  onTap: () => setState(() => _selected = val),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? color.withOpacity(0.2)
                          : AppColors.backgroundElevated,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color:
                            isSelected ? color : AppColors.divider,
                        width: isSelected ? 1.5 : 1,
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(s['icon'] as IconData,
                            color: isSelected
                                ? color
                                : AppColors.textHint,
                            size: 16),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            s['label'] as String,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: isSelected
                                  ? FontWeight.w600
                                  : FontWeight.w400,
                              color: isSelected
                                  ? color
                                  : AppColors.textSecondary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (isSelected)
                          Icon(Icons.check_circle_rounded,
                              color: color, size: 14),
                      ],
                    ),
                  ).animate(delay: Duration(milliseconds: i * 30))
                      .scale(begin: const Offset(0.9, 0.9), duration: 200.ms),
                );
              },
            ),
          ),
          // Save button
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
            child: SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton.icon(
                onPressed: _saving ? null : _save,
                icon: _saving
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.save_rounded, size: 18),
                label: Text(_saving ? 'Saving…' : 'Save Status',
                    style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.w700)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.statusColor(_selected),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
