import { Button, Textarea } from "@fluentui/react-components";
import { Send24Regular } from "@fluentui/react-icons";
import { useState } from "react";
import styles from "./QuestionInput.module.css";

interface Props {
    onSend: (question: string) => void;
    disabled: boolean;
    placeholder?: string;
}

const EXAMPLE_QUESTIONS = [
    "Was ist bei der Mietkaution zu beachten?",
    "Wann darf die Miete erhöht werden und welche Grenzen gelten?",
    "Was passiert bei einem Eigentümerwechsel?",
];

export const QuestionInput = ({ onSend, disabled, placeholder }: Props) => {
    const [question, setQuestion] = useState("");

    const handleSend = () => {
        if (question.trim() && !disabled) {
            onSend(question.trim());
            setQuestion("");
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className={styles.container}>
            <div className={styles.examples}>
                {EXAMPLE_QUESTIONS.map((q) => (
                    <Button
                        key={q}
                        size="small"
                        appearance="outline"
                        onClick={() => onSend(q)}
                        disabled={disabled}
                    >
                        {q}
                    </Button>
                ))}
            </div>
            <div className={styles.inputRow}>
                <Textarea
                    className={styles.input}
                    value={question}
                    onChange={(_, data) => setQuestion(data.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder || "Stellen Sie eine Frage zum Mietrecht..."}
                    disabled={disabled}
                    resize="vertical"
                />
                <Button
                    icon={<Send24Regular />}
                    appearance="primary"
                    onClick={handleSend}
                    disabled={disabled || !question.trim()}
                />
            </div>
        </div>
    );
};
