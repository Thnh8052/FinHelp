import React, { useState } from "react";
import { BrowserRouter, Routes, Route, useNavigate, Navigate } from "react-router-dom";
import { LandingPage } from "./features/landing/LandingPage";
import { Workspace } from "./features/workspace/Workspace";
import { AuthModal } from "./components/auth/AuthModal";
import { useAuth } from "./context/AuthContext";
import "./App.css";

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
        {/* Landing Page (Trang giới thiệu chính thức của FinHelp) */}
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

        {/* Workspace 4-Zone Workstation (Không gian phân tích báo cáo tài chính) */}
        <Route
          path="/app"
          element={<Workspace onNavigateHome={handleNavigateHome} />}
        />

        {/* Tiện ích mở thẳng popup auth từ URL */}
        <Route
          path="/login"
          element={
            <LandingPage
              onEnterApp={handleEnterApp}
              onOpenAuth={handleOpenAuth}
              isAuthenticated={isAuthenticated}
            />
          }
        />
        <Route
          path="/register"
          element={
            <LandingPage
              onEnterApp={handleEnterApp}
              onOpenAuth={handleOpenAuth}
              isAuthenticated={isAuthenticated}
            />
          }
        />

        {/* Redirect mọi route không khớp về trang chủ */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Global Auth Modal cho Landing Page */}
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
