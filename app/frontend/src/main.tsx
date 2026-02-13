import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { Chat } from "./pages/chat/Chat";
import { Evaluation } from "./pages/evaluation/Evaluation";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <FluentProvider theme={webLightTheme}>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Chat />} />
                    <Route path="/evaluation" element={<Evaluation />} />
                </Routes>
            </BrowserRouter>
        </FluentProvider>
    </React.StrictMode>
);
