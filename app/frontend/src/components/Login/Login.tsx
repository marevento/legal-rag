import { Button, Input, Label, Title1, Text } from "@fluentui/react-components";
import { useState } from "react";
import { type AuthUser, requestAccess, verifyCode } from "../../api/api";
import styles from "./Login.module.css";

interface Props {
    onLogin: (user: AuthUser) => void;
}

export const Login = ({ onLogin }: Props) => {
    const [email, setEmail] = useState("");
    const [code, setCode] = useState("");
    const [step, setStep] = useState<"email" | "code">("email");
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const handleRequestAccess = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            await requestAccess(email);
            setStep("code");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to send code");
        } finally {
            setLoading(false);
        }
    };

    const handleVerify = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            const result = await verifyCode(email, code);
            sessionStorage.setItem("auth_token", result.token);
            onLogin({ email, role: result.role as "admin" | "viewer" });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Verification failed");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.container}>
            {step === "email" ? (
                <form className={styles.form} onSubmit={handleRequestAccess}>
                    <Title1>Mietrecht Assistent</Title1>
                    <Text size={300}>
                        Enter your email to receive an access code.
                    </Text>

                    <div className={styles.field}>
                        <Label htmlFor="email">Email</Label>
                        <Input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(_, d) => setEmail(d.value)}
                            required
                        />
                    </div>

                    {error && <Text className={styles.error}>{error}</Text>}

                    <Button appearance="primary" type="submit" disabled={loading}>
                        {loading ? "Sending..." : "Send Access Code"}
                    </Button>
                </form>
            ) : (
                <form className={styles.form} onSubmit={handleVerify}>
                    <Title1>Check Your Email</Title1>
                    <Text size={300}>
                        We sent a 6-digit code to <strong>{email}</strong>.
                    </Text>

                    <div className={styles.field}>
                        <Label htmlFor="code">Access Code</Label>
                        <Input
                            id="code"
                            value={code}
                            onChange={(_, d) => setCode(d.value)}
                            placeholder="123456"
                            maxLength={6}
                            required
                        />
                    </div>

                    {error && <Text className={styles.error}>{error}</Text>}

                    <Button appearance="primary" type="submit" disabled={loading}>
                        {loading ? "Verifying..." : "Verify"}
                    </Button>

                    <Button
                        appearance="subtle"
                        onClick={() => {
                            setStep("email");
                            setCode("");
                            setError(null);
                        }}
                    >
                        Use a different email
                    </Button>
                </form>
            )}
        </div>
    );
};
