import {
    Dropdown,
    Label,
    Option,
    Slider,
    Switch,
} from "@fluentui/react-components";
import { Settings24Regular } from "@fluentui/react-icons";
import styles from "./Settings.module.css";

export interface SettingsState {
    searchStrategy: string;
    temperature: number;
    topK: number;
    useSemanticRanker: boolean;
    approach: string;
}

interface Props {
    settings: SettingsState;
    onChange: (settings: SettingsState) => void;
}

export const Settings = ({ settings, onChange }: Props) => {
    return (
        <div className={styles.container}>
            <div className={styles.header}>
                <Settings24Regular />
                <Label weight="semibold">Einstellungen</Label>
            </div>

            <div className={styles.field}>
                <Label size="small">Suchstrategie</Label>
                <Dropdown
                    value={settings.searchStrategy}
                    selectedOptions={[settings.searchStrategy]}
                    onOptionSelect={(_, data) =>
                        onChange({ ...settings, searchStrategy: data.optionValue! })
                    }
                >
                    <Option value="hybrid">Hybrid (BM25 + Vektor)</Option>
                    <Option value="bm25">BM25 (Keyword)</Option>
                    <Option value="vector">Vektor (Semantisch)</Option>
                </Dropdown>
            </div>

            <div className={styles.field}>
                <Label size="small">
                    Temperatur: {settings.temperature.toFixed(1)}
                </Label>
                <Slider
                    min={0}
                    max={1}
                    step={0.1}
                    value={settings.temperature}
                    onChange={(_, data) =>
                        onChange({ ...settings, temperature: data.value })
                    }
                />
            </div>

            <div className={styles.field}>
                <Label size="small">Top K: {settings.topK}</Label>
                <Slider
                    min={1}
                    max={20}
                    step={1}
                    value={settings.topK}
                    onChange={(_, data) =>
                        onChange({ ...settings, topK: data.value })
                    }
                />
            </div>

            <div className={styles.field}>
                <Switch
                    checked={settings.useSemanticRanker}
                    onChange={(_, data) =>
                        onChange({ ...settings, useSemanticRanker: data.checked })
                    }
                    label="Semantic Ranker (Standard tier)"
                />
            </div>

            <div className={styles.field}>
                <Label size="small">RAG Ansatz</Label>
                <Dropdown
                    value={settings.approach}
                    selectedOptions={[settings.approach]}
                    onOptionSelect={(_, data) =>
                        onChange({ ...settings, approach: data.optionValue! })
                    }
                >
                    <Option value="custom">Custom (Azure SDK)</Option>
                    <Option value="langchain">LangChain (LCEL)</Option>
                </Dropdown>
            </div>
        </div>
    );
};
