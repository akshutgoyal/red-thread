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
import { api, setAuthToken } from "@/api/client";
import type { AuthUser } from "@/types";

const SESSION_KEY = "red-thread.session-token";

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  loginGoogle: (credential: string) => Promise<AuthUser>;
  loginDemo: () => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SESSION_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(() => readToken());
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(token));

  useEffect(() => {
    setAuthToken(token);
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    api
      .me()
      .then((nextUser) => {
        if (!cancelled) setUser(nextUser);
      })
      .catch(() => {
        if (!cancelled) {
          setToken(null);
          setAuthToken(null);
          window.localStorage.removeItem(SESSION_KEY);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const acceptSession = useCallback(
    (nextToken: string, nextUser: AuthUser) => {
      window.localStorage.setItem(SESSION_KEY, nextToken);
      setAuthToken(nextToken);
      setToken(nextToken);
      setUser(nextUser);
      queryClient.clear();
      return nextUser;
    },
    [queryClient],
  );

  const loginGoogle = useCallback(
    async (credential: string) => {
      const session = await api.loginGoogle(credential);
      return acceptSession(session.token, session.user);
    },
    [acceptSession],
  );

  const loginDemo = useCallback(async () => {
    const session = await api.loginDemo();
    return acceptSession(session.token, session.user);
  }, [acceptSession]);

  const logout = useCallback(() => {
    window.localStorage.removeItem(SESSION_KEY);
    setAuthToken(null);
    setToken(null);
    setUser(null);
    queryClient.clear();
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
