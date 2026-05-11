// lib/models/models.dart
import 'package:equatable/equatable.dart';

// ─────────────────────────────────────────────────────────
// USER / AGENT
// ─────────────────────────────────────────────────────────
class AppUser extends Equatable {
  final int id;
  final String username;
  final String firstName;
  final String lastName;
  final String email;
  final String fullName;
  final String? dateJoined;

  const AppUser({
    required this.id,
    required this.username,
    required this.firstName,
    required this.lastName,
    required this.email,
    required this.fullName,
    this.dateJoined,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'] ?? 0,
        username: json['username'] ?? '',
        firstName: json['first_name'] ?? '',
        lastName: json['last_name'] ?? '',
        email: json['email'] ?? '',
        fullName: json['full_name'] ?? json['username'] ?? '',
        dateJoined: json['date_joined'],
      );

  String get initials {
    if (fullName.isNotEmpty) {
      final parts = fullName.trim().split(' ');
      if (parts.length >= 2) return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
      return parts[0][0].toUpperCase();
    }
    return username.isNotEmpty ? username[0].toUpperCase() : 'A';
  }

  @override
  List<Object?> get props => [id, username];
}

class AgentProfile {
  final String department;
  final String phone;
  final String? hireDate;
  final int targetCallsPerDay;
  final int targetConversionsPerMonth;
  final bool isActive;

  const AgentProfile({
    required this.department,
    required this.phone,
    this.hireDate,
    required this.targetCallsPerDay,
    required this.targetConversionsPerMonth,
    required this.isActive,
  });

  factory AgentProfile.fromJson(Map<String, dynamic> json) => AgentProfile(
        department: json['department'] ?? '',
        phone: json['phone'] ?? '',
        hireDate: json['hire_date'],
        targetCallsPerDay: json['target_calls_per_day'] ?? 50,
        targetConversionsPerMonth: json['target_conversions_per_month'] ?? 10,
        isActive: json['is_active'] ?? true,
      );
}

// ─────────────────────────────────────────────────────────
// LEAD
// ─────────────────────────────────────────────────────────
class Lead extends Equatable {
  final int id;
  final String name;
  final String phone;
  final String? email;
  final String? company;
  final String status;
  final String statusDisplay;
  final AppUser? assignedAgent;
  final String? source;
  final String? notes;
  final String createdAt;
  final String updatedAt;
  final int callCount;
  final String? lastCallDate;
  final String? lastCallDisposition;
  final int followUpCount;
  final Map<String, dynamic>? nextFollowUp;

  const Lead({
    required this.id,
    required this.name,
    required this.phone,
    this.email,
    this.company,
    required this.status,
    required this.statusDisplay,
    this.assignedAgent,
    this.source,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
    required this.callCount,
    this.lastCallDate,
    this.lastCallDisposition,
    required this.followUpCount,
    this.nextFollowUp,
  });

  factory Lead.fromJson(Map<String, dynamic> json) => Lead(
        id: json['id'] ?? 0,
        name: json['name'] ?? '',
        phone: json['phone'] ?? '',
        email: json['email'],
        company: json['company'],
        status: json['status'] ?? 'new',
        statusDisplay: json['status_display'] ?? 'New',
        assignedAgent: json['assigned_agent'] != null
            ? AppUser.fromJson(json['assigned_agent'])
            : null,
        source: json['source'],
        notes: json['notes'],
        createdAt: json['created_at'] ?? '',
        updatedAt: json['updated_at'] ?? '',
        callCount: json['call_count'] ?? 0,
        lastCallDate: json['last_call_date'],
        lastCallDisposition: json['last_call_disposition'],
        followUpCount: json['follow_up_count'] ?? 0,
        nextFollowUp: json['next_follow_up'],
      );

  Lead copyWith({
    String? status,
    String? statusDisplay,
    String? notes,
    int? callCount,
    String? lastCallDate,
    String? lastCallDisposition,
    int? followUpCount,
    Map<String, dynamic>? nextFollowUp,
  }) =>
      Lead(
        id: id,
        name: name,
        phone: phone,
        email: email,
        company: company,
        status: status ?? this.status,
        statusDisplay: statusDisplay ?? this.statusDisplay,
        assignedAgent: assignedAgent,
        source: source,
        notes: notes ?? this.notes,
        createdAt: createdAt,
        updatedAt: updatedAt,
        callCount: callCount ?? this.callCount,
        lastCallDate: lastCallDate ?? this.lastCallDate,
        lastCallDisposition: lastCallDisposition ?? this.lastCallDisposition,
        followUpCount: followUpCount ?? this.followUpCount,
        nextFollowUp: nextFollowUp ?? this.nextFollowUp,
      );

  @override
  List<Object?> get props => [id, phone, status];
}

// ─────────────────────────────────────────────────────────
// CALL LOG
// ─────────────────────────────────────────────────────────
class CallLog extends Equatable {
  final int id;
  final Map<String, dynamic> lead;
  final AppUser? agent;
  final String callDate;
  final String? duration;
  final String? durationDisplay;
  final String disposition;
  final String dispositionDisplay;
  final String? remarks;
  final String createdAt;

  const CallLog({
    required this.id,
    required this.lead,
    this.agent,
    required this.callDate,
    this.duration,
    this.durationDisplay,
    required this.disposition,
    required this.dispositionDisplay,
    this.remarks,
    required this.createdAt,
  });

  factory CallLog.fromJson(Map<String, dynamic> json) => CallLog(
        id: json['id'] ?? 0,
        lead: json['lead'] is Map ? Map<String, dynamic>.from(json['lead']) : {},
        agent: json['agent'] != null ? AppUser.fromJson(json['agent']) : null,
        callDate: json['call_date'] ?? '',
        duration: json['duration'],
        durationDisplay: json['duration_display'],
        disposition: json['disposition'] ?? '',
        dispositionDisplay: json['disposition_display'] ?? '',
        remarks: json['remarks'],
        createdAt: json['created_at'] ?? '',
      );

  @override
  List<Object?> get props => [id];
}

// ─────────────────────────────────────────────────────────
// FOLLOW-UP
// ─────────────────────────────────────────────────────────
class FollowUp extends Equatable {
  final int id;
  final Map<String, dynamic> lead;
  final AppUser? agent;
  final String followUpDate;
  final String followUpTime;
  final String? remarks;
  final bool isCompleted;
  final String? createdAt;
  final String? completedAt;
  final bool isOverdue;
  final bool isToday;
  final String formattedDatetime;

  const FollowUp({
    required this.id,
    required this.lead,
    this.agent,
    required this.followUpDate,
    required this.followUpTime,
    this.remarks,
    required this.isCompleted,
    this.createdAt,
    this.completedAt,
    required this.isOverdue,
    required this.isToday,
    required this.formattedDatetime,
  });

  factory FollowUp.fromJson(Map<String, dynamic> json) => FollowUp(
        id: json['id'] ?? 0,
        lead: json['lead'] is Map ? Map<String, dynamic>.from(json['lead']) : {},
        agent: json['agent'] != null ? AppUser.fromJson(json['agent']) : null,
        followUpDate: json['follow_up_date'] ?? '',
        followUpTime: json['follow_up_time'] ?? '',
        remarks: json['remarks'],
        isCompleted: json['is_completed'] ?? false,
        createdAt: json['created_at'],
        completedAt: json['completed_at'],
        isOverdue: json['is_overdue'] ?? false,
        isToday: json['is_today'] ?? false,
        formattedDatetime: json['formatted_datetime'] ?? '',
      );

  String get leadName => lead['name'] ?? '';
  String get leadPhone => lead['phone'] ?? '';
  int get leadId => lead['id'] ?? 0;

  @override
  List<Object?> get props => [id, isCompleted];
}

// ─────────────────────────────────────────────────────────
// DASHBOARD SUMMARY
// ─────────────────────────────────────────────────────────
class DashboardSummary {
  final int totalLeads;
  final int newLeads;
  final int contactedLeads;
  final int convertedLeads;
  final double conversionRate;
  final int todayCalls;
  final int todayFollowUps;
  final int weekCalls;
  final int pendingFollowUps;
  final int overdueFollowUps;
  final List<CallLog> recentCalls;
  final List<FollowUp> upcomingFollowUps;
  final List<Map<String, dynamic>> leadStatuses;

  const DashboardSummary({
    required this.totalLeads,
    required this.newLeads,
    required this.contactedLeads,
    required this.convertedLeads,
    required this.conversionRate,
    required this.todayCalls,
    required this.todayFollowUps,
    required this.weekCalls,
    required this.pendingFollowUps,
    required this.overdueFollowUps,
    required this.recentCalls,
    required this.upcomingFollowUps,
    required this.leadStatuses,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    final summary = json['summary'] as Map<String, dynamic>? ?? {};
    return DashboardSummary(
      totalLeads: summary['total_leads'] ?? 0,
      newLeads: summary['new_leads'] ?? 0,
      contactedLeads: summary['contacted_leads'] ?? 0,
      convertedLeads: summary['converted_leads'] ?? 0,
      conversionRate: (summary['conversion_rate'] ?? 0.0).toDouble(),
      todayCalls: summary['today_calls'] ?? 0,
      todayFollowUps: summary['today_follow_ups'] ?? 0,
      weekCalls: summary['week_calls'] ?? 0,
      pendingFollowUps: summary['pending_follow_ups'] ?? 0,
      overdueFollowUps: summary['overdue_follow_ups'] ?? 0,
      recentCalls: (json['recent_calls'] as List? ?? [])
          .map((e) => CallLog.fromJson(e))
          .toList(),
      upcomingFollowUps: (json['upcoming_follow_ups'] as List? ?? [])
          .map((e) => FollowUp.fromJson(e))
          .toList(),
      leadStatuses: (json['lead_statuses'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e))
          .toList(),
    );
  }
}

// ─────────────────────────────────────────────────────────
// PAGINATED RESPONSE
// ─────────────────────────────────────────────────────────
class PaginatedLeads {
  final int count;
  final String? next;
  final String? previous;
  final List<Lead> results;

  const PaginatedLeads({
    required this.count,
    this.next,
    this.previous,
    required this.results,
  });

  factory PaginatedLeads.fromJson(Map<String, dynamic> json) => PaginatedLeads(
        count: json['count'] ?? 0,
        next: json['next'],
        previous: json['previous'],
        results: (json['results'] as List? ?? [])
            .map((e) => Lead.fromJson(e))
            .toList(),
      );
}
