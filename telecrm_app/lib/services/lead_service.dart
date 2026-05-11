// lib/services/lead_service.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../core/constants.dart';
import '../models/models.dart';
import 'notification_service.dart';

// ─────────────────────────────────────────────────────────
// PROVIDERS
// ─────────────────────────────────────────────────────────
final leadServiceProvider = Provider<LeadService>((ref) {
  return LeadService(ref.read(apiClientProvider));
});

final followUpServiceProvider = Provider<FollowUpService>((ref) {
  return FollowUpService(ref.read(apiClientProvider));
});

final dashboardServiceProvider = Provider<DashboardService>((ref) {
  return DashboardService(ref.read(apiClientProvider));
});

// Dashboard
final dashboardProvider = FutureProvider.autoDispose<DashboardSummary>((ref) async {
  return ref.read(dashboardServiceProvider).getDashboard();
});

// My Leads (assigned)
class LeadsNotifier extends StateNotifier<LeadsState> {
  final LeadService _service;
  LeadsNotifier(this._service) : super(const LeadsState());

  Future<void> loadLeads({bool refresh = false}) async {
    if (refresh) state = state.copyWith(page: 1, leads: [], hasMore: true);
    if (!state.hasMore || state.isLoading) return;

    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await _service.getMyLeads(
        page: state.page,
        search: state.searchQuery,
        statusFilter: state.statusFilter,
      );
      final newLeads = refresh ? result.results : [...state.leads, ...result.results];
      state = state.copyWith(
        leads: newLeads,
        isLoading: false,
        page: state.page + 1,
        hasMore: result.next != null,
        totalCount: result.count,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: apiErrorMessage(e));
    }
  }

  Future<void> search(String query) async {
    state = state.copyWith(searchQuery: query, page: 1, leads: [], hasMore: true);
    await loadLeads();
  }

  Future<void> filterByStatus(String? status) async {
    state = state.copyWith(statusFilter: status, page: 1, leads: [], hasMore: true);
    await loadLeads();
  }

  void updateLeadLocally(Lead updated) {
    state = state.copyWith(
      leads: state.leads.map((l) => l.id == updated.id ? updated : l).toList(),
    );
  }
}

class LeadsState {
  final List<Lead> leads;
  final bool isLoading;
  final String? error;
  final int page;
  final bool hasMore;
  final int totalCount;
  final String searchQuery;
  final String? statusFilter;

  const LeadsState({
    this.leads = const [],
    this.isLoading = false,
    this.error,
    this.page = 1,
    this.hasMore = true,
    this.totalCount = 0,
    this.searchQuery = '',
    this.statusFilter,
  });

  LeadsState copyWith({
    List<Lead>? leads,
    bool? isLoading,
    String? error,
    int? page,
    bool? hasMore,
    int? totalCount,
    String? searchQuery,
    String? statusFilter,
  }) =>
      LeadsState(
        leads: leads ?? this.leads,
        isLoading: isLoading ?? this.isLoading,
        error: error,
        page: page ?? this.page,
        hasMore: hasMore ?? this.hasMore,
        totalCount: totalCount ?? this.totalCount,
        searchQuery: searchQuery ?? this.searchQuery,
        statusFilter: statusFilter ?? this.statusFilter,
      );
}

final leadsProvider = StateNotifierProvider.autoDispose<LeadsNotifier, LeadsState>((ref) {
  final notifier = LeadsNotifier(ref.read(leadServiceProvider));
  notifier.loadLeads();
  return notifier;
});

// Follow-ups
class FollowUpsNotifier extends StateNotifier<FollowUpsState> {
  final FollowUpService _service;
  FollowUpsNotifier(this._service) : super(const FollowUpsState()) {
    loadAll();
  }

  Future<void> loadAll() async {
    state = state.copyWith(isLoading: true);
    try {
      final results = await Future.wait([
        _service.getTodayFollowUps(),
        _service.getOverdueFollowUps(),
        _service.getUpcomingFollowUps(),
      ]);
      state = state.copyWith(
        today: results[0],
        overdue: results[1],
        upcoming: results[2],
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: apiErrorMessage(e));
    }
  }

  Future<bool> complete(int followUpId, {String? notes}) async {
    try {
      await _service.completeFollowUp(followUpId, notes: notes);
      await loadAll();
      return true;
    } catch (e) {
      return false;
    }
  }
}

class FollowUpsState {
  final List<FollowUp> today;
  final List<FollowUp> overdue;
  final List<FollowUp> upcoming;
  final bool isLoading;
  final String? error;

  const FollowUpsState({
    this.today = const [],
    this.overdue = const [],
    this.upcoming = const [],
    this.isLoading = false,
    this.error,
  });

  FollowUpsState copyWith({
    List<FollowUp>? today,
    List<FollowUp>? overdue,
    List<FollowUp>? upcoming,
    bool? isLoading,
    String? error,
  }) =>
      FollowUpsState(
        today: today ?? this.today,
        overdue: overdue ?? this.overdue,
        upcoming: upcoming ?? this.upcoming,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

final followUpsProvider = StateNotifierProvider.autoDispose<FollowUpsNotifier, FollowUpsState>((ref) {
  return FollowUpsNotifier(ref.read(followUpServiceProvider));
});

// Dialer queue — subset of my_leads for auto-dialing
final dialerQueueProvider = StateNotifierProvider<DialerQueueNotifier, DialerQueueState>((ref) {
  return DialerQueueNotifier(ref.read(leadServiceProvider));
});

class DialerQueueState {
  final List<Lead> queue;
  final int currentIndex;
  final bool isDialing;
  final bool isActive;
  final Lead? currentLead;
  final bool callInProgress;
  final Duration callDuration;
  final bool isLoading;
  final String? error;

  const DialerQueueState({
    this.queue = const [],
    this.currentIndex = 0,
    this.isDialing = false,
    this.isActive = false,
    this.currentLead,
    this.callInProgress = false,
    this.callDuration = Duration.zero,
    this.isLoading = false,
    this.error,
  });

  DialerQueueState copyWith({
    List<Lead>? queue,
    int? currentIndex,
    bool? isDialing,
    bool? isActive,
    Lead? currentLead,
    bool? callInProgress,
    Duration? callDuration,
    bool? isLoading,
    String? error,
    bool clearCurrentLead = false,
  }) =>
      DialerQueueState(
        queue: queue ?? this.queue,
        currentIndex: currentIndex ?? this.currentIndex,
        isDialing: isDialing ?? this.isDialing,
        isActive: isActive ?? this.isActive,
        currentLead: clearCurrentLead ? null : (currentLead ?? this.currentLead),
        callInProgress: callInProgress ?? this.callInProgress,
        callDuration: callDuration ?? this.callDuration,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );

  int get remaining => queue.length - currentIndex;
  double get progress => queue.isEmpty ? 0 : currentIndex / queue.length;
}

class DialerQueueNotifier extends StateNotifier<DialerQueueState> {
  final LeadService _service;
  DialerQueueNotifier(this._service) : super(const DialerQueueState());

  Future<void> loadQueue() async {
    state = state.copyWith(isLoading: true);
    try {
      final result = await _service.getMyLeads(page: 1, pageSize: 100, statusFilter: 'new');
      final result2 = await _service.getMyLeads(page: 1, pageSize: 100, statusFilter: 'callback');
      final all = [...result.results, ...result2.results];
      state = state.copyWith(
        queue: all,
        isLoading: false,
        currentIndex: 0,
        currentLead: all.isNotEmpty ? all[0] : null,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: apiErrorMessage(e));
    }
  }

  void startDialing() => state = state.copyWith(isActive: true);
  void stopDialing() => state = state.copyWith(isActive: false, isDialing: false, callInProgress: false);

  void setCallInProgress(bool inProgress) =>
      state = state.copyWith(callInProgress: inProgress);

  void updateCallDuration(Duration d) => state = state.copyWith(callDuration: d);

  void nextLead() {
    final next = state.currentIndex + 1;
    if (next < state.queue.length) {
      state = state.copyWith(
        currentIndex: next,
        currentLead: state.queue[next],
        callInProgress: false,
        callDuration: Duration.zero,
        isDialing: false,
        isActive: state.isActive,
      );
    } else {
      state = state.copyWith(isActive: false, isDialing: false, clearCurrentLead: true);
    }
  }

  void skipLead() => nextLead();

  void setDialing(bool v) => state = state.copyWith(isDialing: v);
}

// ─────────────────────────────────────────────────────────
// SERVICES
// ─────────────────────────────────────────────────────────
class LeadService {
  final ApiClient _client;
  LeadService(this._client);

  Future<PaginatedLeads> getMyLeads({
    int page = 1,
    String? search,
    String? statusFilter,
    int pageSize = 20,
  }) async {
    final params = <String, dynamic>{
      'page': page,
      'page_size': pageSize,
      if (search != null && search.isNotEmpty) 'q': search,
      if (statusFilter != null) 'status': statusFilter,
    };

    // Use search endpoint when searching, otherwise my_leads
    final endpoint = (search != null && search.isNotEmpty)
        ? AppConstants.searchLeadsEndpoint
        : AppConstants.myLeadsEndpoint;

    final response = await _client.dio.get(endpoint, queryParameters: params);
    return PaginatedLeads.fromJson(response.data);
  }

  Future<Lead> getLead(int id) async {
    final response = await _client.dio.get('${AppConstants.leadsEndpoint}$id/');
    return Lead.fromJson(response.data);
  }

  Future<Lead> updateLead(int id, {String? status, String? notes}) async {
    final response = await _client.dio.patch(
      '${AppConstants.leadsEndpoint}$id/',
      data: {
        if (status != null) 'status': status,
        if (notes != null) 'notes': notes,
      },
    );
    return Lead.fromJson(response.data);
  }

  Future<CallLog> createCallLog(int leadId, {
    required String disposition,
    String? remarks,
    Duration? duration,
    String? leadStatus,
  }) async {
    final response = await _client.dio.post(
      '/leads/$leadId/call/',
      data: {
        'disposition': disposition,
        if (remarks != null) 'remarks': remarks,
        if (duration != null)
          'duration': '${duration.inHours.toString().padLeft(2, '0')}:${(duration.inMinutes % 60).toString().padLeft(2, '0')}:${(duration.inSeconds % 60).toString().padLeft(2, '0')}',
        if (leadStatus != null) 'lead_status': leadStatus,
      },
    );
    return CallLog.fromJson(response.data);
  }

  Future<FollowUp> createFollowUp(int leadId, {
    required String followUpDate,
    required String followUpTime,
    String? remarks,
  }) async {
    final response = await _client.dio.post(
      '/leads/$leadId/follow-up/',
      data: {
        'follow_up_date': followUpDate,
        'follow_up_time': followUpTime,
        if (remarks != null) 'remarks': remarks,
      },
    );
    final followUp = FollowUp.fromJson(response.data);

    // Schedule a local notification 15 min before follow-up
    try {
      final dateParts = followUpDate.split('-');
      final timeParts = followUpTime.split(':');
      if (dateParts.length == 3 && timeParts.length >= 2) {
        final dt = DateTime(
          int.parse(dateParts[0]),
          int.parse(dateParts[1]),
          int.parse(dateParts[2]),
          int.parse(timeParts[0]),
          int.parse(timeParts[1]),
        );
        final lead = await getLead(leadId);
        await NotificationService().scheduleFollowUpReminder(
          followUpId: followUp.id,
          leadName: lead.name,
          followUpDateTime: dt,
        );
      }
    } catch (_) {
      // Notification scheduling is best-effort; don't fail the API call
    }

    return followUp;
  }

  Future<List<CallLog>> getCallLogs({int? leadId}) async {
    final params = <String, dynamic>{
      if (leadId != null) 'lead': leadId,
    };
    final response = await _client.dio.get(
      AppConstants.callLogsEndpoint,
      queryParameters: params,
    );
    final data = response.data;
    final list = data is Map ? (data['results'] as List? ?? []) : (data as List);
    return list.map((e) => CallLog.fromJson(e)).toList();
  }
}

class FollowUpService {
  final ApiClient _client;
  FollowUpService(this._client);

  Future<List<FollowUp>> getTodayFollowUps() async {
    final response = await _client.dio.get(AppConstants.todayFollowUpsEndpoint);
    final list = response.data is List ? response.data : (response.data['results'] ?? []);
    return (list as List).map((e) => FollowUp.fromJson(e)).toList();
  }

  Future<List<FollowUp>> getOverdueFollowUps() async {
    final response = await _client.dio.get(AppConstants.overdueFollowUpsEndpoint);
    final list = response.data is List ? response.data : (response.data['results'] ?? []);
    return (list as List).map((e) => FollowUp.fromJson(e)).toList();
  }

  Future<List<FollowUp>> getUpcomingFollowUps() async {
    final response = await _client.dio.get(AppConstants.upcomingFollowUpsEndpoint);
    final list = response.data is List ? response.data : (response.data['results'] ?? []);
    return (list as List).map((e) => FollowUp.fromJson(e)).toList();
  }

  Future<void> completeFollowUp(int id, {String? notes}) async {
    await _client.dio.post(
      '/follow-ups/$id/complete/',
      data: {
        if (notes != null) 'completion_notes': notes,
      },
    );
  }

  Future<void> snoozeFollowUp(int id, {required int minutes}) async {
    await _client.dio.post(
      '/follow-ups/$id/snooze/',
      data: {'snooze_minutes': minutes},
    );
  }
}

class DashboardService {
  final ApiClient _client;
  DashboardService(this._client);

  Future<DashboardSummary> getDashboard() async {
    final response = await _client.dio.get(AppConstants.dashboardEndpoint);
    return DashboardSummary.fromJson(response.data);
  }

  Future<Map<String, dynamic>> getAgentStats() async {
    final response = await _client.dio.get(AppConstants.agentStatsEndpoint);
    return response.data;
  }
}
