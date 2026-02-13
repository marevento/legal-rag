import { Button, Input, Label, Title1, Text } from "@fluentui/react-components";
import { useState } from "react";
import styles from "./Login.module.css";

interface Props {
    onLogin: () => void;
}

export const Login = ({ onLogin }: Props) => {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        // Test credentials against the health endpoint
        const response = await fetch("/config", {
            headers: {
                Authorization: "Basic " + btoa(`${username}:${password}`),
            },
        });

        if (response.ok) {
            sessionStorage.setItem("auth_username", username);
            sessionStorage.setItem("auth_password", password);
            onLogin();
        } else {
            setError("Invalid credentials");
        }
    };

    return (
        <div className={styles.container}>
            <form className={styles.form} onSubmit={handleSubmit}>
                <Title1>Mietrecht Assistent</Title1>
                <Text size={300}>Login to access the legal RAG system</Text>

                <div className={styles.field}>
                    <Label htmlFor="username">Username</Label>
                    <Input id="username" value={username} onChange={(_, d) => setUsername(d.value)} />
                </div>

                <div className={styles.field}>
                    <Label htmlFor="password">Password</Label>
                    <Input id="password" type="password" value={password} onChange={(_, d) => setPassword(d.value)} />
                </div>

                {error && <Text className={styles.error}>{error}</Text>}

                <Button appearance="primary" type="submit">
                    Login
                </Button>
            </form>
        </div>
    );
};
