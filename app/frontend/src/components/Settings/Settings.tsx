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
    queryTransform: string;
    decompose: boolean;
    temperature: number;
    topK: number;
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
                <Label weight="semibold">Settings</Label>
            </div>

            <div className={styles.field}>
                <Label size="small">Search Strategy</Label>
                <Dropdown
                    value={settings.searchStrategy}
                    selectedOptions={[settings.searchStrategy]}
                    onOptionSelect={(_, data) =>
                        onChange({ ...settings, searchStrategy: data.optionValue! })
                    }
                >
                    <Option value="hybrid">Hybrid (BM25 + Vector)</Option>
                    <Option value="bm25">BM25 (Keyword)</Option>
                    <Option value="vector">Vector (Semantic)</Option>
                </Dropdown>
            </div>

            <div className={styles.field}>
                <Label size="small">Query Transform</Label>
                <Dropdown
                    value={settings.queryTransform}
                    selectedOptions={[settings.queryTransform]}
                    onOptionSelect={(_, data) =>
                        onChange({ ...settings, queryTransform: data.optionValue! })
                    }
                >
                    <Option value="none">None</Option>
                    <Option value="rewrite">Query Rewrite</Option>
                    <Option value="hyde">HyDE</Option>
                </Dropdown>
            </div>

            <div className={styles.field}>
                <Switch
                    label="Query Decomposition"
                    checked={settings.decompose}
                    onChange={(_, data) =>
                        onChange({ ...settings, decompose: data.checked })
                    }
                />
            </div>

            <div className={styles.field}>
                <Label size="small">
                    Temperature: {settings.temperature.toFixed(1)}
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
                <Label size="small">RAG Approach</Label>
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
