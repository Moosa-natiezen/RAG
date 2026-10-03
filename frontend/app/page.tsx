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

type Citation = {
  id: string;
  docId: string;
  section: string;
  title: string;
  updated: string;
  parentText: string;
  childText: string;
};

type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  fallback?: boolean;
};

const travelCitation: Citation = {
  id: "travel-expense",
  docId: "hr_policy_2026_v3",
  section: "Section 4.2 - Travel Expense Reimbursement",
  title: "Remote Work & Expense Policy 2026",
  updated: "Aug 15, 2026",
  parentText:
    "Employees traveling internationally for approved business are eligible for a daily meal stipend. The stipend is intended to cover reasonable meal costs during the trip. Receipts for travel expenses must be submitted through the Expense Portal within 14 business days after the expense is incurred. Managers review submissions against the applicable travel policy before reimbursement is approved.",
  childText:
    "Employees are eligible for a daily meal stipend of up to $75 during international business travel. Receipts must be submitted within 14 business days via the Expense Portal.",
};

const citationToken = `[Doc: ${travelCitation.docId}, Section: ${travelCitation.section}]`;

const initialMessages: ChatMessage[] = [
  {
    id: 1,
    role: "user",
    text: "What is the deadline for submitting travel expense receipts, and what is the meal allowance for overseas trips?",
  },
  {
    id: 2,
    role: "assistant",
    text: `Submit receipts through the Expense Portal within 14 business days. ${citationToken}\n\nFor international business travel, the daily meal stipend is up to $75. ${citationToken}`,
    citations: [travelCitation],
  },
];

const historyItems = [
  { title: "Travel expense receipt deadline", date: "Today", active: true },
  { title: "Customer data password policy", date: "Today" },
  { title: "Engineering access review", date: "Yesterday" },
  { title: "Remote work equipment policy", date: "Yesterday" },
  { title: "Q3 procurement thresholds", date: "Previous 7 days" },
  { title: "Incident response ownership", date: "Previous 7 days" },
];

function CitationPill({ citation, onOpen }: { citation: Citation; onOpen: () => void }) {
  return (
    <button className="citation-pill" onClick={onOpen} type="button" aria-label={`Open source: ${citation.docId}, ${citation.section}`} data-tooltip={citation.childText}>
      {`[Doc: ${citation.docId}, Section: ${citation.section}]`}
    </button>
  );
}

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
    const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [drawerCitation, setDrawerCitation] = useState<Citation | null>(null);
  const [messages, setMessages] = useState(initialMessages);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState<Record<number, "up" | "down" | undefined>>({});
  const [searchOpen, setSearchOpen] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("");
  const feedEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isLoading]);

  function startNewChat() {
    setMessages([]);
    setDrawerCitation(null);
    setMobileSidebarOpen(false);
    setQuery("");
    inputRef.current?.focus();
  }

  function submitQuery(event?: FormEvent) {
    event?.preventDefault();
    const question = query.trim();
    if (!question || isLoading) return;

    setMessages((current) => [...current, { id: Date.now(), role: "user", text: question }]);
    setQuery("");
    setIsLoading(true);

    window.setTimeout(() => {
      const isTravelQuestion = /travel|receipt|expense|meal|stipend|overseas|international/i.test(question);
      const nextMessage: ChatMessage = isTravelQuestion
        ? {
            id: Date.now() + 1,
            role: "assistant",
            text: `Receipts are due within 14 business days through the Expense Portal. ${citationToken}\n\nThe meal stipend for international business travel is up to $75 per day. ${citationToken}`,
            citations: [travelCitation],
          }
        : {
            id: Date.now() + 1,
            role: "assistant",
            text: "Information not found in internal knowledge base.",
            fallback: true,
          };
      setMessages((current) => [...current, nextMessage]);
      setIsLoading(false);
    }, 1150);
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
              <button className={`history-item ${item.active && messages.length > 0 ? "selected" : ""}`} key={item.title} onClick={() => { setMobileSidebarOpen(false); item.active ? setMessages(initialMessages) : startNewChat(); }}>
                <MessageSquare size={15} /><span>{item.title}</span>{index === 0 && item.active && <span className="history-active-dot" />}
              </button>
            ))}
            {visibleHistory.length === 0 && <p className="empty-history">No matches found</p>}
            <div className="history-divider" />
            <button className="sidebar-nav-item"><Files size={15} /><span>Knowledge sources</span><span className="nav-count">12</span></button>
          </div>

          <div className="sidebar-bottom">
            <div className="workspace-status"><span className="status-pulse" /><div><strong>Knowledge base</strong><small>Synced just now</small></div><Check size={14} /></div>
            <button className="account-button"><div className="avatar">MQ</div><span className="account-copy"><strong>Moosa Qureshi</strong><small>Workspace member</small></span><ChevronDown size={14} /></button>
          </div>
        </>}
        {!sidebarOpen && <div className="collapsed-rail">
          <button className="rail-icon" onClick={startNewChat} title="New chat"><Plus size={17} /></button>
          <button className="rail-icon" onClick={() => setSearchOpen((open) => !open)} title="Search conversations"><Search size={17} /></button>
          <button className="rail-icon active" title="Chat history"><Clock3 size={17} /></button>
          <button className="rail-icon" title="Knowledge sources"><Files size={17} /></button>
          <div className="rail-spacer" /><div className="avatar small">MQ</div>
          <div className="rail-spacer" /><div className="avatar small">MQ</div>
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
            <button className="user-chip"><span className="avatar tiny">MQ</span><span>Moosa</span><ChevronDown size={13} /></button>
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
              {messages.map((message) => message.role === "user" ? (
                <article className="user-message" key={message.id}>
                  <div className="user-message-label"><div className="avatar tiny">MQ</div><span>You</span><time>Just now</time></div>
                  <div className="user-bubble">{message.text}</div>
                </article>
              ) : (
                <article className="assistant-message" key={message.id}>
                  <div className="assistant-heading"><div className="assistant-mark"><Sparkles size={15} /></div><span>Northstar</span><span className="verified-label"><ShieldCheck size={12} /> GROUNDED</span><time>Just now</time><button className="icon-button message-more" title="More options" aria-label="More options"><MoreHorizontal size={17} /></button></div>
                  <div className={`answer-card ${message.fallback ? "fallback-card" : ""}`}>
                    {message.fallback ? <div className="fallback-content"><div className="warning-icon"><CircleHelp size={17} /></div><div><strong>Outside your knowledge base</strong><p>{message.text}</p></div></div> : <div className="answer-copy">{message.text.split(/(\[Doc: [^\]]+\])/g).map((part, index) => {
                      if (!part.startsWith("[Doc: ")) return <span key={index}>{part}</span>;
                      return <CitationPill key={index} citation={message.citations?.[0] ?? travelCitation} onOpen={() => setDrawerCitation(message.citations?.[0] ?? travelCitation)} />;
                    })}</div>}
                    {!message.fallback && <div className="answer-footer"><div className="answer-confidence"><span className="confidence-bars"><i /><i /><i /></span>Answer grounded in <strong>1 source</strong></div><div className="answer-actions"><button className={feedback[message.id] === "up" ? "chosen" : ""} onClick={() => setFeedback((state) => ({ ...state, [message.id]: state[message.id] === "up" ? undefined : "up" }))} aria-label="Helpful answer" title="Helpful"><ThumbsUp size={14} /></button><button className={feedback[message.id] === "down" ? "chosen" : ""} onClick={() => setFeedback((state) => ({ ...state, [message.id]: state[message.id] === "down" ? undefined : "down" }))} aria-label="Not helpful" title="Not helpful"><ThumbsDown size={14} /></button><span className="action-separator" /><button aria-label="Copy answer" title="Copy answer" onClick={() => navigator.clipboard?.writeText(message.text)}><Files size={14} /></button></div></div>}
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
          <div className="drawer-footer"><button className="drawer-back" onClick={() => setDrawerCitation(null)}><ArrowLeft size={14} /> Back to answer</button><button className="open-source-button" title="Open source document"><ArrowDown size={14} /> Source details</button></div>
        </>}
      </aside>
      {drawerCitation && <button className="drawer-scrim" onClick={() => setDrawerCitation(null)} aria-label="Close citation drawer" />}
      <div className="system-health"><Gauge size={12} /><span>All systems operational</span><span className="health-dot" /></div>
    </main>
  );
}