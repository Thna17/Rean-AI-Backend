import 'package:flutter/material.dart';
import 'package:ai_tutor_app/core/network/api_client.dart';
import 'package:provider/provider.dart';

class MisconceptionHeatmap extends StatefulWidget {
  const MisconceptionHeatmap({super.key});

  @override
  State<MisconceptionHeatmap> createState() => _MisconceptionHeatmapState();
}

class _MisconceptionHeatmapState extends State<MisconceptionHeatmap> {
  bool _isLoading = true;
  String? _error;
  List<Map<String, dynamic>> _data = [];

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  Future<void> _fetchData() async {
    try {
      final apiClient = context.read<ApiClient>();
      final response = await apiClient.get('/misconceptions/heatmap');
      if (mounted) {
        setState(() {
          _data = List<Map<String, dynamic>>.from(response['data'] ?? []);
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  Color _getColorForErrorCount(int count) {
    if (count == 0) return Colors.green.withValues(alpha: 0.2);
    if (count < 3) return Colors.yellow.withValues(alpha: 0.5);
    if (count < 5) return Colors.orange.withValues(alpha: 0.7);
    return Colors.red.withValues(alpha: 0.8);
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(child: Text('Failed to load heatmap: $_error'));
    }

    if (_data.isEmpty) {
      return const Center(child: Text('No misconceptions logged yet.'));
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        columns: const [
          DataColumn(label: Text('Subject')),
          DataColumn(label: Text('Sub Topic')),
          DataColumn(label: Text('Errors')),
          DataColumn(label: Text('Severity')),
        ],
        rows: _data.map((item) {
          final count = (item['error_count'] as num?)?.toInt() ?? 0;
          return DataRow(
            cells: [
              DataCell(Text(item['subject']?.toString() ?? 'N/A')),
              DataCell(Text(item['sub_topic']?.toString() ?? 'N/A')),
              DataCell(Text(count.toString())),
              DataCell(
                Container(
                  width: 24,
                  height: 24,
                  decoration: BoxDecoration(
                    color: _getColorForErrorCount(count),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }
}
