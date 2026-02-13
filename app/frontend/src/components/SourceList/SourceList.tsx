import { Link, Text } from "@fluentui/react-components";
import { Open16Regular } from "@fluentui/react-icons";
import type { NormReference } from "../../api/api";
import styles from "./SourceList.module.css";

interface Props {
    sources: NormReference[];
    onSourceClick?: (source: NormReference) => void;
}

export const SourceList = ({ sources, onSourceClick }: Props) => {
    if (sources.length === 0) return null;

    return (
        <div className={styles.container}>
            <Text weight="semibold" size={200}>
                Quellen
            </Text>
            <div className={styles.list}>
                {sources.map((source, i) => (
                    <div
                        key={source.norm_id}
                        className={styles.source}
                        onClick={() => onSourceClick?.(source)}
                    >
                        <Text size={200} weight="semibold">
                            [{i + 1}] §{source.paragraph} BGB
                        </Text>
                        {source.titel && (
                            <Text size={200} className={styles.titel}>
                                {source.titel}
                            </Text>
                        )}
                        <Link
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <Open16Regular /> gesetze-im-internet.de
                        </Link>
                    </div>
                ))}
            </div>
        </div>
    );
};
