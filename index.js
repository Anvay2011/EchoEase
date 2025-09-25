import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";  // 👈 important

const root = createRoot(document.getElementById("root"));
root.render(<App />);
