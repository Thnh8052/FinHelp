import React from "react";
import { Route, Routes } from "react-router-dom";
import { AdminLayout } from "./AdminLayout";
import { AuditPage } from "./AuditPage";
import { DocumentsPage } from "./DocumentsPage";
import { OverviewPage } from "./OverviewPage";
import { TokensPage } from "./TokensPage";
import { UsersPage } from "./UsersPage";

/** Everything under /admin, loaded as its own chunk: members and guests never download the chart library. */
const AdminRoutes: React.FC = () => (
  <Routes>
    <Route element={<AdminLayout />}>
      <Route index element={<OverviewPage />} />
      <Route path="documents" element={<DocumentsPage />} />
      <Route path="audit" element={<AuditPage />} />
      <Route path="tokens" element={<TokensPage />} />
      <Route path="users" element={<UsersPage />} />
    </Route>
  </Routes>
);

export default AdminRoutes;
