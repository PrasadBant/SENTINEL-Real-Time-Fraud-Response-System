import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { Copy, Check, RotateCcw, Trash2, History, Plus, Send, X, Sparkles, ArrowLeft } from 'lucide-react';
import { apiFetch } from '../services/api';

const GREETING = {
  id: 'greeting',
  role: 'assistant',
  content: 'Hello! I am your Sentinel AI Copilot. I can analyze cases, explain risk scores, and execute actions. How can I assist you?',
};

// SENTINEL's real domain — bank-transfer/mule-chain fraud, not generic
// e-commerce/card-fraud examples. These map onto Phase B's structured
// intents and Phase D/F general capabilities, so a fresh conversation
// starts with prompts that are guaranteed to work well.
const SUGGESTED_PROMPTS = [
  'Show me open high-risk cases',
  'What should I investigate next?',
  "What's our total exposure?",
  'What is a mule chain?',
];

let _uidCounter = 0;
const uid = () => `m-${Date.now()}-${_uidCounter++}`;

const formatRelativeTime = (iso) => {
  if (!iso) return '';
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
};

/**
 * Parses one or more complete `data: {...}\n\n` SSE frames out of a
 * growing text buffer, returning the parsed payloads and whatever
 * incomplete tail remains for the next chunk.
 */
const extractSseEvents = (buffer) => {
  const events = [];
  let rest = buffer;
  let sepIndex;
  while ((sepIndex = rest.indexOf('\n\n')) !== -1) {
    const rawEvent = rest.slice(0, sepIndex);
    rest = rest.slice(sepIndex + 2);
    const line = rawEvent.split('\n').find((l) => l.startsWith('data: '));
    if (line) {
      try {
        events.push(JSON.parse(line.slice(6)));
      } catch {
        // ignore a malformed frame rather than crash the whole stream
      }
    }
  }
  return { events, rest };
};

const AICopilot = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [view, setView] = useState('chat'); // 'chat' | 'history'
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [historyList, setHistoryList] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const location = useLocation();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen, view]);

  // Ctrl/Cmd+K toggles the panel from anywhere in the app; Escape closes it.
  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const currentCaseId = useCallback(() => {
    if (location.pathname.startsWith('/graph/')) {
      return location.pathname.split('/').pop();
    }
    return null;
  }, [location.pathname]);

  /** Streams one turn via SSE, updating `assistantId`'s message content
   * as deltas arrive. Returns the final { text, action, conversationId }. */
  const streamTurn = async (userMessage, assistantId) => {
    const response = await apiFetch('/api/copilot/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: userMessage,
        context_case_id: currentCaseId(),
        conversation_id: conversationId,
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Copilot stream request failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let assistantText = '';
    let finalAction = null;
    let finalConvId = conversationId;

    let done = false;
    while (!done) {
      const chunk = await reader.read();
      done = chunk.done;
      if (done) break;
      buffer += decoder.decode(chunk.value, { stream: true });

      const { events, rest } = extractSseEvents(buffer);
      buffer = rest;

      for (const payload of events) {
        if (payload.type === 'start') {
          finalConvId = payload.conversation_id;
          setConversationId(payload.conversation_id);
        } else if (payload.type === 'delta') {
          assistantText += payload.text;
          const snapshot = assistantText;
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: snapshot } : m))
          );
        } else if (payload.type === 'done') {
          finalAction = payload.action;
          finalConvId = payload.conversation_id;
        } else if (payload.type === 'error') {
          assistantText = assistantText || payload.message || 'The copilot hit an error.';
        }
      }
    }

    return { text: assistantText, action: finalAction, conversationId: finalConvId };
  };

  const runTurn = async (userMessage, assistantId) => {
    setIsLoading(true);
    try {
      const { text, action } = await streamTurn(userMessage, assistantId);
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, content: text, action, streaming: false } : m))
      );
    } catch (error) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: '⚠️ Connection to AI engine failed.', streaming: false }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (overrideMessage) => {
    const userMessage = (overrideMessage ?? input).trim();
    if (!userMessage || isLoading) return;

    setInput('');
    const assistantId = uid();
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMessage, id: uid() },
      { role: 'assistant', content: '', id: assistantId, streaming: true },
    ]);

    await runTurn(userMessage, assistantId);
  };

  const handleRegenerate = async () => {
    if (isLoading) return;
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (!lastUserMsg) return;

    const assistantId = uid();
    setMessages((prev) => {
      const lastUserIdx = prev.map((m) => m.role).lastIndexOf('user');
      const trimmed = prev.slice(0, lastUserIdx + 1);
      return [...trimmed, { role: 'assistant', content: '', id: assistantId, streaming: true }];
    });

    await runTurn(lastUserMsg.content, assistantId);
  };

  const handleCopy = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId((prev) => (prev === id ? null : prev)), 1500);
    } catch {
      // clipboard permission denied — silently ignore, not worth a toast
    }
  };

  const handleNewChat = () => {
    setConversationId(null);
    setMessages([GREETING]);
    setView('chat');
  };

  const handleClearCurrent = async () => {
    if (conversationId) {
      try {
        await apiFetch(`/api/copilot/history?conversation_id=${encodeURIComponent(conversationId)}`, {
          method: 'DELETE',
        });
      } catch {
        // best-effort — the local view resets regardless
      }
    }
    handleNewChat();
  };

  const loadHistoryList = async () => {
    setHistoryLoading(true);
    try {
      const res = await apiFetch('/api/copilot/history');
      const data = await res.json();
      setHistoryList(data.conversations || []);
    } catch {
      setHistoryList([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const openHistory = async () => {
    setView('history');
    await loadHistoryList();
  };

  const openConversation = async (id) => {
    setHistoryLoading(true);
    try {
      const res = await apiFetch(`/api/copilot/history?conversation_id=${encodeURIComponent(id)}`);
      if (!res.ok) throw new Error('not found');
      const data = await res.json();
      const loaded = (data.messages || []).map((m) => ({
        id: m.message_id || uid(),
        role: m.role,
        content: m.content,
        action: m.action,
      }));
      setMessages(loaded.length ? loaded : [GREETING]);
      setConversationId(id);
      setView('chat');
    } catch {
      // leave the history list open on failure
    } finally {
      setHistoryLoading(false);
    }
  };

  const deleteHistoryItem = async (id, e) => {
    e.stopPropagation();
    try {
      await apiFetch(`/api/copilot/history?conversation_id=${encodeURIComponent(id)}`, { method: 'DELETE' });
      setHistoryList((prev) => prev.filter((c) => c.conversation_id !== id));
      if (id === conversationId) {
        handleNewChat();
      }
    } catch {
      // best-effort
    }
  };

  const handleInputKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isFreshConversation = messages.length === 1 && messages[0].id === 'greeting';
  const lastMessage = messages[messages.length - 1];
  const canRegenerate =
    !isLoading && lastMessage && lastMessage.role === 'assistant' && lastMessage.id !== 'greeting';

  return (
    <>
      {/* Floating Action Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          title="Sentinel Copilot (Ctrl+K)"
          className="fixed bottom-6 right-6 p-4 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground shadow-xl transition-all duration-300 z-50 flex items-center justify-center group"
        >
          <Sparkles size={24} />
        </button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 w-[400px] h-[600px] bg-card border border-border rounded-xl shadow-2xl flex flex-col z-50 overflow-hidden">
          {/* Header */}
          <div className="p-4 border-b border-border bg-muted/50 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-2">
              {view === 'history' ? (
                <button
                  onClick={() => setView('chat')}
                  className="text-muted-foreground hover:text-foreground"
                  title="Back to chat"
                >
                  <ArrowLeft size={18} />
                </button>
              ) : (
                <Sparkles size={18} className="text-primary" />
              )}
              <h3 className="font-bold text-sm tracking-tight text-foreground">
                {view === 'history' ? 'Conversation History' : 'Sentinel Copilot'}
              </h3>
            </div>
            <div className="flex items-center gap-1">
              {view === 'chat' && (
                <>
                  <button
                    onClick={handleNewChat}
                    title="New chat"
                    className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-background/60"
                  >
                    <Plus size={16} />
                  </button>
                  <button
                    onClick={openHistory}
                    title="History"
                    className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-background/60"
                  >
                    <History size={16} />
                  </button>
                  <button
                    onClick={handleClearCurrent}
                    title="Clear this conversation"
                    className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-background/60"
                  >
                    <Trash2 size={16} />
                  </button>
                </>
              )}
              <button
                onClick={() => setIsOpen(false)}
                title="Close (Esc)"
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-background/60"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {view === 'history' ? (
            <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-background">
              {historyLoading && (
                <p className="text-xs text-muted-foreground text-center py-8">Loading…</p>
              )}
              {!historyLoading && historyList.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-8">No past conversations yet.</p>
              )}
              {!historyLoading &&
                historyList.map((c) => (
                  <button
                    key={c.conversation_id}
                    onClick={() => openConversation(c.conversation_id)}
                    className="w-full text-left p-3 rounded-lg border border-border bg-card hover:border-primary/50 transition-colors group"
                  >
                    <div className="flex justify-between items-start gap-2">
                      <p className="text-xs text-foreground line-clamp-2 flex-1">
                        {c.preview || 'Empty conversation'}
                      </p>
                      <button
                        onClick={(e) => deleteHistoryItem(c.conversation_id, e)}
                        title="Delete"
                        className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive shrink-0"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      <span className="text-[10px] text-muted-foreground">{formatRelativeTime(c.updated_at)}</span>
                      <span className="text-[10px] text-muted-foreground">{c.message_count} messages</span>
                    </div>
                  </button>
                ))}
            </div>
          ) : (
            <>
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-background">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                        msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
                      }`}
                    >
                      {msg.role === 'user' ? (
                        msg.content
                      ) : msg.streaming && !msg.content ? (
                        <div className="flex items-center gap-2 py-1">
                          <div className="w-2 h-2 rounded-full bg-primary animate-bounce" />
                          <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.2s' }} />
                          <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0.4s' }} />
                        </div>
                      ) : (
                        <div className="markdown-content">
                          <ReactMarkdown>{msg.content || ''}</ReactMarkdown>
                        </div>
                      )}

                      {msg.action && (
                        <div className="mt-3 p-2 bg-background/60 rounded-md text-xs font-mono border border-border">
                          Action Executed: {msg.action.type}
                        </div>
                      )}

                      {msg.role === 'assistant' && msg.id !== 'greeting' && !msg.streaming && msg.content && (
                        <div className="flex items-center gap-1 mt-2 -mb-1">
                          <button
                            onClick={() => handleCopy(msg.id, msg.content)}
                            title="Copy"
                            className="p-1 rounded text-muted-foreground/70 hover:text-foreground hover:bg-background/60"
                          >
                            {copiedId === msg.id ? <Check size={12} /> : <Copy size={12} />}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isFreshConversation && (
                  <div className="flex flex-col gap-2 pt-2">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground px-1">
                      Try asking
                    </p>
                    {SUGGESTED_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => handleSend(prompt)}
                        className="text-left text-xs px-3 py-2 rounded-lg border border-border bg-card hover:border-primary/50 hover:bg-muted/50 text-foreground transition-colors"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="p-3 border-t border-border bg-card shrink-0">
                {canRegenerate && (
                  <button
                    onClick={handleRegenerate}
                    className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground mb-2 px-1"
                  >
                    <RotateCcw size={12} /> Regenerate response
                  </button>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  className="flex gap-2 items-end"
                >
                  <textarea
                    ref={inputRef}
                    rows={1}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleInputKeyDown}
                    placeholder="Ask Copilot… (Enter to send, Shift+Enter for a new line)"
                    className="flex-1 resize-none bg-muted border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 max-h-24"
                  />
                  <button
                    type="submit"
                    disabled={!input.trim() || isLoading}
                    className="bg-primary text-primary-foreground p-2 rounded-lg disabled:opacity-50 transition-opacity shrink-0"
                  >
                    <Send size={18} />
                  </button>
                </form>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
};

export default AICopilot;
