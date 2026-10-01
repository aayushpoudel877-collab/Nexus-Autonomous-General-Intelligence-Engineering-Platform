"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
type Conversation = { id: string; title: string; course_id: string | null };
type Message = { id: string; role: string; content: string; created_at: string };

export default function TutorPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function request(path: string, init?: RequestInit) {
    const response = await fetch(API + path, {
      ...init, credentials: "include",
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail ?? "Request failed. Please sign in and try again.");
    }
    return response.json();
  }

  async function refreshConversations() {
    const rows = await request("/tutor/conversations") as Conversation[];
    setConversations(rows);
  }

  async function createConversation() {
    setError("");
    try {
      const row = await request("/tutor/conversations", {
        method: "POST", body: JSON.stringify({ title: "New tutoring session" }),
      }) as Conversation;
      setConversations((old) => [row, ...old]);
      setActive(row.id);
      setMessages([]);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to create conversation."); }
  }

  async function openConversation(id: string) {
    setError("");
    try {
      const row = await request("/tutor/conversations/" + id) as { messages: Message[] };
      setActive(id);
      setMessages(row.messages ?? []);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load conversation."); }
  }

  async function sendMessage() {
    const text = question.trim();
    if (!text || !active || loading) return;
    setLoading(true); setError(""); setQuestion("");
    const optimistic: Message = { id: crypto.randomUUID(), role: "user", content: text, created_at: new Date().toISOString() };
    setMessages((old) => [...old, optimistic]);
    try {
      const reply = await request("/tutor/conversations/" + active + "/messages", {
        method: "POST", body: JSON.stringify({ content: text }),
      }) as Message;
      setMessages((old) => [...old, reply]);
      await refreshConversations();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tutor request failed.");
    } finally { setLoading(false); }
  }

  useEffect(() => { refreshConversations().catch((e) => setError(e.message)); }, []);

  return <main className="shell">
    <div className="dashboard-top">
      <div><p className="eyebrow">NEXUS LEARNING INTELLIGENCE</p><h1>AI Tutor</h1><p className="lead">Ask questions, review course material, and keep your tutoring sessions in one place.</p></div>
      <a className="secondary" href="/lms">Back to LMS</a>
    </div>
    <section className="grid dashboard-grid">
      <article>
        <h2>Your sessions</h2>
        <button className="secondary" onClick={createConversation}>New session</button>
        {conversations.map((c) => <p key={c.id}><button className="secondary" onClick={() => openConversation(c.id)}>{c.title}</button></p>)}
      </article>
      <article>
        <h2>Learning conversation</h2>
        <div aria-live="polite">{messages.map((m) => <div key={m.id}><p className="eyebrow">{m.role === "assistant" ? "NEXUS TUTOR" : "YOU"}</p><p style={{ whiteSpace: "pre-wrap" }}>{m.content}</p></div>)}</div>
        {error && <p role="alert">{error}</p>}
        {!active && <p>Create a session to start. You must be signed in.</p>}
        <form onSubmit={(e) => { e.preventDefault(); void sendMessage(); }}>
          <label htmlFor="tutor-question">Your question</label>
          <textarea id="tutor-question" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={8000} rows={4} placeholder="What would you like to understand?" />
          <button type="submit" disabled={!active || loading || !question.trim()}>{loading ? "Thinking…" : "Send question"}</button>
        </form>
        <p className="muted">Provider status: local fallback unless a hosted AI provider is configured. The fallback is transparent and does not pretend to be a live model.</p>
      </article>
    </section>
  </main>;
}
