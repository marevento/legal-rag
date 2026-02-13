import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { type AuthUser, getStoredUser } from "./api/api";
import { Login } from "./components/Login/Login";
import { MagicLinkVerify } from "./pages/auth/MagicLinkVerify";
import { Admin } from "./pages/admin/Admin";
import { Chat } from "./pages/chat/Chat";
import { Evaluation } from "./pages/evaluation/Evaluation";
import "./index.css";

const App = () => {
    const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());

    if (!user) {
        return (
            <BrowserRouter>
                <Routes>
                    <Route
                        path="/auth/verify"
                        element={<MagicLinkVerify onLogin={setUser} />}
                    />
                    <Route path="*" element={<Login onLogin={setUser} />} />
                </Routes>
            </BrowserRouter>
        );
    }

    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Chat user={user} />} />
                <Route path="/evaluation" element={<Evaluation user={user} />} />
                {user.role === "admin" && (
                    <Route path="/admin" element={<Admin />} />
                )}
                <Route path="/auth/verify" element={<MagicLinkVerify onLogin={setUser} />} />
            </Routes>
        </BrowserRouter>
    );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <FluentProvider theme={webLightTheme}>
            <App />
        </FluentProvider>
    </React.StrictMode>
);
