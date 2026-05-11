// lib/services/call_service.dart
import 'dart:async';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:phone_state/phone_state.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'call_recording_service.dart';
import 'activity_tracking_service.dart';

final callServiceProvider = Provider<CallService>((ref) => CallService());

enum CallStatus { idle, dialing, ringing, active, ended, failed, permissionDenied }

class CallStateModel {
  final CallStatus status;
  final String? phoneNumber;
  final DateTime? startTime;
  final Duration? duration;
  final int? callLogId;   // Linked call log for recording upload
  final int? leadId;      // Linked lead for activity tracking
  final bool isRecording;

  const CallStateModel({
    this.status = CallStatus.idle,
    this.phoneNumber,
    this.startTime,
    this.duration,
    this.callLogId,
    this.leadId,
    this.isRecording = false,
  });

  CallStateModel copyWith({
    CallStatus? status,
    String? phoneNumber,
    DateTime? startTime,
    Duration? duration,
    bool clearStart = false,
    int? callLogId,
    int? leadId,
    bool? isRecording,
  }) =>
      CallStateModel(
        status: status ?? this.status,
        phoneNumber: phoneNumber ?? this.phoneNumber,
        startTime: clearStart ? null : (startTime ?? this.startTime),
        duration: duration ?? this.duration,
        callLogId: callLogId ?? this.callLogId,
        leadId: leadId ?? this.leadId,
        isRecording: isRecording ?? this.isRecording,
      );
}

class CallService {
  StreamSubscription? _phoneStateSubscription;
  final StreamController<CallStateModel> _callStateController =
      StreamController<CallStateModel>.broadcast();

  Stream<CallStateModel> get callStateStream => _callStateController.stream;

  CallStateModel _current = const CallStateModel();

  // Request phone permissions
  Future<bool> requestPermissions() async {
    final statuses = await [
      Permission.phone,
      Permission.microphone,
    ].request();
    return statuses[Permission.phone]!.isGranted &&
        statuses[Permission.microphone]!.isGranted;
  }

  // Make a call using url_launcher (opens native dialer)
  Future<bool> makeDirectCall(String phoneNumber) async {
    try {
      final hasPermission = await requestPermissions();
      if (!hasPermission) {
        _emit(_current.copyWith(status: CallStatus.permissionDenied));
        return false;
      }

      final cleaned = _cleanPhone(phoneNumber);

      _emit(_current.copyWith(
        status: CallStatus.dialing,
        phoneNumber: cleaned,
        clearStart: true,
      ));

      final uri = Uri(scheme: 'tel', path: cleaned);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri);
        _emit(_current.copyWith(status: CallStatus.ringing));
        _startListeningToPhoneState();
        return true;
      } else {
        _emit(_current.copyWith(status: CallStatus.failed));
        return false;
      }
    } on PlatformException {
      _emit(_current.copyWith(status: CallStatus.failed));
      return false;
    } catch (e) {
      _emit(_current.copyWith(status: CallStatus.failed));
      return false;
    }
  }

  void _startListeningToPhoneState() {
    _phoneStateSubscription?.cancel();
    _phoneStateSubscription = PhoneState.stream.listen((event) {
      switch (event.status) {
        case PhoneStateStatus.CALL_STARTED:
          final now = DateTime.now();
          _emit(_current.copyWith(status: CallStatus.active, startTime: now));
          break;
        case PhoneStateStatus.CALL_ENDED:
          final duration = _current.startTime != null
              ? DateTime.now().difference(_current.startTime!)
              : null;
          _emit(_current.copyWith(
            status: CallStatus.ended,
            duration: duration,
          ));
          _stopListening();
          break;
        case PhoneStateStatus.CALL_INCOMING:
          break;
        case PhoneStateStatus.NOTHING:
          if (_current.status == CallStatus.ringing ||
              _current.status == CallStatus.dialing) {
            _emit(_current.copyWith(status: CallStatus.ended));
            _stopListening();
          }
          break;
      }
    });
  }

  void _stopListening() {
    _phoneStateSubscription?.cancel();
    _phoneStateSubscription = null;
  }

  void resetCallState() {
    _emit(const CallStateModel());
  }

  void _emit(CallStateModel model) {
    _current = model;
    _callStateController.add(model);
  }

  String _cleanPhone(String phone) {
    return phone.replaceAll(RegExp(r'[\s\-\(\)]'), '');
  }

  void dispose() {
    _stopListening();
    _callStateController.close();
  }
}

// Riverpod notifier that wraps call state + recording + activity tracking
class CallStateNotifier extends StateNotifier<CallStateModel> {
  final CallService _callService;
  final CallRecordingService _recordingService;
  final ActivityTrackingService _activityService;
  final Ref _ref;
  StreamSubscription? _sub;
  Timer? _durationTimer;
  Duration _elapsed = Duration.zero;

  CallStateNotifier(
    this._callService,
    this._recordingService,
    this._activityService,
    this._ref,
  ) : super(const CallStateModel()) {
    _sub = _callService.callStateStream.listen((callState) async {
      state = callState;

      if (callState.status == CallStatus.active) {
        _startTimer();
        // Activity: log call_started
        unawaited(_activityService.logEvent(
          ActivityEvent.callStarted,
          leadId: state.leadId,
        ));
        // Start recording if enabled
        final recordingEnabled = _ref.read(recordingEnabledProvider);
        if (recordingEnabled && state.callLogId != null) {
          final started = await _recordingService.startRecording(state.callLogId!);
          if (started) {
            state = state.copyWith(isRecording: true);
            _ref.read(isRecordingProvider.notifier).state = true;
          }
        }
      } else if (callState.status == CallStatus.ended ||
          callState.status == CallStatus.idle) {
        _stopTimer();
        // Activity: log call_ended
        unawaited(_activityService.logEvent(
          ActivityEvent.callEnded,
          leadId: state.leadId,
        ));
        // Stop recording and upload
        if (state.isRecording && state.callLogId != null) {
          _ref.read(isRecordingProvider.notifier).state = false;
          state = state.copyWith(isRecording: false);
          await _recordingService.stopAndUpload(state.callLogId!);
        }
      }
    });
  }

  void _startTimer() {
    _elapsed = Duration.zero;
    _durationTimer?.cancel();
    _durationTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      _elapsed += const Duration(seconds: 1);
      state = state.copyWith(duration: _elapsed);
    });
  }

  void _stopTimer() {
    _durationTimer?.cancel();
    _durationTimer = null;
  }

  /// Sets the call log ID so recording can be linked to it.
  void setCallLogId(int id) {
    state = state.copyWith(callLogId: id);
  }

  /// Sets the lead ID so activity events can be linked to the right lead.
  void setLeadId(int id) {
    state = state.copyWith(leadId: id);
  }

  Future<bool> call(String phoneNumber) {
    return _callService.makeDirectCall(phoneNumber);
  }

  void reset() {
    _stopTimer();
    _elapsed = Duration.zero;
    _callService.resetCallState();
    state = const CallStateModel();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _durationTimer?.cancel();
    super.dispose();
  }
}

final callStateProvider =
    StateNotifierProvider<CallStateNotifier, CallStateModel>((ref) {
  return CallStateNotifier(
    ref.read(callServiceProvider),
    ref.read(callRecordingServiceProvider),
    ref.read(activityTrackingServiceProvider),
    ref,
  );
});
