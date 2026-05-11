// lib/widgets/lead_search_delegate.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../services/lead_service.dart';

class LeadSearchDelegate extends SearchDelegate<Lead?> {
  final WidgetRef ref;

  LeadSearchDelegate(this.ref)
      : super(
          searchFieldLabel: 'Search leads...',
          searchFieldStyle: const TextStyle(
            color: AppColors.textPrimary,
            fontSize: 16,
          ),
        );

  @override
  ThemeData appBarTheme(BuildContext context) {
    return Theme.of(context).copyWith(
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.backgroundCard,
        iconTheme: IconThemeData(color: AppColors.textSecondary),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: InputBorder.none,
        hintStyle: TextStyle(color: AppColors.textHint),
      ),
    );
  }

  @override
  List<Widget> buildActions(BuildContext context) => [
        if (query.isNotEmpty)
          IconButton(
            onPressed: () => query = '',
            icon: const Icon(Icons.clear_rounded, color: AppColors.textSecondary),
          ),
      ];

  @override
  Widget buildLeading(BuildContext context) => IconButton(
        onPressed: () => close(context, null),
        icon: const Icon(Icons.arrow_back_ios_new_rounded,
            color: AppColors.textSecondary, size: 20),
      );

  @override
  Widget buildResults(BuildContext context) => _buildSearchResults(context);

  @override
  Widget buildSuggestions(BuildContext context) {
    if (query.length < 2) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.search_rounded,
                color: AppColors.textHint, size: 60),
            const SizedBox(height: 12),
            Text(
              'Type at least 2 characters to search',
              style: TextStyle(color: AppColors.textSecondary),
            ),
          ],
        ),
      );
    }
    return _buildSearchResults(context);
  }

  Widget _buildSearchResults(BuildContext context) {
    return _SearchResultsList(query: query, onSelect: (lead) => close(context, lead));
  }
}

// ─────────────────────────────────────────────────────────
// RESULTS LIST (stateful for API call)
// ─────────────────────────────────────────────────────────
class _SearchResultsList extends ConsumerStatefulWidget {
  final String query;
  final void Function(Lead) onSelect;
  const _SearchResultsList({required this.query, required this.onSelect});

  @override
  ConsumerState<_SearchResultsList> createState() => _SearchResultsListState();
}

class _SearchResultsListState extends ConsumerState<_SearchResultsList> {
  List<Lead> _results = [];
  bool _loading = false;
  String _lastQuery = '';

  @override
  void didUpdateWidget(_SearchResultsList old) {
    super.didUpdateWidget(old);
    if (widget.query != _lastQuery && widget.query.length >= 2) {
      _search(widget.query);
    }
  }

  @override
  void initState() {
    super.initState();
    if (widget.query.length >= 2) _search(widget.query);
  }

  Future<void> _search(String q) async {
    setState(() { _loading = true; _lastQuery = q; });
    try {
      final result = await ref.read(leadServiceProvider).getMyLeads(
            search: q,
            pageSize: 30,
          );
      if (mounted && _lastQuery == q) {
        setState(() { _results = result.results; _loading = false; });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(
          child: CircularProgressIndicator(color: AppColors.primaryLight));
    }
    if (_results.isEmpty && _lastQuery.isNotEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.search_off_rounded,
                color: AppColors.textHint, size: 50),
            const SizedBox(height: 12),
            Text('No results for "$_lastQuery"',
                style:
                    const TextStyle(color: AppColors.textSecondary, fontSize: 15)),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: _results.length,
      itemBuilder: (_, i) {
        final lead = _results[i];
        final statusColor = AppColors.statusColor(lead.status);
        return ListTile(
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
          leading: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            alignment: Alignment.center,
            child: Text(
              lead.name.isNotEmpty ? lead.name[0].toUpperCase() : '?',
              style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: statusColor),
            ),
          ),
          title: Text(
            lead.name,
            style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 15,
                color: AppColors.textPrimary),
          ),
          subtitle: Row(
            children: [
              const Icon(Icons.phone_rounded,
                  size: 12, color: AppColors.textHint),
              const SizedBox(width: 4),
              Text(lead.phone,
                  style: const TextStyle(
                      fontSize: 12, color: AppColors.textSecondary)),
              if (lead.company != null && lead.company!.isNotEmpty) ...[
                const Text(' · ',
                    style: TextStyle(color: AppColors.textHint)),
                Expanded(
                  child: Text(lead.company!,
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textHint),
                      overflow: TextOverflow.ellipsis),
                ),
              ],
            ],
          ),
          trailing: Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              lead.statusDisplay,
              style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: statusColor),
            ),
          ),
          onTap: () => widget.onSelect(lead),
        );
      },
    );
  }
}
