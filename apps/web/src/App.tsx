import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import Landing from "@/pages/Landing";
import Overview from "@/pages/Overview";
import Library from "@/pages/Library";
import DocumentReview from "@/pages/DocumentReview";
import Rules from "@/pages/Rules";
import Impact from "@/pages/Impact";
import Approvals from "@/pages/Approvals";
import Evidence from "@/pages/Evidence";
import SettingsPage from "@/pages/Settings";
import { EmptyState } from "@/components/States";

export default function App() {
  return (
    <Routes>
      <Route index element={<Landing />} />
      <Route element={<AppShell />}>
        <Route path="overview" element={<Overview />} />
        <Route path="library" element={<Library />} />
        <Route path="library/:documentId" element={<DocumentReview />} />
        <Route path="rules" element={<Rules />} />
        <Route path="impact" element={<Impact />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="evidence" element={<Evidence />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<EmptyState title="Page not found" hint="Use the navigation on the left." />} />
      </Route>
    </Routes>
  );
}
