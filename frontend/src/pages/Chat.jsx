import React, { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "../components/Sidebar";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Separator } from "../components/ui/separator";
import { ScrollArea } from "../components/ui/scroll-area";
import { useToast } from "../hooks/use-toast";
import { Copy, Send, Menu, RefreshCw, Bot, User, MoreVertical } from "lucide-react";
import {
  createNewSession,
  defaultModels,
  deleteSessionById,
  getActiveSessionId,
  loadSessions,
  mockStreamResponse,
  saveSessions,
  setActiveSessionId,
  upsertSession,
} from "../mock";

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
  const [sessions, setSessions] = useState(() => loadSessions());
  const [activeId, setActiveId] = useState(() => getActiveSessionId() || sessions[0]?.id || null);
  const active = useMemo(() => sessions.find((s) => s.id === activeId) || null, [sessions, activeId]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [aborter, setAborter] = useState(null);
  const listRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (!activeId && sessions.length === 0) {
      const first = createNewSession();
      const next = upsertSession([], first);
      setSessions(next);
      setActiveId(first.id);
      setActiveSessionId(first.id);
      saveSessions(next);
    }
  }, []);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [active?.messages?.length, isStreaming]);

  function persist(nextSessions) {
    setSessions(nextSessions);
    saveSessions(nextSessions);
  }

  function handleNewChat() {
    const fresh = createNewSession();
    const next = upsertSession(sessions, fresh);
    persist(next);
    setActiveId(fresh.id);
    setActiveSessionId(fresh.id);
    setInput("");
  }

  function handleSelectSession(id) {
    setActiveId(id);
    setActiveSessionId(id);
  }

  function handleDeleteSession(id) {
    const next = deleteSessionById(sessions, id);
    persist(next);
    if (id === activeId) {
      const newActive = next[0]?.id || null;
      setActiveId(newActive);
      setActiveSessionId(newActive || "");
    }
  }

  function updateActiveSession(patch) {
    if (!active) return;
    const updated = { ...active, ...patch, updatedAt: new Date().toISOString() };
    const next = upsertSession(sessions, updated);
    persist(next);
  }

  async function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed || !active || isStreaming) return;

    // push user message
    const userMsg = { id: crypto.randomUUID(), role: "user", content: trimmed, createdAt: new Date().toISOString() };
    const assistMsg = { id: crypto.randomUUID(), role: "assistant", content: "", createdAt: new Date().toISOString() };
    updateActiveSession({ messages: [...active.messages, userMsg, assistMsg] });
    setInput("");
    textareaRef.current?.focus();

    // stream assistant
    const controller = new AbortController();
    setAborter(controller);
    setIsStreaming(true);

    try {
      for await (const chunk of mockStreamResponse(trimmed, active.model, { signal: controller.signal })) {
        // update last message content
        const cur = sessions.find((s) => s.id === active.id) || active; // ensure up-to-date reference
        const msgs = cur.messages.map((m) => (m.id === assistMsg.id ? { ...m, content: chunk } : m));
        const patched = { ...cur, messages: msgs };
        const next = upsertSession(sessions, patched);
        setSessions(next);
      }
    } finally {
      setIsStreaming(false);
      setAborter(null);
      // ensure saved
      const cur = sessions.find((s) => s.id === active.id) || active;
      saveSessions(upsertSession(sessions, cur));
    }
  }

  function stopGeneration() {
    aborter?.abort();
  }

  function regenerateLast() {
    if (!active) return;
    const lastUser = [...active.messages].reverse().find((m) => m.role === "user");
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
            <Button variant="secondary" size="sm" onClick={regenerateLast} disabled={!active?.messages?.length || isStreaming}>
              <RefreshCw className="h-4 w-4 mr-1" /> Rigenera
            </Button>
            <Button variant="ghost" size="icon">
              <MoreVertical className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea ref={listRef} className="flex-1 px-4">
          <div className="max-w-3xl mx-auto py-6 space-y-6">
            {(!active || active.messages.length === 0) && (
              <div className="text-center text-muted-foreground py-16">
                Inizia una conversazione con il tuo ChatGPT locale.
              </div>
            )}
            {active?.messages?.map((m) => (
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
            <div className="text-[11px] text-muted-foreground mt-2">
              Questo è un mock frontend. Nessuna richiesta viene inviata a modelli reali.
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}