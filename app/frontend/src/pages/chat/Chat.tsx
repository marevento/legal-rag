import { Button, Spinner, Text, Title1 } from "@fluentui/react-components";
import { DataBarVertical24Regular } from "@fluentui/react-icons";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { type ChatResponse, type NormReference, chatApi } from "../../api/api";
import { Answer } from "../../components/Answer/Answer";
import { CitationPanel } from "../../components/CitationPanel/CitationPanel";
import { QuestionInput } from "../../components/QuestionInput/QuestionInput";
import { Settings, type SettingsState } from "../../components/Settings/Settings";
import styles from "./Chat.module.css";

interface Message {
    role: "user" | "assistant";
    content: string;
    response?: ChatResponse;
}

export const Chat = () => {
    const navigate = useNavigate();
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedSource, setSelectedSource] = useState<NormReference | null>(null);
    const [panelOpen, setPanelOpen] = useState(false);

    const [settings, setSettings] = useState<SettingsState>({
        searchStrategy: "hybrid",
        temperature: 0,
        topK: 5,
        useSemanticRanker: false,
        approach: "custom",
    });

    const handleSend = useCallback(
        async (question: string) => {
            setError(null);
            const userMessage: Message = { role: "user", content: question };
            setMessages((prev) => [...prev, userMessage]);
            setIsLoading(true);

            try {
                const response = await chatApi({
                    messages: [{ role: "user", content: question }],
                    search_strategy: settings.searchStrategy,
                    temperature: settings.temperature,
                    top_k: settings.topK,
                    use_semantic_ranker: settings.useSemanticRanker,
                    approach: settings.approach,
                });

                const assistantMessage: Message = {
                    role: "assistant",
                    content: response.answer,
                    response,
                };
                setMessages((prev) => [...prev, assistantMessage]);
            } catch (e) {
                setError(e instanceof Error ? e.message : "An error occurred");
            } finally {
                setIsLoading(false);
            }
        },
        [settings]
    );

    const handleSourceClick = (source: NormReference) => {
        setSelectedSource(source);
        setPanelOpen(true);
    };

    return (
        <div className={styles.layout}>
            <div className={styles.sidebar}>
                <Settings settings={settings} onChange={setSettings} />
                <Button
                    appearance="subtle"
                    icon={<DataBarVertical24Regular />}
                    onClick={() => navigate("/evaluation")}
                >
                    Evaluation Dashboard
                </Button>
            </div>

            <div className={styles.main}>
                <div className={styles.header}>
                    <Title1>Mietrecht Assistent</Title1>
                    <Text size={300}>
                        RAG-basierte Auskunft zu deutschem Mietrecht (BGB §§535-580a)
                    </Text>
                </div>

                <div className={styles.messages}>
                    {messages.map((msg, i) => (
                        <div key={i} className={msg.role === "user" ? styles.userMessage : styles.assistantMessage}>
                            {msg.role === "user" ? (
                                <div className={styles.userBubble}>
                                    <Text>{msg.content}</Text>
                                </div>
                            ) : msg.response ? (
                                <Answer response={msg.response} onSourceClick={handleSourceClick} />
                            ) : (
                                <Text>{msg.content}</Text>
                            )}
                        </div>
                    ))}
                    {isLoading && (
                        <div className={styles.loading}>
                            <Spinner size="small" label="Analysiere Mietrecht-Normen..." />
                        </div>
                    )}
                    {error && (
                        <div className={styles.error}>
                            <Text>{error}</Text>
                        </div>
                    )}
                </div>

                <QuestionInput onSend={handleSend} disabled={isLoading} />
            </div>

            <CitationPanel
                source={selectedSource}
                open={panelOpen}
                onClose={() => setPanelOpen(false)}
            />
        </div>
    );
};
