export interface ChatMessage {
    role: "user" | "assistant" | "system";
    content: string;
}

export interface NormReference {
    norm_id: string;
    paragraph: string;
    titel: string;
    text: string;
    url: string;
    relevance_score: number;
}

export interface ChatRequest {
    messages: ChatMessage[];
    search_strategy?: string;
    query_transform?: string;
    decompose?: boolean;
    temperature?: number;
    top_k?: number;
    approach?: string;
}

export interface ChatResponse {
    answer: string;
    sources: NormReference[];
    confidence: "high" | "medium" | "low";
    search_strategy: string;
    approach: string;
}

export interface AppConfig {
    search_strategy: string;
    temperature: number;
    top_k: number;
    approach: string;
}

export interface RetrievalMetrics {
    recall_at_k: number;
    precision_at_k: number;
    k: number;
}

export interface GenerationMetrics {
    groundedness_score: number;
    citation_accuracy: number;
    confidence: string;
}

export interface EvalResult {
    question: string;
    category: string;
    retrieval: RetrievalMetrics;
    generation: GenerationMetrics;
    search_strategy: string;
    latency_ms: number;
}

export interface StrategyComparison {
    strategy: string;
    avg_recall_at_5: number;
    avg_precision_at_5: number;
    avg_groundedness: number;
    avg_citation_accuracy: number;
    avg_latency_ms: number;
}

export interface PatternRecommendation {
    pattern: string;
    signal: string;
    metric_name: string;
    current_value: number;
    threshold: number;
    recommended: boolean;
    explanation: string;
}

export interface MetricsReport {
    results: EvalResult[];
    strategy_comparisons: StrategyComparison[];
    pattern_recommendations: PatternRecommendation[];
    results_by_category: Record<string, EvalResult[]>;
}

export interface AuthUser {
    email: string;
    role: "admin" | "viewer";
}

// --- Auth helpers ---

function getAuthHeaders(): HeadersInit {
    const token = sessionStorage.getItem("auth_token");
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
}

function handleAuthError(response: Response): void {
    if (response.status === 401) {
        sessionStorage.removeItem("auth_token");
        window.location.reload();
    }
}

export function getStoredUser(): AuthUser | null {
    const token = sessionStorage.getItem("auth_token");
    if (!token) return null;
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        if (payload.exp * 1000 < Date.now()) {
            sessionStorage.removeItem("auth_token");
            return null;
        }
        return { email: payload.sub, role: payload.role };
    } catch {
        sessionStorage.removeItem("auth_token");
        return null;
    }
}

export function logout(): void {
    sessionStorage.removeItem("auth_token");
    window.location.reload();
}

// --- Auth API ---

export async function requestAccess(email: string): Promise<void> {
    const res = await fetch("/auth/request-access", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
    });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Failed to send access code");
    }
}

export async function verifyCode(
    email: string,
    code?: string,
    token?: string,
): Promise<{ token: string; role: string }> {
    const res = await fetch("/auth/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code, token }),
    });
    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Verification failed");
    }
    return res.json();
}

// --- Admin API ---

export interface UsageUser {
    email: string;
    count: number;
    first_seen: number;
    last_seen: number;
}

export interface DailyCount {
    day: string;
    count: number;
}

export interface DistributionItem {
    strategy?: string;
    confidence?: string;
    count: number;
}

export interface RecentQuery {
    timestamp: number;
    user_email: string;
    query: string;
    search_strategy: string;
    confidence: string;
    citation_count: number;
    latency_ms: number | null;
}

export interface UsageStats {
    total_requests: number;
    total_chat_queries: number;
    users: UsageUser[];
    daily_queries: DailyCount[];
    strategy_distribution: DistributionItem[];
    confidence_distribution: DistributionItem[];
    avg_latency_ms: number | null;
    recent_queries: RecentQuery[];
}

export async function getUsageStats(): Promise<UsageStats> {
    const response = await fetch("/admin/usage", {
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        handleAuthError(response);
        throw new Error("Failed to fetch usage stats");
    }
    return response.json();
}

// --- App API ---

export async function chatApi(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...getAuthHeaders(),
        },
        body: JSON.stringify(request),
    });
    if (!response.ok) {
        handleAuthError(response);
        throw new Error(`Chat request failed: ${response.statusText}`);
    }
    return response.json();
}

export async function getConfig(): Promise<AppConfig> {
    const response = await fetch("/config", {
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        handleAuthError(response);
        throw new Error("Failed to fetch config");
    }
    return response.json();
}

export interface EvalProgressData {
    completed: number;
    total: number;
    strategy: string;
    question: string;
    status: "running" | "throttled";
}

export interface EvalStatusResponse {
    running: boolean;
    progress: EvalProgressData | null;
    report: MetricsReport | null;
}

export async function startEvaluation(
    strategies?: string[],
    topK?: number
): Promise<void> {
    const response = await fetch("/evaluate", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...getAuthHeaders(),
        },
        body: JSON.stringify({ strategies, top_k: topK }),
    });
    if (!response.ok) {
        handleAuthError(response);
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "Evaluation failed");
    }
}

export async function getEvalStatus(): Promise<EvalStatusResponse> {
    const response = await fetch("/evaluate/status", {
        headers: getAuthHeaders(),
    });
    if (!response.ok) {
        handleAuthError(response);
        throw new Error("Failed to fetch evaluation status");
    }
    return response.json();
}
