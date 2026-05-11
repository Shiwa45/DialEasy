// lib/core/theme.dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppColors {
  // Primary gradient — deep violet to electric indigo
  static const Color primary = Color(0xFF6C3CE1);
  static const Color primaryDark = Color(0xFF4A1FA8);
  static const Color primaryLight = Color(0xFF9B6DFF);

  // Accent — vivid orange
  static const Color accent = Color(0xFFFF6B35);
  static const Color accentLight = Color(0xFFFF9A72);

  // Secondary — electric cyan
  static const Color secondary = Color(0xFF00D4FF);
  static const Color secondaryDark = Color(0xFF0099CC);

  // Status colors
  static const Color success = Color(0xFF00C896);
  static const Color successLight = Color(0xFFE0FFF7);
  static const Color warning = Color(0xFFFFB800);
  static const Color warningLight = Color(0xFFFFF8E1);
  static const Color error = Color(0xFFFF4757);
  static const Color errorLight = Color(0xFFFFEBEE);
  static const Color info = Color(0xFF2196F3);

  // Backgrounds
  static const Color background = Color(0xFF0F0E1A);
  static const Color backgroundCard = Color(0xFF1A1828);
  static const Color backgroundElevated = Color(0xFF221F35);
  static const Color surface = Color(0xFF2A2642);

  // Text
  static const Color textPrimary = Color(0xFFF0EDFF);
  static const Color textSecondary = Color(0xFFAAA7CC);
  static const Color textHint = Color(0xFF6B6890);
  static const Color textOnPrimary = Colors.white;

  // Divider
  static const Color divider = Color(0xFF2E2B48);

  // Lead status colors
  static const Color statusNew = Color(0xFF2196F3);
  static const Color statusContacted = Color(0xFF9C27B0);
  static const Color statusInterested = Color(0xFF00C896);
  static const Color statusNotInterested = Color(0xFFFF4757);
  static const Color statusCallback = Color(0xFFFFB800);
  static const Color statusWrongNumber = Color(0xFF607D8B);
  static const Color statusNotReachable = Color(0xFFFF6B35);
  static const Color statusConverted = Color(0xFF4CAF50);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF6C3CE1), Color(0xFF3D1FA3)],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFFF6B35), Color(0xFFFF2D55)],
  );

  static const LinearGradient successGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF00C896), Color(0xFF00A878)],
  );

  static const LinearGradient cyanGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF00D4FF), Color(0xFF0099CC)],
  );

  static const LinearGradient backgroundGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0xFF0F0E1A), Color(0xFF1A1828)],
  );

  static const LinearGradient cardGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF1E1B30), Color(0xFF251F40)],
  );

  static Color statusColor(String status) {
    switch (status) {
      case 'new': return statusNew;
      case 'contacted': return statusContacted;
      case 'interested': return statusInterested;
      case 'not_interested': return statusNotInterested;
      case 'callback': return statusCallback;
      case 'wrong_number': return statusWrongNumber;
      case 'not_reachable': return statusNotReachable;
      case 'converted': return statusConverted;
      default: return textSecondary;
    }
  }
}

class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.background,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.primary,
        secondary: AppColors.accent,
        surface: AppColors.backgroundCard,
        error: AppColors.error,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: AppColors.textPrimary,
      ),
      textTheme: GoogleFonts.poppinsTextTheme(
        const TextTheme(
          displayLarge: TextStyle(
            fontSize: 32, fontWeight: FontWeight.w700, color: AppColors.textPrimary, letterSpacing: -0.5,
          ),
          displayMedium: TextStyle(
            fontSize: 28, fontWeight: FontWeight.w700, color: AppColors.textPrimary, letterSpacing: -0.5,
          ),
          displaySmall: TextStyle(
            fontSize: 24, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
          ),
          headlineLarge: TextStyle(
            fontSize: 22, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
          ),
          headlineMedium: TextStyle(
            fontSize: 20, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
          ),
          headlineSmall: TextStyle(
            fontSize: 18, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
          ),
          titleLarge: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
          ),
          titleMedium: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w500, color: AppColors.textPrimary,
          ),
          titleSmall: TextStyle(
            fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.textSecondary,
          ),
          bodyLarge: TextStyle(
            fontSize: 16, fontWeight: FontWeight.w400, color: AppColors.textPrimary,
          ),
          bodyMedium: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w400, color: AppColors.textSecondary,
          ),
          bodySmall: TextStyle(
            fontSize: 12, fontWeight: FontWeight.w400, color: AppColors.textHint,
          ),
          labelLarge: TextStyle(
            fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textPrimary,
          ),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontFamily: 'Poppins',
          fontSize: 20,
          fontWeight: FontWeight.w700,
          color: AppColors.textPrimary,
        ),
        iconTheme: IconThemeData(color: AppColors.textPrimary),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AppColors.backgroundCard,
        selectedItemColor: AppColors.primaryLight,
        unselectedItemColor: AppColors.textHint,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        color: AppColors.backgroundCard,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        clipBehavior: Clip.antiAlias,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.backgroundElevated,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.divider),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.divider),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: AppColors.primaryLight, width: 2),
        ),
        hintStyle: const TextStyle(
          color: AppColors.textHint,
          fontFamily: 'Poppins',
        ),
        labelStyle: const TextStyle(
          color: AppColors.textSecondary,
          fontFamily: 'Poppins',
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          textStyle: const TextStyle(
            fontFamily: 'Poppins',
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.divider,
        thickness: 1,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.surface,
        labelStyle: const TextStyle(
          color: AppColors.textSecondary,
          fontFamily: 'Poppins',
          fontSize: 12,
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),
    );
  }
}
