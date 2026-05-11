// lib/services/whatsapp_service.dart
import 'package:url_launcher/url_launcher.dart';

class WhatsAppService {
  static Future<bool> sendViaDevice({
    required String phone,
    required String message,
  }) async {
    final cleaned = _cleanPhone(phone);
    final encoded = Uri.encodeComponent(message);
    final url = 'https://wa.me/$cleaned?text=$encoded';
    final uri = Uri.parse(url);
    try {
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  /// Cloud WhatsApp via wa.me (fallback/web approach)
  /// In production this should call your backend or WhatsApp Business API
  static Future<bool> sendViaCloudWhatsApp({
    required String phone,
    required String message,
    String? templateName,
  }) async {
    // TODO: Replace with your WhatsApp Cloud API call
    // For now, opens WhatsApp web/app
    final cleaned = _cleanPhone(phone);
    final encoded = Uri.encodeComponent(message);
    final url = 'https://api.whatsapp.com/send?phone=$cleaned&text=$encoded';
    final uri = Uri.parse(url);
    try {
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  static String applyTemplate(String template, {required String name, String? company}) {
    return template
        .replaceAll('{name}', name)
        .replaceAll('{company}', company ?? 'your company');
  }

  static String _cleanPhone(String phone) {
    var cleaned = phone.replaceAll(RegExp(r'[\s\-\(\)]'), '');
    // Add country code if not present (default India +91)
    if (!cleaned.startsWith('+') && !cleaned.startsWith('91')) {
      cleaned = '91$cleaned';
    } else if (cleaned.startsWith('+')) {
      cleaned = cleaned.substring(1);
    }
    return cleaned;
  }
}
