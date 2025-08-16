import React, { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "../components/Sidebar";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { ScrollArea } from "../components/ui/scroll-area";
import { useToast } from "../hooks/use-toast";
import { Copy, Send, Menu, RefreshCw, Bot, User, MoreVertical, LogOut } from "lucide-react";
import { SessionsAPI, ChatAPI, AuthAPI } from "../lib/api";
import { defaultModels } from "../mock";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "../components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

function Avatar({ role }) {
  return (
    <div className={`h-7 w-7 rounded-md flex items-center justify-center ${role === "assistant" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"}`}>
      {role === "assistant" ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
    </div>
  );
}

function ChatBubble({ msg, onCopy }) {
  return (
    <div className="flex gap-3">
      <Avatar role={msg.role} />
      <div className="flex-1 min-w-0">
        <div className="prose prose-slate dark:prose-invert max-w-none text-sm">
          {msg.content.split("\n").map((line, i) => (
            <p key={i} className="leading-6">{line}</p>
          ))}
        </div>
        <div className="mt-1 flex items-center gap-2 opacity-0 hover:opacity-100 transition-opacity">
          <Button size="xs" variant="ghost" className="h-7 px-2 text-xs" onClick={() => onCopy(msg.content)}>
            <Copy className="h-3.5 w-3.5 mr-1" /> Copia
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function Chat() {
  const { toast } = useToast();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const active = useMemo(() => sessions.find((s) => s.id === activeId) || null, [sessions, activeId]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [aborter, setAborter] = useState(null);
  const [openChangePwd, setOpenChangePwd] = useState(false);
  const [openProfile, setOpenProfile] = useState(false);
  const [pwdForm, setPwdForm] = useState({ current: "", next: "", confirm: "" });
  const listRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await SessionsAPI.list();
        if (!list.length) {
          const created = await SessionsAPI.create({});
          setSessions([created]);
          setActiveId(created.id);
          setMessages([]);
        } else {
          setSessions(list);
          setActiveId(list[0].id);
          const msgs = await SessionsAPI.messages(list[0].id);
          setMessages(msgs);
        }
      } catch (e) {
        console.error(e);
        toast({ title: "Errore nel caricamento delle sessioni" });
      }
    })();
  }, []);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages.length, isStreaming]);

  async function reloadMessages(id) {
    try {
      const msgs = await SessionsAPI.messages(id);
      setMessages(msgs);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleNewChat() {
    try {
      const created = await SessionsAPI.create({});
      setSessions((prev) => [created, ...prev]);
      setActiveId(created.id);
      setMessages([]);
    } catch (e) {
      toast({ title: "Impossibile creare la chat" });
    }
  }

  async function handleSelectSession(id) {
    setActiveId(id);
    await reloadMessages(id);
  }

  async function handleDeleteSession(id) {
    try {
      await SessionsAPI.remove(id);
      const next = sessions.filter((s) => s.id !== id);
      setSessions(next);
      if (id === activeId) {
        const newActive = next[0]?.id || null;
        setActiveId(newActive);
        if (newActive) await reloadMessages(newActive); else setMessages([]);
      }
    } catch (e) {
      toast({ title: "Impossibile eliminare" });
    }
  }

  async function updateActiveSession(patch) {
    if (!active) return;
    try {
      const updated = await SessionsAPI.update(active.id, patch);
      setSessions((prev) => {
        const idx = prev.findIndex((s) => s.id === updated.id);
        if (idx === -1) return [updated, ...prev];
        const copy = [...prev];
        copy[idx] = updated;
        return [copy[idx], ...copy.filter((_, i) => i !== idx)];
      });
    } catch (e) {
      console.error(e);
    }
  }

  async function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed || !active || isStreaming) return;

    const userMsg = { id: crypto.randomUUID(), sessionId: active.id, role: "user", content: trimmed, createdAt: new Date().toISOString() };
    const assistMsg = { id: crypto.randomUUID(), sessionId: active.id, role: "assistant", content: "", createdAt: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg, assistMsg]);
    setInput("");
    textareaRef.current?.focus();

    const controller = new AbortController();
    setAborter(controller);
    setIsStreaming(true);

    try {
      for await (const evt of ChatAPI.stream({ sessionId: active.id, model: active.model, messages: [...messages, userMsg] }, { signal: controller.signal })) {
        if (evt.type === 'chunk') {
          setMessages((prev) => prev.map((m) => (m.id === assistMsg.id ? { ...m, content: (m.content || '') + (evt.delta || '') } : m)));
        } else if (evt.type === 'end') {
          await reloadMessages(active.id);
        }
      }
    } catch (e) {
      console.error(e);
      toast({ title: "Errore durante lo streaming" });
    } finally {
      setIsStreaming(false);
      setAborter(null);
    }
  }

  function stopGeneration() {
    aborter?.abort();
  }

  function regenerateLast() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    setInput(lastUser.content);
    setTimeout(() => sendMessage(), 0);
  }

  function handleCopy(text) {
    navigator.clipboard.writeText(text);
    toast({ title: "Copiato negli appunti" });
  }

  function onModelChange(newModel) {
    if (!active) return;
    updateActiveSession({ model: newModel });
  }

  function onTitleChange(e) {
    const value = e.target.value;
    updateActiveSession({ title: value });
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  async function onChangePassword(e) {
    e.preventDefault();
    if (!pwdForm.next || pwdForm.next.length < 6) {
      toast({ title: "Minimo 6 caratteri" });
      return;
    }
    if (pwdForm.next !== pwdForm.confirm) {
      toast({ title: "Le password non coincidono" });
      return;
    }
    try {
      await AuthAPI.changePassword(pwdForm.current, pwdForm.next);
      toast({ title: "Password aggiornata" });
      setOpenChangePwd(false);
      setPwdForm({ current: "", next: "", confirm: "" });
    } catch (err) {
      toast({ title: err.message || "Cambio password fallito" });
    }
  }

  const placeholder = "Invia un messaggio...";

  return (
    <div className="h-screen flex bg-background">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
      />
      <main className="flex-1 flex flex-col">
        {/* Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b bg-background/70 backdrop-blur">
          <div className="flex items-center gap-2 min-w-0">
            <Button variant="ghost" size="icon" className="md:hidden">
              <Menu className="h-5 w-5" />
            </Button>
            <input
              value={active?.title || "Nuova chat"}
              onChange={onTitleChange}
              className="bg-transparent outline-none text-sm font-medium rounded px-2 py-1 hover:bg-accent focus:bg-accent"
            />
          </div>
          <div className="flex items-center gap-2">
            <Select value={active?.model} onValueChange={onModelChange}>
              <SelectTrigger className="w-[160px] h-8 text-xs">
                <SelectValue placeholder="Seleziona modello" />
              </SelectTrigger>
              <SelectContent>
                {defaultModels.map((m) => (
                  <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Account menu */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="max-w-[200px] truncate">
                  {user?.email || "Account"}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => setOpenProfile(true)}>Profilo</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setOpenChangePwd(true)}>Cambia password</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={async () => { await logout(); navigate('/auth', { replace: true }); }}>Esci</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea ref={listRef} className="flex-1 px-4">
          <div className="max-w-3xl mx-auto py-6 space-y-6">
            {(!active || messages.length === 0) && (
              <div className="text-center text-muted-foreground py-16">
                Inizia una conversazione con il tuo ChatGPT locale.
              </div>
            )}
            {messages.map((m) => (
              <ChatBubble key={m.id} msg={m} onCopy={handleCopy} />
            ))}
          </div>
        </ScrollArea>

        {/* Composer */}
        <div className="border-t bg-background/70">
          <div className="max-w-3xl mx-auto p-3">
            <div className="relative rounded-xl border bg-card shadow-sm">
              <Textarea
                ref={textareaRef}
                placeholder={placeholder}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                className="min-h-[64px] max-h-[220px] resize-none border-0 focus-visible:ring-0 focus:outline-none"
              />
              <div className="flex items-center justify-between px-3 pb-3">
                <div className="text-[11px] text-muted-foreground">Invia con Invio • Nuova riga con Shift+Invio</div>
                <div className="flex items-center gap-2">
                  {isStreaming ? (
                    <Button size="sm" variant="secondary" onClick={stopGeneration}>Stop</Button>
                  ) : (
                    <Button size="sm" onClick={sendMessage} disabled={!input.trim()}>
                      <Send className="h-4 w-4 mr-1" /> Invia
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Profile dialog */}
      <Dialog open={openProfile} onOpenChange={setOpenProfile}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Profilo</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <div><span className="text-muted-foreground">Email:</span> {user?.email}</div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Change password dialog */}
      <Dialog open={openChangePwd} onOpenChange={setOpenChangePwd}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cambia password</DialogTitle>
          </DialogHeader>
          <form className="space-y-3" onSubmit={onChangePassword}>
            <div className="space-y-2">
              <Label>Password attuale</Label>
              <Input type="password" value={pwdForm.current} onChange={(e) => setPwdForm({ ...pwdForm, current: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label>Nuova password</Label>
              <Input type="password" value={pwdForm.next} onChange={(e) => setPwdForm({ ...pwdForm, next: e.target.value })} required />
            </div>
            <div className="space-y-2">
              <Label>Conferma nuova password</Label>
              <Input type="password" value={pwdForm.confirm} onChange={(e) => setPwdForm({ ...pwdForm, confirm: e.target.value })} required />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={() => setOpenChangePwd(false)}>Annulla</Button>
              <Button type="submit">Aggiorna</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}