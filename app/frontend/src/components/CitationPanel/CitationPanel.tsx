import {
    DrawerBody,
    DrawerHeader,
    DrawerHeaderTitle,
    Link,
    OverlayDrawer,
    Text,
} from "@fluentui/react-components";
import { Dismiss24Regular, Open16Regular } from "@fluentui/react-icons";
import type { NormReference } from "../../api/api";
import styles from "./CitationPanel.module.css";

interface Props {
    source: NormReference | null;
    open: boolean;
    onClose: () => void;
}

export const CitationPanel = ({ source, open, onClose }: Props) => {
    if (!source) return null;

    return (
        <OverlayDrawer open={open} onOpenChange={(_, { open }) => !open && onClose()} position="end" size="medium">
            <DrawerHeader>
                <DrawerHeaderTitle
                    action={
                        <button onClick={onClose} className={styles.closeButton}>
                            <Dismiss24Regular />
                        </button>
                    }
                >
                    §{source.paragraph} BGB
                </DrawerHeaderTitle>
            </DrawerHeader>
            <DrawerBody>
                <div className={styles.content}>
                    {source.titel && (
                        <Text size={400} weight="semibold" block>
                            {source.titel}
                        </Text>
                    )}

                    <div className={styles.normText}>
                        <Text size={300}>{source.text}</Text>
                    </div>

                    <div className={styles.meta}>
                        <Link href={source.url} target="_blank" rel="noopener noreferrer">
                            <Open16Regular /> Volltext auf gesetze-im-internet.de
                        </Link>
                        {source.relevance_score > 0 && (
                            <Text size={200} className={styles.score}>
                                Relevanz: {(source.relevance_score * 100).toFixed(1)}%
                            </Text>
                        )}
                    </div>
                </div>
            </DrawerBody>
        </OverlayDrawer>
    );
};
