import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { Chat } from "./pages/chat/Chat";
import { Evaluation } from "./pages/evaluation/Evaluation";
import { Login } from "./components/Login/Login";
import "./index.css";

const App = () => {
    const [authenticated, setAuthenticated] = useState(
        () => !!sessionStorage.getItem("auth_password")
    );

    if (!authenticated) {
        return <Login onLogin={() => setAuthenticated(true)} />;
    }

    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<Chat />} />
                <Route path="/evaluation" element={<Evaluation />} />
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
