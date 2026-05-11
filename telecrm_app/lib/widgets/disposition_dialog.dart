// lib/widgets/disposition_dialog.dart
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../core/theme.dart';
import '../models/models.dart';

class DispositionDialog extends StatefulWidget {
  final Lead lead;
  final Duration? callDuration;

  const DispositionDialog({super.key, required this.lead, this.callDuration});

  @override
  State<DispositionDialog> createState() => _DispositionDialogState();
}

class _DispositionDialogState extends State<DispositionDialog> {
  String? _disposition;
  String? _leadStatus;
  final _remarksCtrl = TextEditingController();
  bool _scheduleFollowUp = false;
  DateTime _followUpDate = DateTime.now().add(const Duration(days: 1));
  TimeOfDay _followUpTime = const TimeOfDay(hour: 10, minute: 0);

  static const _dispositions = [
    {'value': 'interested', 'label': 'Interested', 'icon': Icons.thumb_up_rounded, 'color': AppColors.success},
    {'value': 'not_interested', 'label': 'Not Interested', 'icon': Icons.thumb_down_rounded, 'color': AppColors.error},
    {'value': 'callback', 'label': 'Callback Later', 'icon': Icons.schedule_rounded, 'color': AppColors.warning},
    {'value': 'not_reachable', 'label': 'Not Reachable', 'icon': Icons.phone_missed_rounded, 'color': AppColors.textHint},
    {'value': 'busy', 'label': 'Busy', 'icon': Icons.phone_in_talk_rounded, 'color': AppColors.secondary},
    {'value': 'wrong_number', 'label': 'Wrong Number', 'icon': Icons.wrong_location_rounded, 'color': AppColors.textSecondary},
    {'value': 'voicemail', 'label': 'Voicemail', 'icon': Icons.voicemail_rounded, 'color': AppColors.accent},
    {'value': 'follow_up', 'label': 'Follow-up Required', 'icon': Icons.event_note_rounded, 'color': AppColors.primary},
  ];

  static const _statusMap = {
    'interested': 'interested',
    'not_interested': 'not_interested',
    'callback': 'callback',
    'not_reachable': 'not_reachable',
    'wrong_number': 'wrong_number',
    'busy': 'contacted',
    'voicemail': 'contacted',
    'follow_up': 'callback',
  };

  @override
  void dispose() {
    _remarksCtrl.dispose();
    super.dispose();
  }

  void _submit() {
    if (_disposition == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select a disposition'),
          backgroundColor: AppColors.error,
        ),
      );
      return;
    }
    Navigator.of(context).pop({
      'disposition': _disposition,
      'remarks': _remarksCtrl.text.trim(),
      'leadStatus': _leadStatus ?? _statusMap[_disposition!],
      'scheduleFollowUp': _scheduleFollowUp,
      if (_scheduleFollowUp) ...{
        'followUpDate': DateFormat('yyyy-MM-dd').format(_followUpDate),
        'followUpTime':
            '${_followUpTime.hour.toString().padLeft(2, '0')}:${_followUpTime.minute.toString().padLeft(2, '0')}',
      },
    });
  }

  void _stopCalling() {
    Navigator.of(context).pop({'stopCalling': true});
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.92,
      ),
      decoration: const BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Handle
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: AppColors.divider,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          // Header
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    gradient: AppColors.primaryGradient,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.edit_note_rounded, color: Colors.white, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Call Disposition',
                          style: TextStyle(
                              fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                      Text(widget.lead.name,
                          style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
                    ],
                  ),
                ),
                if (widget.callDuration != null)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: AppColors.success.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.timer_rounded, color: AppColors.success, size: 14),
                        const SizedBox(width: 4),
                        Text(
                          '${widget.callDuration!.inMinutes.toString().padLeft(2, '0')}:${(widget.callDuration!.inSeconds % 60).toString().padLeft(2, '0')}',
                          style: const TextStyle(
                              color: AppColors.success, fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          const Divider(height: 24),
          // Scrollable content
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Disposition grid
                  const Text('How did the call go?',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textSecondary)),
                  const SizedBox(height: 12),
                  GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: 10,
                      crossAxisSpacing: 10,
                      childAspectRatio: 2.6,
                    ),
                    itemCount: _dispositions.length,
                    itemBuilder: (_, i) {
                      final d = _dispositions[i];
                      final isSelected = _disposition == d['value'];
                      final color = d['color'] as Color;
                      return GestureDetector(
                        onTap: () => setState(() => _disposition = d['value'] as String),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: isSelected ? color.withOpacity(0.2) : AppColors.backgroundElevated,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isSelected ? color : AppColors.divider,
                              width: isSelected ? 1.5 : 1,
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(d['icon'] as IconData,
                                  color: isSelected ? color : AppColors.textHint, size: 18),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  d['label'] as String,
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                                    color: isSelected ? color : AppColors.textSecondary,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 20),
                  // Remarks
                  const Text('Remarks (optional)',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textSecondary)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _remarksCtrl,
                    maxLines: 3,
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
                    decoration: InputDecoration(
                      hintText: 'Add notes about this call...',
                      prefixIcon: const Padding(
                        padding: EdgeInsets.only(bottom: 44),
                        child: Icon(Icons.notes_rounded, color: AppColors.textHint, size: 20),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  // Schedule follow-up toggle
                  if (_disposition == 'callback' || _disposition == 'follow_up') ...[
                    GestureDetector(
                      onTap: () => setState(() => _scheduleFollowUp = !_scheduleFollowUp),
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: _scheduleFollowUp
                              ? AppColors.primary.withOpacity(0.15)
                              : AppColors.backgroundElevated,
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: _scheduleFollowUp ? AppColors.primaryLight : AppColors.divider,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.event_available_rounded,
                                color: _scheduleFollowUp ? AppColors.primaryLight : AppColors.textHint),
                            const SizedBox(width: 12),
                            const Expanded(
                              child: Text('Schedule Follow-up',
                                  style: TextStyle(
                                      fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                            ),
                            Switch.adaptive(
                              value: _scheduleFollowUp,
                              onChanged: (v) => setState(() => _scheduleFollowUp = v),
                              activeColor: AppColors.primaryLight,
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (_scheduleFollowUp) ...[
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: _DateTimePicker(
                              icon: Icons.calendar_today_rounded,
                              label: DateFormat('MMM d, yyyy').format(_followUpDate),
                              onTap: () async {
                                final picked = await showDatePicker(
                                  context: context,
                                  initialDate: _followUpDate,
                                  firstDate: DateTime.now(),
                                  lastDate: DateTime.now().add(const Duration(days: 365)),
                                );
                                if (picked != null) setState(() => _followUpDate = picked);
                              },
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _DateTimePicker(
                              icon: Icons.access_time_rounded,
                              label: _followUpTime.format(context),
                              onTap: () async {
                                final picked = await showTimePicker(
                                  context: context,
                                  initialTime: _followUpTime,
                                );
                                if (picked != null) setState(() => _followUpTime = picked);
                              },
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 20),
                  ],
                  // Submit button
                  SizedBox(
                    width: double.infinity,
                    height: 54,
                    child: ElevatedButton.icon(
                      onPressed: _submit,
                      icon: const Icon(Icons.check_rounded, size: 22),
                      label: const Text('Save & Continue',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    height: 54,
                    child: OutlinedButton.icon(
                      onPressed: _stopCalling,
                      icon: const Icon(Icons.stop_rounded, size: 22, color: AppColors.error),
                      label: const Text('Stop Calling',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.error)),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.error,
                        side: const BorderSide(color: AppColors.error),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DateTimePicker extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _DateTimePicker({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          decoration: BoxDecoration(
            color: AppColors.backgroundElevated,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.divider),
          ),
          child: Row(
            children: [
              Icon(icon, color: AppColors.primaryLight, size: 16),
              const SizedBox(width: 8),
              Text(label, style: const TextStyle(fontSize: 13, color: AppColors.textPrimary)),
            ],
          ),
        ),
      );
}
