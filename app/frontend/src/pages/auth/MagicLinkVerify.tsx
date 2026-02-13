import { Spinner, Text, Title1 } from "@fluentui/react-components";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { type AuthUser, verifyCode } from "../../api/api";

interface Props {
    onLogin: (user: AuthUser) => void;
}

export const MagicLinkVerify = ({ onLogin }: Props) => {
    const [searchParams] = useSearchParams();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const token = searchParams.get("token");
        const email = searchParams.get("email");

        if (!token || !email) {
            setError("Invalid magic link.");
            return;
        }

        verifyCode(email, undefined, token)
            .then((result) => {
                sessionStorage.setItem("auth_token", result.token);
                onLogin({ email, role: result.role as "admin" | "viewer" });
                window.location.href = "/";
            })
            .catch((err) => {
                setError(err instanceof Error ? err.message : "Verification failed");
            });
    }, [searchParams, onLogin]);

    return (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
            <div style={{ textAlign: "center" }}>
                {error ? (
                    <>
                        <Title1>Verification Failed</Title1>
                        <Text style={{ display: "block", marginTop: 8 }}>{error}</Text>
                    </>
                ) : (
                    <>
                        <Spinner size="large" label="Verifying..." />
                    </>
                )}
            </div>
        </div>
    );
};
