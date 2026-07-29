import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Dashboard } from "./features/admin/Dashboard";
import { DocDetail } from "./features/admin/DocDetail";
import { UploadWizard } from "./features/admin/UploadWizard";
import { LibraryPage } from "./features/library/LibraryPage";
import { ReaderPage } from "./features/reader/ReaderPage";
import { ScorePage } from "./features/score/ScorePage";
import { HomePage } from "./pages/HomePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />

        <Route path="/admin" element={<Dashboard />} />
        <Route path="/admin/upload" element={<UploadWizard />} />
        <Route path="/admin/docs/:docId" element={<DocDetail />} />

        <Route path="/users" element={<LibraryPage />} />
        <Route path="/users/read/:docId" element={<ReaderPage />} />
        <Route path="/users/score" element={<ScorePage />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
