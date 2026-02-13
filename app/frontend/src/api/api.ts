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
    temperature?: number;
    top_k?: number;
    use_semantic_ranker?: boolean;
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
    use_semantic_ranker: boolean;
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

function getAuthHeaders(): HeadersInit {
    const username = sessionStorage.getItem("auth_username") || "";
    const password = sessionStorage.getItem("auth_password") || "";
    if (!username && !password) return {};
    return {
        Authorization: "Basic " + btoa(`${username}:${password}`),
    };
}

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
        if (response.status === 401) throw new Error("Authentication required");
        throw new Error(`Chat request failed: ${response.statusText}`);
    }
    return response.json();
}

export async function getConfig(): Promise<AppConfig> {
    const response = await fetch("/config", {
        headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to fetch config");
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
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "Evaluation failed");
    }
}

export async function getEvalStatus(): Promise<EvalStatusResponse> {
    const response = await fetch("/evaluate/status", {
        headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error("Failed to fetch evaluation status");
    return response.json();
}
