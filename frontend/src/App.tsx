import React, { useState } from "react";
import { BrowserRouter, Routes, Route, useNavigate, Navigate } from "react-router-dom";
import { LandingPage } from "./features/landing/LandingPage";
import { Workspace } from "./features/workspace/Workspace";
import { LoginPage } from "./features/auth/LoginPage";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ResetPasswordPage } from "./features/auth/ResetPasswordPage";
import { AuthModal } from "./components/auth/AuthModal";
import { useAuth } from "./context/AuthContext";
import "./App.css";

/** /app và /app/:notebookId: một giao diện chat cho cả thành viên (nhiều đoạn chat) lẫn khách (một đoạn chat dùng thử). */
const AppHome: React.FC<{ onNavigateHome: () => void }> = ({ onNavigateHome }) => {
  const { user, hasSession, isLoading } = useAuth();
  // The session is still being checked. Not while a sign-in runs (hasSession is set only once it succeeded: the sign-in box stays to
  // show a wrong password), and not after a check that failed on the network (the session is kept for the next load: guest view now)
  if (hasSession && !user && isLoading) return null;
  return <Workspace onNavigateHome={onNavigateHome} />;
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
        <Route path="/app/:notebookId?" element={<AppHome onNavigateHome={handleNavigateHome} />} />

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
