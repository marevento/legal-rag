import { Badge, Card, Text } from "@fluentui/react-components";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import type { MetricsReport, PatternRecommendation, StrategyComparison } from "../../api/api";
import styles from "./MetricsDashboard.module.css";

interface Props {
    report: MetricsReport;
}

const STRATEGY_COLORS: Record<string, string> = {
    bm25: "#0078d4",
    vector: "#107c10",
    hybrid: "#d83b01",
};

export const MetricsDashboard = ({ report }: Props) => {
    return (
        <div className={styles.container}>
            <StrategyChart comparisons={report.strategy_comparisons} />
            <PatternRecommendations recommendations={report.pattern_recommendations} />
            <CategoryBreakdown report={report} />
        </div>
    );
};

const StrategyChart = ({ comparisons }: { comparisons: StrategyComparison[] }) => {
    const metrics = ["avg_recall_at_5", "avg_precision_at_5", "avg_groundedness", "avg_citation_accuracy"] as const;
    const labels: Record<string, string> = {
        avg_recall_at_5: "Recall@5",
        avg_precision_at_5: "Precision@5",
        avg_groundedness: "Groundedness",
        avg_citation_accuracy: "Citation Acc.",
    };

    const chartData = metrics.map((metric) => {
        const entry: Record<string, string | number> = { metric: labels[metric] };
        for (const comp of comparisons) {
            entry[comp.strategy] = Number(comp[metric].toFixed(3));
        }
        return entry;
    });

    return (
        <Card className={styles.card}>
            <Text size={500} weight="semibold">
                Strategy Comparison
            </Text>
            <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="metric" />
                    <YAxis domain={[0, 1]} />
                    <Tooltip />
                    {comparisons.map((comp) => (
                        <Bar key={comp.strategy} dataKey={comp.strategy} fill={STRATEGY_COLORS[comp.strategy] || "#666"} />
                    ))}
                </BarChart>
            </ResponsiveContainer>

            <div className={styles.latencyRow}>
                {comparisons.map((comp) => (
                    <div key={comp.strategy} className={styles.latencyItem}>
                        <Text size={200} weight="semibold">
                            {comp.strategy}
                        </Text>
                        <Text size={200}>{comp.avg_latency_ms.toFixed(0)}ms avg</Text>
                    </div>
                ))}
            </div>
        </Card>
    );
};

const PatternRecommendations = ({ recommendations }: { recommendations: PatternRecommendation[] }) => {
    if (recommendations.length === 0) return null;

    return (
        <Card className={styles.card}>
            <Text size={500} weight="semibold">
                Pattern Recommendations
            </Text>
            <div className={styles.recommendations}>
                {recommendations.map((rec) => (
                    <div key={rec.pattern} className={styles.recommendation}>
                        <div className={styles.recHeader}>
                            <Text weight="semibold">{rec.pattern}</Text>
                            <Badge
                                color={rec.recommended ? "success" : "informative"}
                                appearance="filled"
                            >
                                {rec.recommended ? "Recommended" : "Not yet needed"}
                            </Badge>
                        </div>
                        <Text size={200} className={styles.recExplanation}>
                            {rec.explanation}
                        </Text>
                        <Text size={100} className={styles.recMeta}>
                            {rec.metric_name}: {rec.current_value} (threshold: {rec.threshold})
                        </Text>
                    </div>
                ))}
            </div>
        </Card>
    );
};

const CategoryBreakdown = ({ report }: { report: MetricsReport }) => {
    const categories = Object.keys(report.results_by_category);
    if (categories.length === 0) return null;

    const chartData = categories
        .map((cat) => {
            const results = report.results_by_category[cat];
            const hybridResults = results.filter((r) => r.search_strategy === "hybrid");
            if (hybridResults.length === 0) return null;
            const n = hybridResults.length;
            return {
                category: cat,
                recall: Number((hybridResults.reduce((s, r) => s + r.retrieval.recall_at_k, 0) / n).toFixed(3)),
                precision: Number((hybridResults.reduce((s, r) => s + r.retrieval.precision_at_k, 0) / n).toFixed(3)),
            };
        })
        .filter((d): d is NonNullable<typeof d> => d !== null);

    return (
        <Card className={styles.card}>
            <Text size={500} weight="semibold">
                Metrics by Query Category (Hybrid)
            </Text>
            <ResponsiveContainer width="100%" height={250}>
                <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="category" />
                    <YAxis domain={[0, 1]} />
                    <Tooltip />
                    <Bar dataKey="recall" fill="#0078d4" name="Recall@5" />
                    <Bar dataKey="precision" fill="#107c10" name="Precision@5" />
                </BarChart>
            </ResponsiveContainer>
        </Card>
    );
};
