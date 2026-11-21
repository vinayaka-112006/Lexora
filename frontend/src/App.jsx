import { useCallback, useEffect, useRef, useState } from "react";
import {
  getChat,
  getChats,
  getCurrentUser,
  loginAccount,
  logout,
  registerAccount,
  searchNews,
  submitQuery,
} from "./api.js";
import { BotanicalLogo } from "./components/BotanicalEmblem.jsx";
import { LandingPage } from "./components/LandingPage.jsx";
import MarkdownMessage from "./components/MarkdownMessage.jsx";
import "./Chat.css";

function followUpSuggestions(originalQuestion) {
  const suggestions = [
    "Explain in simple words",
    "Show a detailed explanation",
  ];
  if (/\bpatent/i.test(originalQuestion)) {
    suggestions.push(
      "What are the patentability requirements?",
      "How does this apply to Ayurvedic products?",
    );
  }
  return suggestions;
}

function isGreetingOrIntro(text) {
  if (!text) return false;
  const trimmed = text.trim();
  return (
    /^(?:hello|hi|hey|greetings|good\s+(?:morning|afternoon|evening)|namaste|vanakkam)\b/i.test(
      trimmed,
    ) ||
    (/\b(?:i am|my name is)\s+[A-Za-z]+/i.test(trimmed) &&
      trimmed.length < 120) ||
    (/^(?:can i ask|can you help|i want some information about)/i.test(
      trimmed,
    ) &&
      trimmed.length < 80)
  );
}

function deriveFollowUpTopic(question) {
  if (!question) return "";
  const qLower = question.toLowerCase();
  const entities = [];
  if (qLower.includes("ashwagandha")) entities.push("Ashwagandha legal use");
  if (qLower.includes("neem")) entities.push("Neem");
  if (qLower.includes("turmeric")) entities.push("Turmeric");
  if (qLower.includes("karnataka")) entities.push("in Karnataka");
  if (qLower.includes("patent")) entities.push("patentability");
  if (
    qLower.includes("biodiversity") ||
    qLower.includes("bda") ||
    qLower.includes("sbb")
  ) {
    entities.push("Biological Diversity Act compliance");
  }
  if (
    qLower.includes("regulation") ||
    qLower.includes("regulations") ||
    qLower.includes("acts") ||
    qLower.includes("applicable")
  ) {
    entities.push("regulatory requirements");
  }
  if (entities.length >= 2) {
    return entities.join(", ");
  }
  return question
    .replace(
      /^(?:what is|what are|explain|describe|can i|is it legal to)\s+/i,
      "",
    )
    .replace(/[?.!]+$/, "")
    .trim();
}

const FOLLOW_UP_TOPIC_STOPWORDS = new Set([
  "about",
  "after",
  "again",
  "also",
  "apply",
  "because",
  "before",
  "being",
  "both",
  "could",
  "does",
  "from",
  "have",
  "into",
  "more",
  "most",
  "other",
  "should",
  "some",
  "such",
  "than",
  "that",
  "their",
  "there",
  "these",
  "they",
  "this",
  "under",
  "what",
  "when",
  "where",
  "which",
  "while",
  "with",
  "would",
  "your",
  "indian",
  "india",
  "legal",
  "law",
  "laws",
  "act",
  "section",
  "sections",
]);

function sharesConversationTopic(query, originalQuestion) {
  if (!originalQuestion) return false;
  const queryTerms = new Set(
    query.toLocaleLowerCase().match(/[a-z0-9]+/g) || [],
  );
  const topicTerms = (
    originalQuestion.toLocaleLowerCase().match(/[a-z0-9]+/g) || []
  ).filter((term) => term.length >= 5 && !FOLLOW_UP_TOPIC_STOPWORDS.has(term));
  return topicTerms.some((term) => queryTerms.has(term));
}

function isContextualFollowUp(query, originalQuestion = "") {
  if (!originalQuestion || isGreetingOrIntro(originalQuestion)) return false;

  const normalized = query
    .replace(/^\s*Follow-up request:\s*/i, "")
    .split(/\s+Context\s*:/i, 1)[0]
    .trim();

  if (
    /^(?:explain|show|give|provide)\b.*\b(?:simple words|detailed explanation)\b/i.test(
      normalized,
    )
  )
    return true;
  if (
    /^(?:yeh[, ]+)?give me (?:the )?summary(?:\s+(?:of (?:this|that|the above|our discussion|our conversation)|please))?[?.!]*$/i.test(
      normalized,
    )
  )
    return true;
  if (
    /^summari[sz]e (?:this|that|it|the above|the discussion|our discussion|our conversation)\b/i.test(
      normalized,
    )
  )
    return true;
  if (/^what about (?:in |for |the )/i.test(normalized)) return true;
  if (
    /^(?:can you|please)\s+(?:elaborate|explain more|clarify)\b/i.test(
      normalized,
    )
  )
    return true;

  const hasSubstantiveEntities =
    /\b(?:ashwagandha|patents?\s+act|biological\s+diversity|section\s+\d+|karnataka|fssai|ayush)\b/i.test(
      normalized,
    ) && normalized.length > 70;
  if (hasSubstantiveEntities) return false;

  if (
    normalized.length < 80 &&
    /\b(?:this|that|these|those|it|they)\b/i.test(normalized)
  )
    return true;
  if (/\bpatentability\b/i.test(normalized)) return true;

  return sharesConversationTopic(normalized, originalQuestion);
}

function followUpContext(originalQuestion, jurisdiction) {
  const isPatentTopic = /\bpatent\b/i.test(originalQuestion);
  const isBdaTopic =
    /\b(?:biodiversity|bda|sbb|nba|bmc|biological resource)/i.test(
      originalQuestion,
    );
  const topic = deriveFollowUpTopic(originalQuestion);
  const inferredJurisdiction = /\b(?:India|Indian law|Karnataka)\b/i.test(
    originalQuestion,
  )
    ? "India"
    : "";
  const contextJurisdiction = jurisdiction || inferredJurisdiction;
  const jurisdictionContext = contextJurisdiction
    ? `${contextJurisdiction} jurisdiction; `
    : "";
  const actContext =
    isPatentTopic && isBdaTopic
      ? "Patents Act and Biological Diversity Act; "
      : isPatentTopic
        ? "Patent Act; "
        : isBdaTopic
          ? "Biological Diversity Act; "
          : "";
  return `${actContext}${jurisdictionContext}original question: ${originalQuestion}; original topic: ${topic}`;
}

function responseMessage(result) {
  if (result.decision === "generation_error") {
    return "Sorry, the AI service could not generate an answer right now. Please try again.";
  }
  return typeof result.answer === "string" && result.answer.trim()
    ? result.answer
    : "The service did not return an answer.";
}

function AnswerClaims({ verification }) {
  const claims = (verification?.claims || []).filter(
    (claim) =>
      claim.status === "uncertain" &&
      claim.citation_valid === true &&
      claim.evidence_found === true &&
      typeof claim.text === "string" &&
      claim.text.trim() &&
      Array.isArray(claim.citations) &&
      claim.citations.some((citation) => typeof citation === "string" && citation.trim()),
  );

  if (!claims.length) return null;

  return (
    <section className="answer-claims" aria-label="Claims with matching citations">
      <h3>Claims with matching citations</h3>
      <ul>
        {claims.map((claim) => (
          <li key={claim.claim_id}>
            <p>{claim.text}</p>
            <p className="answer-claim-citations">
              {claim.citations.filter((citation) => typeof citation === "string" && citation.trim()).join(" ")}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function displayDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function App() {
  const [user, setUser] = useState(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [signOutLoading, setSignOutLoading] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authNotice, setAuthNotice] = useState("");
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [selectedChatId, setSelectedChatId] = useState("");
  const [loadingChatId, setLoadingChatId] = useState("");
  const [messages, setMessages] = useState([]);
  const [rootQuestion, setRootQuestion] = useState("");
  const [query, setQuery] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [newsOpen, setNewsOpen] = useState(false);
  const [newsQuery, setNewsQuery] = useState("");
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState("");
  const [newsResult, setNewsResult] = useState(null);
  const inputRef = useRef(null);
  const historyRequestId = useRef(0);

  useEffect(() => {
    let active = true;
    getCurrentUser()
      .then((result) => {
        if (active && result.user)
          setUser({ name: result.user.name, email: result.user.email });
      })
      .catch((error) => {
        if (active && error.status !== 401) setAuthError(error.message);
      })
      .finally(() => {
        if (active) setSessionLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const returnToLogin = useCallback((notice = "") => {
    historyRequestId.current += 1;
    setUser(null);
    setHistory([]);
    setMessages([]);
    setRootQuestion("");
    setSelectedChatId("");
    setLoadingChatId("");
    setPassword("");
    setAuthMode("login");
    setAuthError("");
    setAuthNotice(notice);
    setHistoryError("");
    setHistoryLoading(false);
    setSidebarOpen(false);
  }, []);

  const refreshHistory = useCallback(
    async ({ showLoading = true } = {}) => {
      const requestId = ++historyRequestId.current;
      if (showLoading) setHistoryLoading(true);
      setHistoryError("");
      try {
        const chats = await getChats();
        if (requestId === historyRequestId.current) setHistory(chats);
      } catch (error) {
        if (requestId !== historyRequestId.current) return;
        if (error.status === 401) {
          returnToLogin("Your session has expired. Please sign in again.");
        } else {
          setHistoryError(error.message);
        }
      } finally {
        if (requestId === historyRequestId.current && showLoading)
          setHistoryLoading(false);
      }
    },
    [returnToLogin],
  );

  useEffect(() => {
    if (user) void refreshHistory();
  }, [user, refreshHistory]);

  async function handleAuthSubmit(event) {
    event.preventDefault();
    if (authLoading) return;
    setAuthLoading(true);
    setAuthError("");
    setAuthNotice("");
    try {
      if (authMode === "register") {
        await registerAccount({
          name: name.trim(),
          email: email.trim(),
          password,
        });
        setPassword("");
        setAuthMode("login");
        setAuthNotice("Account created. Sign in to continue.");
      } else {
        const result = await loginAccount({ email: email.trim(), password });
        if (!result.user)
          throw new Error("Sign in could not be completed. Please try again.");
        setPassword("");
        let session;
        try {
          session = await getCurrentUser();
        } catch (error) {
          if (error.status === 401) {
            throw new Error(
              "Sign-in succeeded, but the browser session cookie was not accepted. Check the local host and cookie settings, then try again.",
              { cause: error },
            );
          }
          throw error;
        }
        if (!session.user)
          throw new Error(
            "Sign-in succeeded, but the browser session could not be verified. Please try again.",
          );
        setUser({ name: session.user.name, email: session.user.email });
        setAuthNotice("");
        setMessages([]);
        setRootQuestion("");
        setSelectedChatId("");
      }
    } catch (error) {
      setAuthError(
        error.message ||
          "Authentication could not be completed. Please try again.",
      );
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    if (signOutLoading) return;
    setSignOutLoading(true);
    try {
      await logout();
    } catch {
      // Clear local session state even if the server cannot clear the cookie.
    } finally {
      returnToLogin("You have signed out. Sign in to continue.");
      setSignOutLoading(false);
    }
  }

  async function submitQuestion(submittedQuery) {
    if (loading) return;
    if (!submittedQuery) {
      setValidationError("Enter a question before sending it.");
      inputRef.current?.focus();
      return;
    }

    const isFollowUp = isContextualFollowUp(submittedQuery, rootQuestion);
    const hasEmbeddedContext = /\bContext:/i.test(submittedQuery);
    const rootQuestionForRequest = isFollowUp
      ? rootQuestion
      : hasEmbeddedContext
        ? ""
        : submittedQuery;
    if (
      !isFollowUp &&
      !hasEmbeddedContext &&
      !isGreetingOrIntro(submittedQuery)
    ) {
      setRootQuestion(submittedQuery);
    }
    const queryWithContext =
      rootQuestionForRequest && isFollowUp && !hasEmbeddedContext
        ? `${submittedQuery}\n\nContext: ${followUpContext(rootQuestionForRequest, jurisdiction)}`
        : submittedQuery;

    setValidationError("");
    setMessages((current) => [
      ...current,
      { role: "user", text: submittedQuery },
    ]);
    setQuery("");
    setSelectedChatId("");
    setLoading(true);
    setSidebarOpen(false);

    try {
      const result = await submitQuery(
        queryWithContext,
        jurisdiction || undefined,
        messages,
      );
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: responseMessage(result),
          decision: result.decision,
          confidence: result.confidence,
          citations: result.citations,
          sources: result.sources,
          retrieved_evidence: result.retrieved_evidence,
          abstention_reason: result.abstention_reason,
          claim_verification: result.claim_verification,
          retrieval_diagnostic: result.retrieval_diagnostic,
          warnings: result.warnings,
          parentQuery: submittedQuery,
        },
      ]);
      await refreshHistory({ showLoading: false });
    } catch (error) {
      if (error.status === 401) {
        returnToLogin("Your session has expired. Please sign in again.");
        return;
      }
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          decision: "client_error",
          text: error.message,
        },
      ]);
      setQuery(submittedQuery);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await submitQuestion(query.trim());
  }

  async function handleNewsSubmit(event) {
    event.preventDefault();
    if (newsLoading || !newsQuery.trim()) return;
    setNewsLoading(true);
    setNewsError("");
    setNewsResult(null);
    try {
      setNewsResult(await searchNews(newsQuery.trim()));
    } catch (error) {
      setNewsError(
        error.message ||
          "Unable to retrieve current information right now. Please try again.",
      );
    } finally {
      setNewsLoading(false);
    }
  }

  async function handleSelectChat(chatId) {
    setLoadingChatId(chatId);
    setHistoryError("");
    try {
      const chat = await getChat(chatId);
      setSelectedChatId(chatId);
      setRootQuestion(/\bContext:/i.test(chat.query) ? "" : chat.query);
      setMessages([
        { role: "user", text: chat.query },
        {
          role: "assistant",
          text: responseMessage({
            answer: chat.answer,
            decision: chat.decision,
          }),
          decision: chat.decision,
          confidence: chat.confidence,
          citations: chat.citations,
          sources: [],
          retrieved_evidence: [],
          abstention_reason: chat.abstentionReason,
          claim_verification: null,
          retrieval_diagnostic: null,
          warnings: [],
        },
      ]);
      setSidebarOpen(false);
    } catch (error) {
      if (error.status === 401) {
        returnToLogin("Your session has expired. Please sign in again.");
      } else {
        setHistoryError(error.message);
      }
    } finally {
      setLoadingChatId("");
    }
  }

  if (sessionLoading) {
    return (
      <main className="app-shell loading-shell">
        <header className="app-header">
          <div className="brand-mark-wrapper">
            <BotanicalLogo size={36} />
          </div>
          <div>
            <p className="eyebrow">Lexora</p>
            <h1>Legal research assistant</h1>
          </div>
        </header>
        <div className="loading-card-body">
          <div className="loading-spinner" aria-hidden="true"></div>
          <p className="history-state" role="status">
            Checking your session…
          </p>
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <LandingPage
        mode={authMode}
        setMode={(mode) => {
          setAuthMode(mode);
          setAuthError("");
          setAuthNotice("");
        }}
        name={name}
        setName={setName}
        email={email}
        setEmail={setEmail}
        password={password}
        setPassword={setPassword}
        loading={authLoading}
        error={authError}
        notice={authNotice}
        onSubmit={handleAuthSubmit}
      />
    );
  }

  return (
    <main className="app-shell workspace-shell">
      {/* Top Application Workspace Header */}
      <header className="app-header">
        <button
          type="button"
          className="sidebar-toggle-btn"
          aria-label="Toggle chat history"
          onClick={() => setSidebarOpen((prev) => !prev)}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        <div className="brand-mark-wrapper">
          <BotanicalLogo size={38} />
        </div>

        <div className="app-header-copy">
          <p className="eyebrow">Lexora</p>
          <h1>Legal research assistant</h1>
        </div>

        <div className="app-header-domain-pill" aria-hidden="true">
          <span className="domain-pill-dot"></span>
          Ayurveda &amp; IP Statutes Active
        </div>

        <div className="app-header-actions">
          <button
            type="button"
            className="news-launch-button"
            onClick={() => setNewsOpen(true)}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M4 4h16v16H4z" />
              <path d="M8 8h8M8 12h8M8 16h5" />
            </svg>
            Recent News?
          </button>
          <div className="user-profile-badge">
            <div className="user-avatar" aria-hidden="true">
              {(user.name || user.email || "U")[0].toUpperCase()}
            </div>
            <span className="user-greeting">{user.name || user.email}</span>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={handleLogout}
            disabled={signOutLoading}
          >
            {signOutLoading ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </header>

      {/* Main Workspace Layout (Sidebar + Chat Area) */}
      <div className="chat-layout">
        {/* Chat History Sidebar */}
        <aside
          className={`history-panel ${sidebarOpen ? "history-panel-open" : ""}`}
          aria-label="Chat history"
        >
          <div className="history-heading">
            <div className="history-title-group">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <h2>Chat history</h2>
            </div>
            <button
              type="button"
              className="new-chat-btn"
              onClick={() => {
                setMessages([]);
                setRootQuestion("");
                setSelectedChatId("");
                setQuery("");
                setSidebarOpen(false);
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                aria-hidden="true"
              >
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              New chat
            </button>
          </div>

          {historyLoading && (
            <p className="history-state" role="status">
              Loading history…
            </p>
          )}
          {historyError && (
            <p className="form-error" role="alert">
              {historyError}
            </p>
          )}
          {!historyLoading && history.length === 0 && !historyError && (
            <div className="history-empty-state">
              <p className="history-state">
                Your saved conversations will appear here.
              </p>
            </div>
          )}

          <ul className="history-list">
            {history.map((chat) => (
              <li key={chat.id}>
                <button
                  type="button"
                  className={`history-item${selectedChatId === chat.id ? " history-item-active" : ""}`}
                  aria-current={selectedChatId === chat.id ? "page" : undefined}
                  disabled={Boolean(loadingChatId)}
                  onClick={() => handleSelectChat(chat.id)}
                >
                  <span className="history-query">{chat.query}</span>
                  <div className="history-item-meta">
                    <time dateTime={chat.createdAt}>
                      {displayDate(chat.createdAt)}
                    </time>
                    {chat.jurisdiction && (
                      <span className="history-jurisdiction-tag">
                        {chat.jurisdiction}
                      </span>
                    )}
                  </div>
                  {loadingChatId === chat.id && (
                    <span className="history-loading">Loading…</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Backdrop for mobile drawer */}
        {sidebarOpen && (
          <div
            className="sidebar-backdrop"
            aria-hidden="true"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Chat Main Area */}
        <section className="chat-main">
          <section
            className="conversation"
            aria-label="Conversation"
            aria-live="polite"
          >
            {messages.length === 0 ? (
              <div className="welcome-message">
                <div className="welcome-emblem">
                  <BotanicalLogo size={52} />
                </div>
                <h2>What would you like to know?</h2>
                <p>
                  Ask about intellectual-property law and related regulations.
                </p>

                {/* Quick starter suggestion chips */}
                <div
                  className="starter-chips-container"
                  aria-label="Suggested starter queries"
                >
                  <p className="starter-chips-label">
                    Frequently researched statutory topics:
                  </p>
                  <div className="starter-chips">
                    <button
                      type="button"
                      className="starter-chip"
                      onClick={() =>
                        submitQuestion("What is a patent under Indian law?")
                      }
                      disabled={loading}
                    >
                      <span className="starter-chip-icon">⚖️</span>
                      What is a patent under Indian law?
                    </button>
                    <button
                      type="button"
                      className="starter-chip"
                      onClick={() =>
                        submitQuestion(
                          "I am an Indian citizen starting an Ayurvedic company in Karnataka. I want to purchase cultivated Ashwagandha roots from a local farmer who cultivates them on private agricultural land. What permissions and legal requirements apply under the Biological Diversity Act?",
                        )
                      }
                      disabled={loading}
                    >
                      <span className="starter-chip-icon">🌿</span>
                      Cultivated Ashwagandha roots permissions under BDA
                    </button>
                    <button
                      type="button"
                      className="starter-chip"
                      onClick={() =>
                        submitQuestion(
                          "Explain the non-patentable inventions under Section 3 of the Patents Act, 1970.",
                        )
                      }
                      disabled={loading}
                    >
                      <span className="starter-chip-icon">📜</span>
                      Non-patentable exclusions under Section 3
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              messages.map((message, index) => {
                const precedingUser = messages
                  .slice(0, index)
                  .reverse()
                  .find((m) => m.role === "user");
                const rawParent =
                  message.parentQuery ||
                  precedingUser?.text ||
                  rootQuestion ||
                  "";
                const parentQuestion = rawParent
                  .replace(
                    /^\s*Follow-up request:\s*[^]*?\n\nContext:\s*(?:[^;]*;\s*)*original question:\s*/i,
                    "",
                  )
                  .replace(/;\s*original topic:.*$/i, "")
                  .trim();
                const canSuggest =
                  ["answer", "answer_with_caution"].includes(
                    message.decision,
                  ) && !isGreetingOrIntro(parentQuestion);

                return (
                  <article
                    className={`message message-${message.role}`}
                    key={`${message.role}-${index}`}
                  >
                    <div className="message-header">
                      <p className="message-label">
                        {message.role === "user" ? "You" : "Lexora"}
                      </p>
                      {message.role === "assistant" &&
                        message.decision &&
                        message.decision !== "general" &&
                        message.decision !== "answer_with_caution" && (
                          <div
                            className={`decision-badge decision-${message.decision}`}
                          >
                            {message.decision === "abstain" &&
                              "Insufficient evidence"}
                            {message.decision === "answer" && "Answer"}
                            {message.decision === "clarification" &&
                              "Clarification needed"}
                            {message.decision === "generation_error" &&
                              "Service unavailable"}
                            {message.decision === "generation_incomplete" &&
                              "Incomplete response"}
                            {message.decision === "client_error" &&
                              "Request error"}
                          </div>
                        )}
                    </div>

                    <div className="message-text">
                      {message.role === "assistant" ? (
                        <MarkdownMessage>{message.text}</MarkdownMessage>
                      ) : (
                        message.text
                      )}
                    </div>

                    {message.role === "assistant" && (
                      <AnswerClaims verification={message.claim_verification} />
                    )}

                    {message.decision === "abstain" &&
                      message.abstention_reason &&
                      !message.text
                        .toLocaleLowerCase()
                        .includes(
                          message.abstention_reason.toLocaleLowerCase(),
                        ) && (
                        <p className="abstention-reason">
                          {message.abstention_reason}
                        </p>
                      )}

                    {message.role === "assistant" &&
                      canSuggest &&
                      parentQuestion && (
                        <div
                          className="follow-up-suggestions"
                          aria-label="Suggested follow-up questions"
                        >
                          <p>Explore this topic</p>
                          <div className="follow-up-buttons">
                            {followUpSuggestions(parentQuestion).map(
                              (suggestion) => (
                                <button
                                  key={suggestion}
                                  type="button"
                                  className="follow-up-button"
                                  disabled={loading}
                                  onClick={() =>
                                    submitQuestion(
                                      `Follow-up request: ${suggestion}\n\nContext: ${followUpContext(parentQuestion, jurisdiction)}`,
                                    )
                                  }
                                >
                                  {suggestion}
                                </button>
                              ),
                            )}
                          </div>
                        </div>
                      )}
                  </article>
                );
              })
            )}

            {loading && (
              <div className="loading-container">
                <div className="loading-pulse-dots" aria-hidden="true">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <p className="loading-indicator" role="status">
                  Searching legal sources and preparing an answer…
                </p>
              </div>
            )}
          </section>

          {/* Chat Query Input Form */}
          <form className="query-form" onSubmit={handleSubmit}>
            <label className="jurisdiction-field">
              <span className="visually-hidden">Jurisdiction</span>
              <div className="select-wrapper">
                <select
                  aria-label="Jurisdiction"
                  value={jurisdiction}
                  onChange={(event) => setJurisdiction(event.target.value)}
                  disabled={loading}
                >
                  <option value="">Service default</option>
                  <option value="India">India</option>
                  <option value="International">International</option>
                </select>
              </div>
            </label>

            <label className="query-field">
              <span className="visually-hidden">Your question</span>
              <textarea
                ref={inputRef}
                aria-label="Your question"
                placeholder="Ask about patents, biodiversity, Ayurveda regulations..."
                rows="2"
                value={query}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    if (!loading && query.trim()) {
                      void handleSubmit(event);
                    }
                  }
                }}
                onChange={(event) => {
                  setQuery(event.target.value);
                  if (validationError) setValidationError("");
                }}
                disabled={loading}
              />
            </label>

            <button type="submit" className="send-btn" disabled={loading}>
              {loading ? (
                "Sending…"
              ) : (
                <>
                  <span>Send</span>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </>
              )}
            </button>

            {validationError && (
              <p className="form-error" role="alert">
                {validationError}
              </p>
            )}
          </form>
        </section>
      </div>
      {newsOpen && (
        <div
          className="news-overlay"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setNewsOpen(false);
          }}
        >
          <section
            className="news-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="news-title"
          >
            <header className="news-panel-header">
              <div>
                <p className="eyebrow">Independent web search</p>
                <h2 id="news-title">News &amp; Web Research</h2>
                <p>
                  Explore the latest developments in Ayurveda, herbal research,
                  regulations and more.
                </p>
              </div>
              <button
                type="button"
                className="news-close-button"
                aria-label="Close research panel"
                onClick={() => setNewsOpen(false)}
              >
                ×
              </button>
            </header>
            <form className="news-search-form" onSubmit={handleNewsSubmit}>
              <label htmlFor="news-query">Search current information</label>
              <div className="news-search-row">
                <input
                  id="news-query"
                  type="search"
                  maxLength={500}
                  value={newsQuery}
                  onChange={(event) => {
                    setNewsQuery(event.target.value);
                    setNewsError("");
                  }}
                  placeholder="Ask about recent news or any current development..."
                />
                <button
                  type="submit"
                  disabled={newsLoading || !newsQuery.trim()}
                >
                  {newsLoading ? "Searching…" : "Search"}
                </button>
              </div>
            </form>
            <div className="news-suggestions" aria-label="Suggested searches">
              {[
                "Latest Ayurveda news in India",
                "Recent AYUSH government announcements",
                "Latest research on Ashwagandha",
                "Recent herbal medicine regulations",
                "International traditional medicine developments",
              ].map((suggestion) => (
                <button
                  type="button"
                  key={suggestion}
                  disabled={newsLoading}
                  onClick={() => setNewsQuery(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
            <div className="news-content" aria-live="polite">
              {newsLoading && (
                <p className="news-status" role="status">
                  Searching the web for the latest updates...
                </p>
              )}
              {newsError && (
                <p className="news-error" role="alert">
                  {newsError}
                </p>
              )}
              {!newsLoading &&
                !newsError &&
                newsResult &&
                newsResult.results.length === 0 && (
                  <p className="news-status">
                    No relevant results found. Try a different search query.
                  </p>
                )}
              {!newsLoading && newsResult && newsResult.results.length > 0 && (
                <>
                  {newsResult.answer && (
                    <section className="news-answer">
                      <h3>Search summary</h3>
                      <p>{newsResult.answer}</p>
                    </section>
                  )}
                  <h3 className="news-sources-heading">Sources</h3>
                  <div className="news-results">
                    {newsResult.results.map((result) => {
                      const date =
                        result.publishedDate &&
                        !Number.isNaN(Date.parse(result.publishedDate))
                          ? new Date(result.publishedDate).toLocaleDateString(
                              undefined,
                              {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              },
                            )
                          : "Date unavailable";
                      return (
                        <article className="news-result-card" key={result.url}>
                          <h4>{result.title}</h4>
                          <p>
                            {result.description || "No description available."}
                          </p>
                          <div className="news-result-meta">
                            <span>{result.source || "Source unavailable"}</span>
                            <span>{date}</span>
                          </div>
                          <a href={result.url} target="_blank" rel="noreferrer">
                            Read original article{" "}
                            <span aria-hidden="true">↗</span>
                          </a>
                        </article>
                      );
                    })}
                  </div>
                </>
              )}
              {!newsLoading && !newsError && !newsResult && (
                <p className="news-status">
                  Ask about recent news, research, policy announcements or any
                  current event.
                </p>
              )}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

export default App;

// The main responsibility of App.jsx is to:
// 1. Manage login and registration.
// 2. Maintain the current user's session.
// 3. Manage chat messages and conversation history.
// 4. Submit legal questions to the backend.
// 5. Maintain context for follow-up questions.
// 6. Display answers, citations, and retrieval diagnostics.
// 7. Handle independent news searches.
// 8. Control the overall application UI.
// Important: App.jsx does not perform the actual legal retrieval or AI answer generation. It sends requests through api.js and displays the responses received from the backend.
