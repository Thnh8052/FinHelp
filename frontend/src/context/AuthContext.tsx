import React, { createContext, useContext, useEffect, useState } from "react";
import { ApiError } from "../services/api";
import { authService } from "../services/auth";
import { GuestQuota, UserProfile } from "../types/auth";

interface AuthContextType {
  user: UserProfile | null;
  hasSession: boolean;
  isAuthenticated: boolean;
  isGuest: boolean;
  guestQuota: GuestQuota | null;
  isLoading: boolean;
  login: (identifier: string, pass: string) => Promise<void>;
  register: (email: string, username: string, pass: string, fullName?: string) => Promise<void>;
  continueAsGuest: () => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [hasSession, setHasSession] = useState<boolean>(authService.hasSession());
  const [isGuest, setIsGuest] = useState<boolean>(!authService.hasSession());
  const [guestQuota, setGuestQuota] = useState<GuestQuota | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchProfile = async () => {
    try {
      const profile = await authService.getMe();
      setUser(profile);
      setIsGuest(false);
    } catch (err) {
      setUser(null);
      setIsGuest(true);
      if (err instanceof ApiError && err.status === 401) {  // the session ended: forget it. A network or server error keeps it for the next load
        authService.forgetSession();
        setHasSession(false);
      }
    }
  };

  const fetchGuestQuota = async () => {
    try {
      const gq = await authService.getGuestQuota();
      setGuestQuota(gq);
    } catch {
      // Fallback guest info if offline
      setGuestQuota({
        is_authenticated: false,
        tier: "guest",
        max_upload_documents: 1,
        max_file_size_mb: 5,
        cost_description: "Guest Trial Mode (Max 1 document)",
      });
    }
  };

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await fetchGuestQuota();
      if (hasSession) {
        await fetchProfile();
      } else {
        setIsGuest(true);
      }
      setIsLoading(false);
    };
    init();
  }, [hasSession]);

  const login = async (identifier: string, pass: string) => {
    setIsLoading(true);
    try {
      await authService.login(identifier, pass);
      setHasSession(true);
      await fetchProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (
    email: string,
    username: string,
    pass: string,
    fullName?: string
  ) => {
    setIsLoading(true);
    try {
      await authService.register(email, username, pass, fullName);
      setHasSession(true);
      await fetchProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    await authService.logout();  // before the page reloads its data as a guest: the cookie must be gone by then
    setHasSession(false);
    setUser(null);
    setIsGuest(true);
  };

  const continueAsGuest = () => logout();

  const refreshUser = async () => {
    if (hasSession) {
      await fetchProfile();
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        hasSession,
        isAuthenticated: !!user && !isGuest,
        isGuest,
        guestQuota,
        isLoading,
        login,
        register,
        continueAsGuest,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
