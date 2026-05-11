// lib/core/api_client.dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'constants.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

class ApiClient {
  late final Dio _dio;
  final Logger _logger = Logger();

  ApiClient() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.baseUrl,
        connectTimeout: AppConstants.connectTimeout,
        receiveTimeout: AppConstants.receiveTimeout,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );
    _dio.interceptors.add(_AuthInterceptor(_logger));
    _dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
      error: true,
      logPrint: (obj) => _logger.d(obj),
    ));
  }

  Dio get dio => _dio;
}

class _AuthInterceptor extends Interceptor {
  final Logger _logger;
  _AuthInterceptor(this._logger);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(AppConstants.tokenKey);
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Token $token';
    }
    super.onRequest(options, handler);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _logger.e('API Error: ${err.response?.statusCode} - ${err.message}');
    if (err.response?.statusCode == 401) {
      // Token expired — can trigger logout from here if needed
    }
    super.onError(err, handler);
  }
}

// Global helper for error messages
String apiErrorMessage(dynamic e) {
  if (e is DioException) {
    final data = e.response?.data;
    if (data is Map) {
      if (data.containsKey('error')) return data['error'];
      if (data.containsKey('detail')) return data['detail'];
      final firstVal = data.values.first;
      if (firstVal is List) return firstVal.first.toString();
      return firstVal.toString();
    }
    return e.message ?? 'Network error';
  }
  return e.toString();
}
