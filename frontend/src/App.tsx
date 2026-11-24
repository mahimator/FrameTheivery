import { useEffect, useMemo, useState } from "react";
import { ArrowDownToLine, CheckCircle2, CircleAlert, Clock3, FileVideo2, Link2, LoaderCircle, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
type Job = { id: string; status: string; result?: { filename: string; bytes: number; sha256: string; path: string } | null; error?: string | null };
export default function App() {
  const [urls, setUrls] = useState("");
  const [token, setToken] = useState(localStorage.getItem("ft_token") || "");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [showToken, setShowToken] = useState(!localStorage.getItem("ft_token"));
  const parsed = useMemo(() => [...new Set(urls.split(/\s+/).map(x => x.trim()).filter(Boolean))], [urls]);
  const completed = jobs.filter(j => j.status === "finished").length;
  const failed = jobs.filter(j => j.status === "failed").length;
  const active = jobs.filter(j => ["queued","started","deferred"].includes(j.status)).length;

  async function request(path: string, init: RequestInit = {}) {
    const response = await fetch(API + path, { ...init, headers: { "Content-Type": "application/json", Authorization: "Bearer " + token, ...(init.headers || {}) } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail?.message || body.detail || body.error || response.statusText);
    return body;
  }
  async function refresh() {
    if (!token) return;
    try { const data = await request("/api/v1/jobs"); setJobs(data.jobs || []); } catch (e) { setMessage(e instanceof Error ? e.message : "Unable to refresh queue"); }
  }
  useEffect(() => { refresh(); const id = setInterval(refresh, 2500); return () => clearInterval(id); }, [token]);
  async function submit() {
    if (!token) { setShowToken(true); return; }
    if (!parsed.length) return;
    setBusy(true); setMessage("");
    try {
      const data = await request("/api/v1/batches", { method: "POST", body: JSON.stringify({ urls: parsed, concurrency: 3 }) });
      setMessage(`Queued ${data.accepted.length} URLs. ${data.rejected.length} rejected.`);
      setUrls(""); await refresh();
    } catch (e) { setMessage(e instanceof Error ? e.message : "Could not queue URLs"); }
    finally { setBusy(false); }
  }
  function saveToken() { localStorage.setItem("ft_token", token); setShowToken(false); refresh(); }
  const fmt = (n: number) => n < 1024 ? n + " B" : n < 1048576 ? (n/1024).toFixed(1)+" KB" : (n/1048576).toFixed(1)+" MB";
  return <main className="shell">
    <header><a className="brand" href="#"><span className="brandmark"><FileVideo2 size={20}/></span><span>frame<span className="accent">theivery</span></span></a><div className="header-right"><span className="secure"><ShieldCheck size={14}/> PRIVATE INSTANCE</span><button className="icon-button" onClick={refresh} title="Refresh queue"><RefreshCw size={17}/></button></div></header>
    <section className="hero"><div className="eyebrow">PERSONAL MEDIA TRANSFER</div><h1>Bring your media<br/><span className="muted">together.</span></h1><p>Queue direct media URLs in bulk. Let the server handle the transfers while you get on with your work.</p></section>
    <section className="composer panel">
      <div className="section-title"><div><span className="step">01</span><h2>Source URLs</h2></div><span className="count">{parsed.length} URL{parsed.length===1?"":"s"} detected</span></div>
      <textarea value={urls} onChange={e=>setUrls(e.target.value)} placeholder={"Paste one direct media URL per line…\nhttps://example.com/video.mp4\nhttps://cdn.example.com/another-video.mp4"} spellCheck={false}/>
      <div className="composer-footer"><span>One URL per line · duplicates removed automatically</span><button className="primary" disabled={!parsed.length || busy} onClick={submit}>{busy?<LoaderCircle className="spin" size={16}/>:<ArrowDownToLine size={16}/>} Queue {parsed.length || ""} download{parsed.length===1?"":"s"}</button></div>
      {message && <div className="notice"><CircleAlert size={15}/>{message}</div>}
      <div className="source-note">YouTube uploads: import your own videos via Google Takeout or YouTube Studio. This tool accepts direct media URLs and does not bypass platform download controls.</div>
    </section>
    <section className="stats">
      <div className="stat panel"><span>IN QUEUE</span><strong>{active}</strong><small><Clock3 size={13}/> Active transfers</small></div>
      <div className="stat panel"><span>COMPLETED</span><strong>{completed}</strong><small><CheckCircle2 size={13}/> Successfully saved</small></div>
      <div className="stat panel"><span>FAILED</span><strong>{failed}</strong><small><CircleAlert size={13}/> Need attention</small></div>
    </section>
    <section className="queue panel"><div className="section-title"><div><span className="step">02</span><h2>Transfer queue</h2></div><button className="text-button" onClick={refresh}><RefreshCw size={14}/> Refresh</button></div>
      {!jobs.length ? <div className="empty"><div className="empty-icon"><Link2 size={22}/></div><strong>Nothing in the queue yet</strong><span>Paste your first batch of URLs above.</span></div> : <div className="job-list">{jobs.map(job=><article className="job" key={job.id}><div className="file-icon"><FileVideo2 size={18}/></div><div className="job-info"><strong>{job.result?.filename || job.id.slice(0,8)}</strong><small>{job.result ? fmt(job.result.bytes) + " · SHA-256 " + job.result.sha256.slice(0,12) : job.error || "Transfer queued"}</small></div><span className={"status "+job.status}>{job.status}</span></article>)}</div>}
    </section>
    <footer><span>FRAMETHEIVERY · SELF-HOSTED MEDIA TOOL</span><span>Files stay on your server.</span></footer>
    {showToken && <div className="modal-backdrop"><div className="modal panel"><div className="eyebrow">INSTANCE AUTHENTICATION</div><h2>Connect to your server</h2><p>Enter the API token configured in your server's environment.</p><input value={token} onChange={e=>setToken(e.target.value)} placeholder="API token" type="password"/><button className="primary full" onClick={saveToken} disabled={!token}>Connect instance</button></div></div>}
  </main>;
}
