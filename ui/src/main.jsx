import React from "react";
import { createRoot } from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import Layout from "./Layout.jsx";
import Home from "./pages/Home.jsx";
import Demo from "./pages/Demo.jsx";
import About from "./pages/About.jsx";
import Docs from "./pages/Docs.jsx";
import "./styles.css";

// HashRouter so the site works as a static export (GitHub Pages / file open) too.
const router = createHashRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: "demo", element: <Demo /> },
      { path: "about", element: <About /> },
      { path: "docs", element: <Docs /> },
    ],
  },
]);

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
