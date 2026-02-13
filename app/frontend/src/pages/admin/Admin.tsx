import { Button, Spinner, Text, Title1, Title3 } from "@fluentui/react-components";
import { ArrowLeft24Regular } from "@fluentui/react-icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Line,
    LineChart,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import { type UsageStats, getUsageStats } from "../../api/api";
import styles from "./Admin.module.css";

const COLORS = ["#0078d4", "#00a86b", "#e3730c", "#d13438", "#8764b8"];

export const Admin = () => {
    const navigate = useNavigate();
    const [stats, setStats] = useState<UsageStats | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        getUsageStats()
            .then(setStats)
            .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
    }, []);

    if (error) {
        return (
            <div className={styles.container}>
                <div className={styles.error}><Text>{error}</Text></div>
            </div>
        );
    }

    if (!stats) {
        return (
            <div className={styles.container}>
                <Spinner size="large" label="Loading usage data..." />
            </div>
        );
    }

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
                <Title1>Usage Analytics</Title1>
            </div>

            <div className={styles.stats}>
                <div className={styles.statCard}>
                    <Text size={200}>Total Requests</Text>
                    <div className={styles.statValue}>{stats.total_requests}</div>
                </div>
                <div className={styles.statCard}>
                    <Text size={200}>Chat Queries</Text>
                    <div className={styles.statValue}>{stats.total_chat_queries}</div>
                </div>
                <div className={styles.statCard}>
                    <Text size={200}>Unique Users</Text>
                    <div className={styles.statValue}>{stats.users.length}</div>
                </div>
                <div className={styles.statCard}>
                    <Text size={200}>Avg Latency</Text>
                    <div className={styles.statValue}>
                        {stats.avg_latency_ms ? `${Math.round(stats.avg_latency_ms)}ms` : "—"}
                    </div>
                </div>
            </div>

            <div className={styles.charts}>
                {stats.daily_queries.length > 0 && (
                    <div className={styles.chartCard}>
                        <Title3>Queries / Day</Title3>
                        <ResponsiveContainer width="100%" height={200}>
                            <LineChart data={stats.daily_queries}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                                <YAxis allowDecimals={false} />
                                <Tooltip />
                                <Line type="monotone" dataKey="count" stroke="#0078d4" strokeWidth={2} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                )}

                {stats.users.length > 0 && (
                    <div className={styles.chartCard}>
                        <Title3>Queries / User</Title3>
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={stats.users}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="email" tick={{ fontSize: 11 }} />
                                <YAxis allowDecimals={false} />
                                <Tooltip />
                                <Bar dataKey="count" fill="#0078d4" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                )}

                {stats.strategy_distribution.length > 0 && (
                    <div className={styles.chartCard}>
                        <Title3>Search Strategy</Title3>
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={stats.strategy_distribution}
                                    dataKey="count"
                                    nameKey="strategy"
                                    cx="50%"
                                    cy="50%"
                                    outerRadius={70}
                                    label={({ strategy, count }) => `${strategy}: ${count}`}
                                >
                                    {stats.strategy_distribution.map((_, i) => (
                                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                )}

                {stats.confidence_distribution.length > 0 && (
                    <div className={styles.chartCard}>
                        <Title3>Confidence</Title3>
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie
                                    data={stats.confidence_distribution}
                                    dataKey="count"
                                    nameKey="confidence"
                                    cx="50%"
                                    cy="50%"
                                    outerRadius={70}
                                    label={({ confidence, count }) => `${confidence}: ${count}`}
                                >
                                    {stats.confidence_distribution.map((_, i) => (
                                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>

            {stats.recent_queries.length > 0 && (
                <>
                    <Title3>Recent Queries</Title3>
                    <table className={styles.table}>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>User</th>
                                <th>Query</th>
                                <th>Strategy</th>
                                <th>Confidence</th>
                                <th>Citations</th>
                                <th>Latency</th>
                            </tr>
                        </thead>
                        <tbody>
                            {stats.recent_queries.map((q, i) => (
                                <tr key={i}>
                                    <td>{new Date(q.timestamp * 1000).toLocaleString()}</td>
                                    <td>{q.user_email}</td>
                                    <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                        {q.query}
                                    </td>
                                    <td>{q.search_strategy}</td>
                                    <td>{q.confidence}</td>
                                    <td>{q.citation_count}</td>
                                    <td>{q.latency_ms ? `${Math.round(q.latency_ms)}ms` : "—"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </>
            )}
        </div>
    );
};
