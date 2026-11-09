import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/api/client";
import type { AuthUser } from "@/types";

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  loginGoogle: (credential: string) => Promise<AuthUser>;
  loginDemo: () => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const loadUser = async (alreadyRetried = false) => {
      try {
        const nextUser = await api.me();
        if (!cancelled) {
          setUser(nextUser);
          setIsLoading(false);
        }
      } catch (error) {
        if (cancelled) return;
        const transient = !(error instanceof ApiError) || error.status >= 500;
        if (transient && !alreadyRetried) {
          await new Promise((resolve) => setTimeout(resolve, 750));
          if (!cancelled) return loadUser(true);
        }
        setUser(null);
        setIsLoading(false);
      }
    };
    void loadUser();
    return () => {
      cancelled = true;
    };
  }, []);

  const acceptSession = useCallback(
    (nextUser: AuthUser) => {
      setUser(nextUser);
      queryClient.clear();
      return nextUser;
    },
    [queryClient],
  );

  const loginGoogle = useCallback(
    async (credential: string) => {
      const session = await api.loginGoogle(credential);
      return acceptSession(session.user);
    },
    [acceptSession],
  );

  const loginDemo = useCallback(async () => {
    const session = await api.loginDemo();
    return acceptSession(session.user);
  }, [acceptSession]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      queryClient.clear();
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, isLoading, loginGoogle, loginDemo, logout }),
    [user, isLoading, loginGoogle, loginDemo, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
