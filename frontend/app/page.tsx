"use client";

import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Command,
  FileText,
  Files,
  Gauge,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { apiRequest } from "@/lib/api";
import { authClient } from "@/lib/auth-client";

type Citation = {
  id: string;
  docId: string;
  section: string;
  title: string;
  updated: string;
  parentText: string;
  childText: string;
  sourceUrl?: string;
};

type CompletionResponse = {
  answer: string;
  citations: Record<string, unknown>[];
  fallback: boolean;
};

type ChatMessage = {
  id: number | string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  fallback?: boolean;
};

type ConversationRecord = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Record<string, unknown>[];
  created_at: string;
};

function CitationPill({ citation, onOpen }: { citation: Citation; onOpen: () => void }) {
  return (
    <button className="citation-pill" onClick={onOpen} type="button" aria-label={`Open source: ${citation.docId}, ${citation.section}`} data-tooltip={citation.childText}>
      {`[Doc: ${citation.docId}, Section: ${citation.section}]`}
    </button>
  );
}

function citationFromRecord(record: Record<string, unknown>): Citation {
  return {
    id: String(record.id ?? record.child_id ?? record.doc_id ?? "source"),
    docId: String(record.docId ?? record.doc_id ?? "internal-document"),
    section: String(record.section ?? record.section_header ?? "Source section"),
    title: String(record.title ?? record.doc_id ?? "Internal source"),
    updated: String(record.updated ?? record.last_updated ?? "Verified source"),
    parentText: String(record.parentText ?? record.parent_text ?? record.childText ?? record.child_text ?? ""),
    childText: String(record.childText ?? record.child_text ?? "Source passage"),
    sourceUrl: typeof (record.sourceUrl ?? record.source_url) === "string" ? String(record.sourceUrl ?? record.source_url) : undefined,
  };
}

function historyDate(dateValue: string): string {
  const date = new Date(dateValue);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return "Today";
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  return date.toDateString() === yesterday.toDateString() ? "Yesterday" : "Previous 7 days";
}

function ChatWorkspace() {
  const { data: session } = authClient.useSession();
  const userName = session?.user.name ?? "Workspace member";
  const userInitials = userName.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [drawerCitation, setDrawerCitation] = useState<Citation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [historyItems, setHistoryItems] = useState<ConversationRecord[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState<Record<string, "up" | "down" | undefined>>({});
  const [searchOpen, setSearchOpen] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("");
  const feedEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isLoading]);

  useEffect(() => {
    let active = true;
    apiRequest<ConversationRecord[]>("/api/v1/chat/history")
      .then((conversations) => { if (active) setHistoryItems(conversations); })
      .catch(() => { if (active) setHistoryError(true); });
    return () => { active = false; };
  }, []);

  function startNewChat() {
    setMessages([]);
    setConversationId(null);
    setDrawerCitation(null);
    setMobileSidebarOpen(false);
    setQuery("");
    inputRef.current?.focus();
  }

  async function submitQuery(event?: FormEvent) {
    event?.preventDefault();
    const question = query.trim();
    if (!question || isLoading) return;

    const userMessage: ChatMessage = { id: Date.now(), role: "user", text: question };
    setMessages((current) => [...current, userMessage]);
    setQuery("");
    setRequestError("");
    setIsLoading(true);

    let activeConversationId = conversationId;
    try {
      if (!activeConversationId) {
        const conversation = await apiRequest<ConversationRecord>("/api/v1/chat/history", {
          method: "POST",
          body: JSON.stringify({ title: question.slice(0, 300) }),
        });
        activeConversationId = conversation.id;
        setConversationId(conversation.id);
        setHistoryItems((items) => [conversation, ...items]);
      }
      await apiRequest<StoredMessage>(`/api/v1/chat/history/${activeConversationId}/messages`, {
        method: "POST",
        body: JSON.stringify({ role: "user", content: question }),
      });
    } catch {
      setHistoryError(true);
    }

    try {
      const completion = await apiRequest<CompletionResponse>("/api/v1/chat/completions", {
        method: "POST",
        body: JSON.stringify({ query: question, stream: false }),
      });
      const nextMessage: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        text: completion.answer,
        citations: completion.citations.map(citationFromRecord),
        fallback: completion.fallback,
      };
      setMessages((current) => [...current, nextMessage]);
      if (activeConversationId) {
        try {
          await apiRequest<StoredMessage>(`/api/v1/chat/history/${activeConversationId}/messages`, {
            method: "POST",
            body: JSON.stringify({
              role: "assistant",
              content: nextMessage.text,
              citations: completion.citations,
            }),
          });
        } catch {
          setHistoryError(true);
        }
      }
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "The knowledge service is unavailable.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitQuery();
    }
  }

  function selectPrompt(prompt: string) {
    setQuery(prompt);
    inputRef.current?.focus();
  }

  const visibleHistory = historyItems.filter((item) => item.title.toLowerCase().includes(historyFilter.toLowerCase()));

  async function openConversation(conversation: ConversationRecord) {
    try {
      const storedMessages = await apiRequest<StoredMessage[]>(`/api/v1/chat/history/${conversation.id}/messages`);
      setConversationId(conversation.id);
      setMessages(storedMessages.map((message) => ({
        id: message.id,
        role: message.role,
        text: message.content,
        citations: message.citations.map(citationFromRecord),
        fallback: message.content === "Information not found in internal knowledge base",
      })));
      setMobileSidebarOpen(false);
      setDrawerCitation(null);
    } catch {
      setHistoryError(true);
    }
  }

  return (
    <main className={`workspace ${sidebarOpen ? "sidebar-expanded" : "sidebar-collapsed"} ${drawerCitation ? "drawer-visible" : ""}`}>
      <aside className={`history-sidebar ${mobileSidebarOpen ? "mobile-visible" : ""}`} aria-label="Chat history">
        <div className="sidebar-brand">
          <div className="brand-mark"><span /><span /><span /></div>
          {sidebarOpen && <span className="brand-name">northstar<span>.</span></span>}
          <button className="icon-button sidebar-toggle" onClick={() => setSidebarOpen((open) => !open)} aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"} title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}>
            {sidebarOpen ? <PanelLeftClose size={17} /> : <PanelLeftOpen size={17} />}
          </button>
        </div>

        <button className={`new-chat-button ${sidebarOpen ? "" : "icon-only"}`} onClick={startNewChat} title="New chat">
          <Plus size={16} strokeWidth={2.3} />{sidebarOpen && <span>New chat</span>}
          {sidebarOpen && <kbd>⌘ K</kbd>}
        </button>

        {sidebarOpen && <>
          <button className="sidebar-search" onClick={() => setSearchOpen((open) => !open)}>
            <Search size={15} /><span>Search conversations</span><kbd>⌘ /</kbd>
          </button>
          {searchOpen && <input className="history-search-input" autoFocus placeholder="Filter history..." value={historyFilter} onChange={(event) => setHistoryFilter(event.target.value)} />}

          <div className="history-scroll">
            <div className="sidebar-section-label">Your conversations <MoreHorizontal size={16} /></div>
            {visibleHistory.map((item, index) => (
              <button className={`history-item ${conversationId === item.id ? "selected" : ""}`} key={item.id} onClick={() => { void openConversation(item); }}>
                <MessageSquare size={15} /><span>{item.title}</span><small className="history-date">{historyDate(item.updated_at)}</small>{index === 0 && conversationId === item.id && <span className="history-active-dot" />}
              </button>
            ))}
            {historyError && <p className="empty-history">History sync unavailable</p>}
            {visibleHistory.length === 0 && <p className="empty-history">No matches found</p>}
            <div className="history-divider" />
            <button className="sidebar-nav-item"><Files size={15} /><span>Knowledge sources</span><span className="nav-count">12</span></button>
          </div>

          <div className="sidebar-bottom">
            <div className="workspace-status"><span className="status-pulse" /><div><strong>Knowledge base</strong><small>Synced just now</small></div><Check size={14} /></div>
            <button className="account-button" onClick={async () => { await authClient.signOut(); window.location.assign("/sign-in"); }} title="Sign out"><div className="avatar">{userInitials}</div><span className="account-copy"><strong>{userName}</strong><small>{session?.user.email}</small></span><ChevronDown size={14} /></button>
          </div>
        </>}
        {!sidebarOpen && <div className="collapsed-rail">
          <button className="rail-icon" onClick={startNewChat} title="New chat"><Plus size={17} /></button>
          <button className="rail-icon" onClick={() => setSearchOpen((open) => !open)} title="Search conversations"><Search size={17} /></button>
          <button className="rail-icon active" title="Chat history"><Clock3 size={17} /></button>
          <button className="rail-icon" title="Knowledge sources"><Files size={17} /></button>
          <div className="rail-spacer" /><div className="avatar small">{userInitials}</div>
        </div>}
      </aside>
      {mobileSidebarOpen && <button className="sidebar-scrim" onClick={() => setMobileSidebarOpen(false)} aria-label="Close chat history" />}

      <section className="chat-column" aria-label="Chat">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setMobileSidebarOpen(true)} aria-label="Open chat history" title="Open chat history"><PanelLeftOpen size={17} /></button>
          <div className="mobile-brand"><div className="brand-mark"><span /><span /><span /></div><span className="brand-name">northstar<span>.</span></span></div>
          <div className="breadcrumbs"><span>WORKSPACE</span><span className="breadcrumb-slash">/</span><span>KNOWLEDGE ASSISTANT</span></div>
          <div className="topbar-actions">
            <span className="preview-badge"><span /> PREVIEW</span>
            <button className="icon-button help-button" title="Help" aria-label="Help"><CircleHelp size={17} /></button>
            <div className="topbar-divider" />
            <button className="user-chip" title="Sign out" onClick={async () => { await authClient.signOut(); window.location.assign("/sign-in"); }}><span className="avatar tiny">{userInitials}</span><span>{userName.split(" ")[0]}</span><ChevronDown size={13} /></button>
          </div>
        </header>

        <div className="chat-scroll-area">
          <div className="chat-content">
            <div className="conversation-heading">
              <div className="eyebrow"><span className="eyebrow-line" /> GROUNDED ANSWERS, VERIFIED SOURCES</div>
              <h1>Ask your knowledge base<span className="heading-period">.</span></h1>
              <p>Answers drawn from your team&apos;s verified internal documents.</p>
            </div>

            {messages.length === 0 && <div className="empty-state">
              <div className="empty-icon"><Sparkles size={20} /></div>
              <h2>What are you looking for?</h2>
              <p>Ask a question across your internal policies, guides, and technical docs.</p>
              <div className="suggestion-grid">
                <button onClick={() => selectPrompt("What is the deadline for travel expense receipts?")}><span className="suggestion-icon cyan"><Clock3 size={15} /></span><span><strong>Find a policy detail</strong><small>Expense deadlines, eligibility, and more</small></span><ArrowUp size={14} /></button>
                <button onClick={() => selectPrompt("What are the password requirements for customer data systems?")}><span className="suggestion-icon pink"><ShieldCheck size={15} /></span><span><strong>Check a security standard</strong><small>Access controls and compliance guidance</small></span><ArrowUp size={14} /></button>
                <button onClick={() => selectPrompt("How do I locate the latest engineering runbook?")}><span className="suggestion-icon mint"><BookOpen size={15} /></span><span><strong>Search team documentation</strong><small>Runbooks, playbooks, and internal guides</small></span><ArrowUp size={14} /></button>
              </div>
            </div>}

            <div className="message-list">
              {requestError && <div className="request-error" role="alert"><CircleHelp size={14} />{requestError}</div>}
              {messages.map((message) => message.role === "user" ? (
                <article className="user-message" key={message.id}>
                  <div className="user-message-label"><div className="avatar tiny">{userInitials}</div><span>You</span><time>Just now</time></div>
                  <div className="user-bubble">{message.text}</div>
                </article>
              ) : (
                <article className="assistant-message" key={message.id}>
                  <div className="assistant-heading"><div className="assistant-mark"><Sparkles size={15} /></div><span>Northstar</span><span className="verified-label"><ShieldCheck size={12} /> GROUNDED</span><time>Just now</time><button className="icon-button message-more" title="More options" aria-label="More options"><MoreHorizontal size={17} /></button></div>
                  <div className={`answer-card ${message.fallback ? "fallback-card" : ""}`}>
                    {message.fallback ? <div className="fallback-content"><div className="warning-icon"><CircleHelp size={17} /></div><div><strong>Outside your knowledge base</strong><p>{message.text}</p></div></div> : <div className="answer-copy">{(() => {
                      let citationIndex = 0;
                      return message.text.split(/(\[Doc: [^\]]+\])/g).map((part, index) => {
                        if (!part.startsWith("[Doc: ")) return <span key={index}>{part}</span>;
                        const citation = message.citations?.[citationIndex++];
                        if (!citation) return <span key={index}>{part}</span>;
                        return <CitationPill key={index} citation={citation} onOpen={() => setDrawerCitation(citation)} />;
                      });
                    })()}</div>}
                    {!message.fallback && <div className="answer-footer"><div className="answer-confidence"><span className="confidence-bars"><i /><i /><i /></span>Answer grounded in <strong>{message.citations?.length ?? 0} {message.citations?.length === 1 ? "source" : "sources"}</strong></div><div className="answer-actions"><button className={feedback[String(message.id)] === "up" ? "chosen" : ""} onClick={() => setFeedback((state) => ({ ...state, [String(message.id)]: state[String(message.id)] === "up" ? undefined : "up" }))} aria-label="Helpful answer" title="Helpful"><ThumbsUp size={14} /></button><button className={feedback[String(message.id)] === "down" ? "chosen" : ""} onClick={() => setFeedback((state) => ({ ...state, [String(message.id)]: state[String(message.id)] === "down" ? undefined : "down" }))} aria-label="Not helpful" title="Not helpful"><ThumbsDown size={14} /></button><span className="action-separator" /><button aria-label="Copy answer" title="Copy answer" onClick={() => navigator.clipboard?.writeText(message.text)}><Files size={14} /></button></div></div>}
                  </div>
                  {message.fallback && <div className="fallback-note"><ShieldCheck size={13} /> No unsupported answer was generated.</div>}
                </article>
              ))}
              {isLoading && <div className="loading-row"><div className="assistant-mark loading-mark"><Sparkles size={14} /></div><span>Searching your knowledge base</span><span className="loading-dots"><i /><i /><i /></span><div className="retrieval-status"><span /> HYBRID RETRIEVAL</div></div>}
              <div ref={feedEndRef} />
            </div>

            {messages.length > 0 && !isLoading && <div className="followup-hint"><span className="hint-line" /> Ask a follow-up to explore this topic <span className="hint-line" /></div>}
          </div>
        </div>

        <div className="composer-wrap">
          <form className="composer" onSubmit={submitQuery}>
            <textarea ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={handleInputKeyDown} placeholder="Ask anything about your company..." rows={1} aria-label="Ask your knowledge base" />
            <div className="composer-bottom"><div className="composer-hints"><span><Command size={12} /> Enter to send</span><span className="hint-divider">·</span><span>Shift + Enter for new line</span></div><button className="send-button" type="submit" disabled={!query.trim() || isLoading} title="Send message" aria-label="Send message"><ArrowUp size={17} /></button></div>
          </form>
          <div className="composer-footnote"><ShieldCheck size={12} /> Responses are grounded in authorized internal sources <span>·</span><button title="About grounded answers"><CircleHelp size={12} /></button></div>
        </div>
      </section>

      <aside className={`context-drawer ${drawerCitation ? "open" : ""}`} aria-label="Context and citations" aria-hidden={!drawerCitation}>
        {drawerCitation && <>
          <div className="drawer-header"><div><div className="drawer-eyebrow"><span className="drawer-live-dot" /> SOURCE CONTEXT</div><h2>Verified citation</h2></div><button className="icon-button drawer-close" onClick={() => setDrawerCitation(null)} aria-label="Close citation drawer" title="Close"><X size={18} /></button></div>
          <div className="drawer-scroll">
            <div className="source-card"><div className="source-file-icon"><FileText size={17} /></div><div className="source-info"><strong>{drawerCitation.title}</strong><span>{drawerCitation.docId}</span></div><button className="icon-button source-more" title="Source options" aria-label="Source options"><MoreHorizontal size={17} /></button></div>
            <div className="source-meta-grid"><div><span>SECTION</span><strong>{drawerCitation.section}</strong></div><div><span>LAST UPDATED</span><strong>{drawerCitation.updated}</strong></div></div>
            <div className="drawer-section-title"><div><span className="section-icon"><BookOpen size={13} /></span><strong>Retrieved passage</strong></div><span className="token-count">CHILD CHUNK · 250 TOKENS</span></div>
            <div className="excerpt-card"><span className="excerpt-label"><span /> MATCHED EXCERPT</span><p>{drawerCitation.childText}</p></div>
            <div className="parent-context-heading"><span>Parent context</span><span>~1,000 tokens</span></div>
            <div className="parent-context-text">{drawerCitation.parentText.split(drawerCitation.childText).length > 1 ? <>{drawerCitation.parentText.split(drawerCitation.childText)[0]}<mark>{drawerCitation.childText}</mark>{drawerCitation.parentText.split(drawerCitation.childText).slice(1).join(drawerCitation.childText)}</> : <>{drawerCitation.parentText}<mark>{drawerCitation.childText}</mark></>}</div>
            <div className="citation-id-block"><span>CITATION REFERENCE</span><code>{`[Doc: ${drawerCitation.docId}, Section: ${drawerCitation.section}]`}</code></div>
            <div className="access-note"><ShieldCheck size={14} /><span>Source access verified for your workspace</span><Check size={13} /></div>
          </div>
          <div className="drawer-footer"><button className="drawer-back" onClick={() => setDrawerCitation(null)}><ArrowLeft size={14} /> Back to answer</button><button className="open-source-button" title="Open source document" disabled={!drawerCitation.sourceUrl} onClick={() => drawerCitation.sourceUrl && window.open(drawerCitation.sourceUrl, "_blank", "noopener,noreferrer")}><ArrowDown size={14} /> Source details</button></div>
        </>}
      </aside>
      {drawerCitation && <button className="drawer-scrim" onClick={() => setDrawerCitation(null)} aria-label="Close citation drawer" />}
      <div className="system-health"><Gauge size={12} /><span>All systems operational</span><span className="health-dot" /></div>
    </main>
  );
}

export default function Home() {
  return <AuthGate><ChatWorkspace /></AuthGate>;
}