import { Text } from "@fluentui/react-components";
import type { ChatResponse, NormReference } from "../../api/api";
import { ConfidenceBadge } from "../ConfidenceBadge/ConfidenceBadge";
import { SourceList } from "../SourceList/SourceList";
import styles from "./Answer.module.css";

interface Props {
    response: ChatResponse;
    onSourceClick: (source: NormReference) => void;
}

export const Answer = ({ response, onSourceClick }: Props) => {
    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <ConfidenceBadge confidence={response.confidence} />
                <Text size={100} className={styles.meta}>
                    {response.search_strategy} | {response.approach}
                </Text>
            </div>
            <div className={styles.answer}>
                <Text size={300}>{response.answer}</Text>
            </div>
            <SourceList sources={response.sources} onSourceClick={onSourceClick} />
        </div>
    );
};
