import { Routes, Route } from "react-router-dom";

import { HomePage } from "../pages/HomePage";
import { ObjViewerPage } from "../pages/ObjViewerPage";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/viewer/obj" element={<ObjViewerPage />} />
    </Routes>
  );
}
