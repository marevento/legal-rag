import { Button, Spinner, Text, Title1 } from "@fluentui/react-components";
import { ArrowLeft24Regular, Play24Regular } from "@fluentui/react-icons";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { type MetricsReport, runEvaluation } from "../../api/api";
import { MetricsDashboard } from "../../components/MetricsDashboard/MetricsDashboard";
import styles from "./Evaluation.module.css";

export const Evaluation = () => {
    const navigate = useNavigate();
    const [report, setReport] = useState<MetricsReport | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleRun = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await runEvaluation();
            setReport(result);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Evaluation failed");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <Button
                    appearance="subtle"
                    icon={<ArrowLeft24Regular />}
                    onClick={() => navigate("/")}
                >
                    Back to Chat
                </Button>
                <Title1>Evaluation Dashboard</Title1>
                <Text size={300}>
                    Compare search strategies and get pattern recommendations based on golden dataset metrics.
                </Text>
            </div>

            <div className={styles.actions}>
                <Button
                    appearance="primary"
                    icon={<Play24Regular />}
                    onClick={handleRun}
                    disabled={isLoading}
                >
                    {isLoading ? "Running evaluation..." : "Run Evaluation"}
                </Button>
            </div>

            {isLoading && (
                <div className={styles.loading}>
                    <Spinner size="large" label="Running evaluation against golden dataset..." />
                </div>
            )}

            {error && (
                <div className={styles.error}>
                    <Text>{error}</Text>
                </div>
            )}

            {report && <MetricsDashboard report={report} />}
        </div>
    );
};
