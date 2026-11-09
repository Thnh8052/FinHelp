import React, { useState } from "react";
import { BrowserRouter, Routes, Route, useNavigate, Navigate } from "react-router-dom";
import { LandingPage } from "./features/landing/LandingPage";
import { Workspace } from "./features/workspace/Workspace";
import { NotebookHub } from "./features/hub/NotebookHub";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { AuthModal } from "./components/auth/AuthModal";
import { useAuth } from "./context/AuthContext";
import "./App.css";

/** /app: trang Hub cho người dùng đã đăng nhập, workspace dùng thử cho khách. */
const AppHome: React.FC<{ onNavigateHome: () => void }> = ({ onNavigateHome }) => {
  const { user, token, isAuthenticated } = useAuth();
  if (token && !user) return null;  // the saved token is still being checked
  return isAuthenticated ? <NotebookHub onNavigateHome={onNavigateHome} /> : <Workspace onNavigateHome={onNavigateHome} />;
};

const AppRoutes: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const isAuthenticated = !!user;

  const handleOpenAuth = (_mode: "login" | "register") => {
    setAuthModalOpen(true);
  };

  const handleEnterApp = () => {
    navigate("/app");
  };

  const handleNavigateHome = () => {
    navigate("/");
  };

  return (
    <>
      <Routes>
        {/* Landing Page (Official FinHelp Overview) */}
        <Route
          path="/"
          element={
            <LandingPage
              onEnterApp={handleEnterApp}
              onOpenAuth={handleOpenAuth}
              isAuthenticated={isAuthenticated}
            />
          }
        />

        {/* Workspace 4-Zone Workstation (Financial Report Intelligence) */}
        <Route path="/app" element={<AppHome onNavigateHome={handleNavigateHome} />} />
        <Route path="/app/:notebookId" element={<Workspace onNavigateHome={handleNavigateHome} />} />

        {/* Dedicated Standalone Auth Pages (Email verification / Direct URL) */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/forgot-password" element={<ResetPasswordPage />} />

        {/* Redirect non-matching routes to root */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Global Auth Modal for Landing Page */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
};

export default App;
