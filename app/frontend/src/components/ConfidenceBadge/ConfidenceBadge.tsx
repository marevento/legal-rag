import { Badge } from "@fluentui/react-components";

interface Props {
    confidence: "high" | "medium" | "low";
}

const COLORS: Record<string, "success" | "warning" | "danger"> = {
    high: "success",
    medium: "warning",
    low: "danger",
};

const LABELS: Record<string, string> = {
    high: "Hohe Sicherheit",
    medium: "Mittlere Sicherheit",
    low: "Geringe Sicherheit",
};

export const ConfidenceBadge = ({ confidence }: Props) => (
    <Badge color={COLORS[confidence]} appearance="filled" size="small">
        {LABELS[confidence]}
    </Badge>
);
