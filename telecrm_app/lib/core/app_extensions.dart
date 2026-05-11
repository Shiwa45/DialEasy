// lib/core/app_extensions.dart

/// Handy extension methods used throughout TeleCRM

extension StringX on String {
  /// "hello_world" → "Hello World"
  String toTitleCase() => split('_')
      .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
      .join(' ');

  /// Initials from a full name: "John Doe" → "JD"
  String get initials {
    final parts = trim().split(' ');
    if (parts.length >= 2) return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
    return isNotEmpty ? this[0].toUpperCase() : '?';
  }

  /// Safe phone format: adds +91 if missing and number is 10 digits
  String get formattedPhone {
    final digits = replaceAll(RegExp(r'\D'), '');
    if (digits.length == 10) return '+91 $digits';
    return this;
  }

  /// Truncate with ellipsis
  String truncate(int maxLen) =>
      length > maxLen ? '${substring(0, maxLen)}…' : this;

  /// True when the string is a valid ISO-8601 date
  bool get isValidDate {
    try {
      DateTime.parse(this);
      return true;
    } catch (_) {
      return false;
    }
  }
}

extension DurationX on Duration {
  /// "02:35" format
  String get mmSs {
    final m = inMinutes.toString().padLeft(2, '0');
    final s = (inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  /// "2m 35s" format
  String get readable {
    if (inSeconds < 60) return '${inSeconds}s';
    if (inMinutes < 60) return '${inMinutes}m ${inSeconds % 60}s';
    return '${inHours}h ${inMinutes % 60}m';
  }
}

extension DateTimeX on DateTime {
  /// "Today", "Yesterday" or "Mar 5"
  String get relativeDate {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final d = DateTime(year, month, day);
    final diff = today.difference(d).inDays;
    if (diff == 0) return 'Today';
    if (diff == 1) return 'Yesterday';
    if (diff < 7) return '$diff days ago';
    return '${_monthAbbr(month)} $day';
  }

  /// "10:30 AM"
  String get timeLabel {
    final h = hour > 12 ? hour - 12 : (hour == 0 ? 12 : hour);
    final m = minute.toString().padLeft(2, '0');
    final suffix = hour >= 12 ? 'PM' : 'AM';
    return '$h:$m $suffix';
  }

  /// "Mar 5, 2024"
  String get dateLabel {
    return '${_monthAbbr(month)} $day, $year';
  }

  static String _monthAbbr(int m) => const [
        '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
      ][m];
}

extension NullableStringX on String? {
  bool get isNullOrEmpty => this == null || this!.isEmpty;
  String get orEmpty => this ?? '';
}

extension ListX<T> on List<T> {
  /// Safe first element
  T? get firstOrNull => isEmpty ? null : first;

  /// Safe last element
  T? get lastOrNull => isEmpty ? null : last;
}
