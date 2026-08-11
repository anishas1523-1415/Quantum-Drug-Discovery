import { createContext, useContext, useEffect, useState } from "react";
import client, { extractErrorMessage } from "../api/client";

const AuthContext = createContext(null);

const TOKEN_KEY = "qdd_token";
const USER_KEY = "qdd_user";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  });
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      if (!token) {
        setInitializing(false);
        return;
      }

      try {
        const response = await client.get("/auth/me");
        if (!cancelled) {
          setUser(response.data.user);
          localStorage.setItem(USER_KEY, JSON.stringify(response.data.user));
        }
      } catch {
        if (!cancelled) {
          setToken(null);
          setUser(null);
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
        }
      } finally {
        if (!cancelled) {
          setInitializing(false);
        }
      }
    }

    verify();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function persistSession(nextToken, nextUser) {
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    setToken(nextToken);
    setUser(nextUser);
  }

  async function login(email, password) {
    try {
      const response = await client.post("/auth/login", { email, password });
      persistSession(response.data.token, response.data.user);
      return { ok: true };
    } catch (error) {
      return { ok: false, message: extractErrorMessage(error) };
    }
  }

  async function register(name, email, password) {
    try {
      const response = await client.post("/auth/register", { name, email, password });
      persistSession(response.data.token, response.data.user);
      return { ok: true };
    } catch (error) {
      return { ok: false, message: extractErrorMessage(error) };
    }
  }

  async function forgotPassword(email) {
    try {
      const response = await client.post("/auth/forgot-password", { email });
      return { ok: true, message: response.data.message };
    } catch (error) {
      return { ok: false, message: extractErrorMessage(error) };
    }
  }

  async function resetPassword(token, password) {
    try {
      const response = await client.post("/auth/reset-password", { token, password });
      return { ok: true, message: response.data.message };
    } catch (error) {
      return { ok: false, message: extractErrorMessage(error) };
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }

  const value = {
    token,
    user,
    isAuthenticated: Boolean(token),
    initializing,
    login,
    register,
    logout,
    forgotPassword,
    resetPassword,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- hook lives alongside its provider by design
export function useAuth() {
  const ctx = useContext(AuthContext);

  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return ctx;
}
