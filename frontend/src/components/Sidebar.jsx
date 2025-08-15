import React from "react";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Separator } from "./ui/separator";
import { Plus, Trash2, MessageSquare } from "lucide-react";

function formatTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleString();
  } catch (e) {
    return ts;
  }
}

export default function Sidebar({
  sessions,
  activeId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
}) {
  return (
    <aside className="hidden md:flex w-72 flex-col border-r bg-card/50">
      <div className="p-3">
        <Button onClick={onNewChat} className="w-full justify-start gap-2" variant="secondary">
          <Plus className="h-4 w-4" /> Nuova chat
        </Button>
      </div>
      <Separator />
      <ScrollArea className="flex-1 px-2">
        <div className="py-2 space-y-1">
          {sessions.length === 0 && (
            <div className="text-sm text-muted-foreground px-2 py-6">Nessuna conversazione</div>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group flex items-center justify-between gap-2 rounded-md px-2 py-2 cursor-pointer hover:bg-accent ${
                s.id === activeId ? "bg-accent" : ""
              }`}
              onClick={() => onSelectSession(s.id)}
            >
              <div className="flex items-center gap-2 min-w-0">
                <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{s.title || "Senza titolo"}</div>
                  <div className="truncate text-xs text-muted-foreground">{formatTime(s.updatedAt)}</div>
                </div>
              </div>
              <button
                className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(s.id);
                }}
                aria-label="Elimina conversazione"
                title="Elimina"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </ScrollArea>
      <Separator />
      <div className="p-3 text-xs text-muted-foreground">
        Chat locale mock • Dati salvati nel browser
      </div>
    </aside>
  );
}