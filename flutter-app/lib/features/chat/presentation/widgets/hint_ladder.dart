import 'package:flutter/material.dart';

class HintLadder extends StatefulWidget {
  const HintLadder({super.key, required this.hints});

  final List<String> hints;

  @override
  State<HintLadder> createState() => _HintLadderState();
}

class _HintLadderState extends State<HintLadder> {
  int currentHintIndex = 0;

  void _showNextHint() {
    if (currentHintIndex < widget.hints.length) {
      setState(() {
        currentHintIndex++;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.hints.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (int i = 0; i < currentHintIndex; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 8.0),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.blue.shade200),
              ),
              child: Text(
                "💡 Hint ${i + 1}: ${widget.hints[i]}",
                style: const TextStyle(color: Colors.black87),
              ),
            ),
          ),
        if (currentHintIndex < widget.hints.length)
          ElevatedButton.icon(
            onPressed: _showNextHint,
            icon: const Icon(Icons.lightbulb_outline),
            label: Text(
              currentHintIndex == 0 ? "I need a hint" : "I need another hint",
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.amber.shade100,
              foregroundColor: Colors.brown.shade800,
            ),
          ),
      ],
    );
  }
}
