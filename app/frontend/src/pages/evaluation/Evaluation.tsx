import { Button, ProgressBar, Text, Title1 } from "@fluentui/react-components";
import { ArrowLeft24Regular, Play24Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
    type AuthUser,
    type EvalProgressData,
    type MetricsReport,
    getEvalStatus,
    startEvaluation,
} from "../../api/api";
import { MetricsDashboard } from "../../components/MetricsDashboard/MetricsDashboard";
import styles from "./Evaluation.module.css";

interface Props {
    user: AuthUser;
}

export const Evaluation = ({ user }: Props) => {
    const navigate = useNavigate();
    const [report, setReport] = useState<MetricsReport | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [progress, setProgress] = useState<EvalProgressData | null>(null);
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const stopPolling = useCallback(() => {
        if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
    }, []);

    const startPolling = useCallback(() => {
        stopPolling();
        pollingRef.current = setInterval(async () => {
            try {
                const status = await getEvalStatus();
                if (status.progress) {
                    setProgress(status.progress);
                }
                if (status.report) {
                    setReport(status.report);
                    setIsLoading(false);
                    setProgress(null);
                    stopPolling();
                }
                if (!status.running && !status.report) {
                    setError("Evaluation stopped unexpectedly");
                    setIsLoading(false);
                    stopPolling();
                }
            } catch {
                // Ignore transient polling errors
            }
        }, 1000);
    }, [stopPolling]);

    useEffect(() => {
        // Load cached results on mount
        getEvalStatus().then((status) => {
            if (status.report) setReport(status.report);
            if (status.running) {
                setIsLoading(true);
                startPolling();
            }
        }).catch(() => {});
        return () => stopPolling();
    }, [stopPolling, startPolling]);

    const handleRun = async () => {
        setIsLoading(true);
        setError(null);
        setReport(null);
        setProgress(null);
        try {
            await startEvaluation();
            startPolling();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Evaluation failed");
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

            {user.role === "admin" && (
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
            )}

            {isLoading && progress && (
                <div className={styles.progressContainer}>
                    <ProgressBar value={progress.completed / progress.total} />
                    <div className={styles.progressInfo}>
                        <Text size={300} weight="semibold">
                            {progress.completed}/{progress.total} — {progress.strategy}
                        </Text>
                        <Text size={200} className={styles.progressQuestion}>
                            {progress.question}
                        </Text>
                    </div>
                    {progress.status === "throttled" && (
                        <div className={styles.throttleWarning}>
                            <Text size={200}>Rate limited — waiting for API quota to reset...</Text>
                        </div>
                    )}
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
