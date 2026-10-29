import React, { createContext, useContext, useEffect, useState } from "react";
import { authService } from "../services/auth";
import { GuestQuota, UserProfile } from "../types/auth";

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isGuest: boolean;
  guestQuota: GuestQuota | null;
  isLoading: boolean;
  login: (identifier: string, pass: string) => Promise<void>;
  register: (email: string, username: string, pass: string, fullName?: string) => Promise<void>;
  continueAsGuest: () => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(authService.getAuthToken());
  const [isGuest, setIsGuest] = useState<boolean>(!authService.getAuthToken());
  const [guestQuota, setGuestQuota] = useState<GuestQuota | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchProfile = async () => {
    try {
      const profile = await authService.getMe();
      setUser(profile);
      setIsGuest(false);
    } catch {
      // Token expired or invalid
      authService.removeAuthToken();
      setToken(null);
      setUser(null);
      setIsGuest(true);
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
        cost_description: "Chế độ dùng thử (Tối đa 1 tài liệu)",
      });
    }
  };

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await fetchGuestQuota();
      if (token) {
        await fetchProfile();
      } else {
        setIsGuest(true);
      }
      setIsLoading(false);
    };
    init();
  }, [token]);

  const login = async (identifier: string, pass: string) => {
    setIsLoading(true);
    try {
      const res = await authService.login(identifier, pass);
      setToken(res.access_token);
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
      const res = await authService.register(email, username, pass, fullName);
      setToken(res.access_token);
      await fetchProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const continueAsGuest = () => {
    authService.removeAuthToken();
    setToken(null);
    setUser(null);
    setIsGuest(true);
  };

  const logout = () => {
    authService.logout();
    setToken(null);
    setUser(null);
    setIsGuest(true);
  };

  const refreshUser = async () => {
    if (token) {
      await fetchProfile();
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
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
