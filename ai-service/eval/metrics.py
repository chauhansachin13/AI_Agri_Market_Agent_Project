"""Classification metrics, computed without pulling in scikit-learn.

Accuracy alone is a poor summary of a four-class problem with an unbalanced
prior — a classifier that always answered `price_query` would score well on a
set where most questions are price questions. Per-class precision, recall and
F1 are what actually show whether the other three intents work, so those are
what the report table quotes and what is computed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClassMetrics:
    label: str
    support: int = 0
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class Report:
    """Per-class and aggregate results for one classification task."""

    name: str
    classes: dict[str, ClassMetrics] = field(default_factory=dict)
    correct: int = 0
    total: int = 0
    errors: list[tuple[str, str, str]] = field(default_factory=list)  # (input, expected, got)

    def add(self, expected: str, predicted: str, source: str = "") -> None:
        self.total += 1
        for label in (expected, predicted):
            self.classes.setdefault(label, ClassMetrics(label=label))

        self.classes[expected].support += 1
        if expected == predicted:
            self.correct += 1
            self.classes[expected].true_positive += 1
        else:
            self.classes[expected].false_negative += 1
            self.classes[predicted].false_positive += 1
            self.errors.append((source, expected, predicted))

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def macro_f1(self) -> float:
        """Unweighted mean F1 — treats a rare intent as seriously as a common one."""
        scored = [c for c in self.classes.values() if c.support]
        return sum(c.f1 for c in scored) / len(scored) if scored else 0.0

    @property
    def weighted_f1(self) -> float:
        scored = [c for c in self.classes.values() if c.support]
        total = sum(c.support for c in scored)
        return sum(c.f1 * c.support for c in scored) / total if total else 0.0

    def table(self) -> str:
        rows = [f"{'class':<26} {'prec':>6} {'recall':>7} {'f1':>6} {'n':>5}"]
        rows.append("-" * 54)
        for metrics in sorted(self.classes.values(), key=lambda c: -c.support):
            if not metrics.support:
                continue
            rows.append(
                f"{metrics.label:<26} {metrics.precision:>6.3f} {metrics.recall:>7.3f} "
                f"{metrics.f1:>6.3f} {metrics.support:>5}"
            )
        rows.append("-" * 54)
        rows.append(
            f"{'accuracy':<26} {'':>6} {'':>7} {self.accuracy:>6.3f} {self.total:>5}"
        )
        rows.append(f"{'macro F1':<26} {'':>6} {'':>7} {self.macro_f1:>6.3f}")
        rows.append(f"{'weighted F1':<26} {'':>6} {'':>7} {self.weighted_f1:>6.3f}")
        return "\n".join(rows)


def confusion(report: Report) -> str:
    """Render the confusion matrix, so systematic mix-ups are visible."""
    labels = sorted(c.label for c in report.classes.values() if c.support)
    if not labels:
        return "(no data)"

    counts = {(a, b): 0 for a in labels for b in labels}
    # Correct predictions are the diagonal; errors were recorded as they happened.
    for label in labels:
        counts[(label, label)] = report.classes[label].true_positive
    for _, expected, got in report.errors:
        if (expected, got) in counts:
            counts[(expected, got)] += 1

    width = max(len(label) for label in labels) + 1
    header = " " * (width + 2) + " ".join(f"{label[:8]:>9}" for label in labels)
    rows = [header, " " * (width + 2) + "-" * (10 * len(labels))]
    for expected in labels:
        cells = " ".join(f"{counts[(expected, got)]:>9}" for got in labels)
        rows.append(f"{expected:<{width}} | {cells}")
    return "\n".join(rows)
