import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { useToast } from "../hooks/use-toast";
import { useNavigate } from "react-router-dom";

export default function AuthPage() {
  const { login, register } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setLoading(true);
    const ok = await login(form.get("email"), form.get("password"));
    setLoading(false);
    if (ok) {
      navigate("/chat", { replace: true });
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    if ((form.get("password") || "").length < 6) {
      toast({ title: "La password deve avere almeno 6 caratteri" });
      return;
    }
    setLoading(true);
    const ok = await register(form.get("email"), form.get("password"));
    setLoading(false);
    if (ok) {
      navigate("/chat", { replace: true });
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-sm">
        <Tabs defaultValue="login">
          <TabsList className="grid grid-cols-2 w-full">
            <TabsTrigger value="login">Login</TabsTrigger>
            <TabsTrigger value="register">Registrati</TabsTrigger>
          </TabsList>
          <TabsContent value="login">
            <form className="space-y-4 mt-4" onSubmit={handleLogin}>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" name="email" type="email" required placeholder="you@example.com" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" name="password" type="password" required placeholder="••••••••" />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>Entra</Button>
            </form>
          </TabsContent>
          <TabsContent value="register">
            <form className="space-y-4 mt-4" onSubmit={handleRegister}>
              <div className="space-y-2">
                <Label htmlFor="remail">Email</Label>
                <Input id="remail" name="email" type="email" required placeholder="you@example.com" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rpassword">Password</Label>
                <Input id="rpassword" name="password" type="password" required placeholder="min 6 caratteri" />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>Crea account</Button>
            </form>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}