// lib/screens/login_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../services/auth_service.dart';
import 'home_screen.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;
    ref.read(authProvider.notifier).clearError();
    final success = await ref.read(authProvider.notifier).login(
          _usernameCtrl.text.trim(),
          _passwordCtrl.text,
        );
    if (success && mounted) {
      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          pageBuilder: (_, __, ___) => const HomeScreen(),
          transitionsBuilder: (_, animation, __, child) =>
              FadeTransition(opacity: animation, child: child),
          transitionDuration: const Duration(milliseconds: 400),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF0F0E1A), Color(0xFF1E0A5C), Color(0xFF0F0E1A)],
            stops: [0.0, 0.5, 1.0],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 60),
                // Header
                Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.2),
                            blurRadius: 10,
                          ),
                        ],
                      ),
                      child: Image.asset(
                        'assets/icons/icon.png',
                        fit: BoxFit.contain,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ShaderMask(
                          shaderCallback: (b) => AppColors.primaryGradient.createShader(b),
                          child: const Text(
                            'TeleCRM',
                            style: TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        Text(
                          'Agent Portal',
                          style: TextStyle(
                            fontSize: 13,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ],
                ).animate().slideX(begin: -0.3, duration: 600.ms, curve: Curves.easeOut).fade(),
                const SizedBox(height: 50),
                const Text(
                  'Welcome back 👋',
                  style: TextStyle(
                    fontSize: 30,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ).animate(delay: 100.ms).slideY(begin: 0.3, duration: 500.ms).fade(),
                const SizedBox(height: 8),
                Text(
                  'Sign in to start your calling session',
                  style: TextStyle(
                    fontSize: 15,
                    color: AppColors.textSecondary,
                  ),
                ).animate(delay: 150.ms).slideY(begin: 0.3, duration: 500.ms).fade(),
                const SizedBox(height: 40),

                // Form
                Form(
                  key: _formKey,
                  child: Column(
                    children: [
                      // Username
                      _buildField(
                        controller: _usernameCtrl,
                        label: 'Username',
                        icon: Icons.person_outline_rounded,
                        validator: (v) => v!.isEmpty ? 'Enter username' : null,
                        delay: 200.ms,
                      ),
                      const SizedBox(height: 18),
                      // Password
                      _buildField(
                        controller: _passwordCtrl,
                        label: 'Password',
                        icon: Icons.lock_outline_rounded,
                        obscure: _obscure,
                        validator: (v) => v!.isEmpty ? 'Enter password' : null,
                        delay: 300.ms,
                        suffix: IconButton(
                          icon: Icon(
                            _obscure ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                            color: AppColors.textHint,
                            size: 20,
                          ),
                          onPressed: () => setState(() => _obscure = !_obscure),
                        ),
                        onSubmit: (_) => _login(),
                      ),
                      const SizedBox(height: 12),

                      // Error
                      if (auth.error != null)
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: AppColors.error.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: AppColors.error.withOpacity(0.4)),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.error_outline_rounded,
                                  color: AppColors.error, size: 18),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  auth.error!,
                                  style: const TextStyle(color: AppColors.error, fontSize: 13),
                                ),
                              ),
                            ],
                          ),
                        ).animate().shake().fade(),
                      const SizedBox(height: 28),

                      // Login button
                      SizedBox(
                        width: double.infinity,
                        height: 56,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            gradient: auth.isLoading
                                ? const LinearGradient(
                                    colors: [Color(0xFF4A3A7A), Color(0xFF3A2A6A)])
                                : AppColors.primaryGradient,
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(
                                color: AppColors.primary.withOpacity(0.4),
                                blurRadius: 20,
                                offset: const Offset(0, 8),
                              ),
                            ],
                          ),
                          child: ElevatedButton(
                            onPressed: auth.isLoading ? null : _login,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.transparent,
                              shadowColor: Colors.transparent,
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(16)),
                            ),
                            child: auth.isLoading
                                ? const SizedBox(
                                    width: 24,
                                    height: 24,
                                    child: CircularProgressIndicator(
                                      color: Colors.white,
                                      strokeWidth: 2.5,
                                    ),
                                  )
                                : const Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(Icons.login_rounded, size: 20),
                                      SizedBox(width: 8),
                                      Text(
                                        'Sign In',
                                        style: TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w700,
                                          letterSpacing: 0.5,
                                        ),
                                      ),
                                    ],
                                  ),
                          ),
                        ),
                      ).animate(delay: 400.ms).slideY(begin: 0.5, duration: 500.ms).fade(),
                    ],
                  ),
                ),
                const SizedBox(height: 40),

                // Bottom decor
                Center(
                  child: Text(
                    'Powered by TeleCRM Platform',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppColors.textHint,
                    ),
                  ),
                ).animate(delay: 600.ms).fade(),
                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    bool obscure = false,
    String? Function(String?)? validator,
    Duration delay = Duration.zero,
    Widget? suffix,
    void Function(String)? onSubmit,
  }) =>
      TextFormField(
        controller: controller,
        obscureText: obscure,
        style: const TextStyle(color: AppColors.textPrimary, fontSize: 15),
        validator: validator,
        onFieldSubmitted: onSubmit,
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon, color: AppColors.textHint, size: 22),
          suffixIcon: suffix,
        ),
      ).animate(delay: delay).slideY(begin: 0.3, duration: 500.ms).fade();
}
