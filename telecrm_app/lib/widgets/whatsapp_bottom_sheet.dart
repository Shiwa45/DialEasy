// lib/widgets/whatsapp_bottom_sheet.dart
import 'package:flutter/material.dart';
import '../core/constants.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/whatsapp_service.dart';

class WhatsAppBottomSheet extends StatefulWidget {
  final Lead lead;
  const WhatsAppBottomSheet({super.key, required this.lead});

  @override
  State<WhatsAppBottomSheet> createState() => _WhatsAppBottomSheetState();
}

class _WhatsAppBottomSheetState extends State<WhatsAppBottomSheet> {
  int _selectedTemplate = 0;
  bool _useCloud = false;
  final _customMsgCtrl = TextEditingController();
  bool _useCustom = false;

  @override
  void dispose() {
    _customMsgCtrl.dispose();
    super.dispose();
  }

  String get _resolvedMessage {
    if (_useCustom && _customMsgCtrl.text.trim().isNotEmpty) {
      return _customMsgCtrl.text.trim();
    }
    return WhatsAppService.applyTemplate(
      AppConstants.whatsappTemplates[_selectedTemplate]['message']!,
      name: widget.lead.name,
      company: widget.lead.company,
    );
  }

  Future<void> _send() async {
    final msg = _resolvedMessage;
    bool success;
    if (_useCloud) {
      success = await WhatsAppService.sendViaCloudWhatsApp(
        phone: widget.lead.phone,
        message: msg,
        templateName: AppConstants.whatsappTemplates[_selectedTemplate]['name'],
      );
    } else {
      success = await WhatsAppService.sendViaDevice(
        phone: widget.lead.phone,
        message: msg,
      );
    }
    if (mounted) {
      if (success) {
        Navigator.pop(context);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Could not open WhatsApp'),
              backgroundColor: AppColors.error),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints:
          BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.90),
      decoration: const BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
                color: AppColors.divider,
                borderRadius: BorderRadius.circular(2)),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF25D366).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.chat_rounded,
                      color: Color(0xFF25D366), size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Send WhatsApp',
                          style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              color: AppColors.textPrimary)),
                      Text('to ${widget.lead.name} · ${widget.lead.phone}',
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.textSecondary)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 20),
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Channel toggle
                  const Text('Send via',
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textSecondary)),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                          child: _ChannelButton(
                              label: 'Device WhatsApp',
                              icon: Icons.phone_android_rounded,
                              isSelected: !_useCloud,
                              onTap: () => setState(() => _useCloud = false))),
                      const SizedBox(width: 10),
                      Expanded(
                          child: _ChannelButton(
                              label: 'Cloud WhatsApp',
                              icon: Icons.cloud_rounded,
                              isSelected: _useCloud,
                              onTap: () => setState(() => _useCloud = true))),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Message Template',
                          style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textSecondary)),
                      GestureDetector(
                        onTap: () =>
                            setState(() => _useCustom = !_useCustom),
                        child: Text(
                          _useCustom ? 'Use Template' : 'Custom Message',
                          style: const TextStyle(
                              color: AppColors.primaryLight,
                              fontSize: 12,
                              fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  if (!_useCustom) ...[
                    SizedBox(
                      height: 44,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: AppConstants.whatsappTemplates.length,
                        separatorBuilder: (_, __) => const SizedBox(width: 8),
                        itemBuilder: (_, i) {
                          final t = AppConstants.whatsappTemplates[i];
                          final sel = _selectedTemplate == i;
                          return GestureDetector(
                            onTap: () =>
                                setState(() => _selectedTemplate = i),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 16, vertical: 10),
                              decoration: BoxDecoration(
                                gradient: sel
                                    ? AppColors.primaryGradient
                                    : null,
                                color: sel
                                    ? null
                                    : AppColors.backgroundElevated,
                                borderRadius: BorderRadius.circular(22),
                                border: Border.all(
                                    color: sel
                                        ? Colors.transparent
                                        : AppColors.divider),
                              ),
                              child: Text(t['name']!,
                                  style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: sel
                                          ? FontWeight.w600
                                          : FontWeight.w400,
                                      color: sel
                                          ? Colors.white
                                          : AppColors.textSecondary)),
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 14),
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: const Color(0xFF25D366).withOpacity(0.08),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                            color: const Color(0xFF25D366).withOpacity(0.2)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.preview_rounded,
                                  color: Color(0xFF25D366), size: 14),
                              SizedBox(width: 6),
                              Text('Preview',
                                  style: TextStyle(
                                      color: Color(0xFF25D366),
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600)),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(_resolvedMessage,
                              style: const TextStyle(
                                  color: AppColors.textSecondary,
                                  fontSize: 13,
                                  height: 1.5)),
                        ],
                      ),
                    ),
                  ] else ...[
                    TextField(
                      controller: _customMsgCtrl,
                      maxLines: 5,
                      style: const TextStyle(
                          color: AppColors.textPrimary, fontSize: 14),
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(
                          hintText: 'Type your custom message...'),
                    ),
                  ],
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    height: 54,
                    child: ElevatedButton.icon(
                      onPressed: _send,
                      icon: const Icon(Icons.send_rounded),
                      label: Text(
                          'Send via ${_useCloud ? 'Cloud' : 'Device'} WhatsApp',
                          style: const TextStyle(
                              fontSize: 15, fontWeight: FontWeight.w700)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF25D366),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(14)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChannelButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;
  const _ChannelButton(
      {required this.label,
      required this.icon,
      required this.isSelected,
      required this.onTap});

  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding:
              const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
          decoration: BoxDecoration(
            color: isSelected
                ? const Color(0xFF25D366).withOpacity(0.15)
                : AppColors.backgroundElevated,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
                color: isSelected
                    ? const Color(0xFF25D366)
                    : AppColors.divider,
                width: isSelected ? 1.5 : 1),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon,
                  color: isSelected
                      ? const Color(0xFF25D366)
                      : AppColors.textHint,
                  size: 18),
              const SizedBox(width: 8),
              Flexible(
                child: Text(label,
                    style: TextStyle(
                        fontSize: 12,
                        fontWeight: isSelected
                            ? FontWeight.w600
                            : FontWeight.w400,
                        color: isSelected
                            ? const Color(0xFF25D366)
                            : AppColors.textSecondary),
                    overflow: TextOverflow.ellipsis),
              ),
            ],
          ),
        ),
      );
}
