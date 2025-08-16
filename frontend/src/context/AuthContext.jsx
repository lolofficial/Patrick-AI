import React, { createContext, useContext, useEffect, useState } from "react";
import { AuthAPI } from "../lib/api";
import { useToast } from "../hooks/use-toast";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const { toast } = useToast();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const me = await AuthAPI.me();
        setUser(me);
      } catch (e) {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function login(email, password) {
    try {
      const u = await AuthAPI.login(email, password);
      setUser(u);
      return true;
    } catch (e) {
      toast({ title: "Login fallito" });
      return false;
    }
  }

  async function register(email, password) {
    try {
      await AuthAPI.register(email, password);
      // auto-login
      return await login(email, password);
    } catch (e) {
      toast({ title: "Registrazione fallita" });
      return false;
    }
  }

  async function logout() {
    try {
      await AuthAPI.logout();
    } catch {}
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  return useContext(AuthCtx);
}