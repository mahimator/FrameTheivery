import { useEffect, useMemo, useState } from "react";
import { ArrowDownToLine, CheckCircle2, CircleAlert, Clock3, FileArchive, FileVideo2, Link2, LoaderCircle, RefreshCw, ShieldCheck, RotateCcw, Server, Settings2 } from "lucide-react";

const DEFAULT_API = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://localhost:8000" : "");
type Job = {
  id: string; batch_id?: string; url?: string; source?: string; status: string; progress?: number | null;
  downloaded_bytes?: number; total_bytes?: number | null; phase?: string;
  result?: { filename: string; bytes: number; sha256: string; path: string } | null; error?: string | null
};
export default function App() {
  const [urls, setUrls] = useState("");
  const [apiBase, setApiBase] = useState(localStorage.getItem("ft_api_base") || DEFAULT_API);
  const [apiDraft, setApiDraft] = useState(localStorage.getItem("ft_api_base") || DEFAULT_API);
  const [token, setToken] = useState(localStorage.getItem("ft_token") || "");
  const [tokenDraft, setTokenDraft] = useState(localStorage.getItem("ft_token") || "");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [showConnection, setShowConnection] = useState(!localStorage.getItem("ft_api_base") || !localStorage.getItem("ft_token"));
  const parsed = useMemo(() => [...new Set(urls.split(/\s+/).map(x => x.trim()).filter(Boolean))], [urls]);
  const completed = jobs.filter(j => j.status === "finished").length;
  const failed = jobs.filter(j => j.status === "failed").length;
  const active = jobs.filter(j => ["queued","started","deferred"].includes(j.status)).length;
  const batches = useMemo(() => {
    const grouped = new Map<string, Job[]>();
    jobs.forEach(job => { if (job.batch_id) grouped.set(job.batch_id, [...(grouped.get(job.batch_id) || []), job]); });
    return grouped;
  }, [jobs]);

  const base = apiBase.trim().replace(/\/+$/, "");
  async function request(path: string, init: RequestInit = {}) {
    if (!base) throw new Error("Set your backend API URL in connection settings first.");
    const response = await fetch(base + path, { ...init, headers: { "Content-Type": "application/json", Authorization: "Bearer " + token, ...(init.headers || {}) } });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail?.message || body.detail || body.error || response.statusText);
    return body;
  }
  async function refresh() {
    if (!token || !base) return;
    try { const data = await request("/api/v1/jobs"); setJobs(data.jobs || []); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Unable to refresh queue"); }
  }
  useEffect(() => {
    if (!token || !base) return;
    refresh();
    const id = window.setInterval(refresh, 3000);
    return () => window.clearInterval(id);
  }, [token, base]);
  async function submit() {
    if (!token || !base) { setShowConnection(true); return; }
    if (!parsed.length) return;
    setBusy(true); setMessage("");
    try {
      const data = await request("/api/v1/batches", { method: "POST", body: JSON.stringify({ urls: parsed }) });
      setMessage(`Queued ${data.accepted.length} URLs. ${data.rejected.length} rejected.`);
      setUrls(""); await refresh();
    } catch (e) { setMessage(e instanceof Error ? e.message : "Could not queue URLs"); }
    finally { setBusy(false); }
  }
  async function download(path: string, filename: string) {
    try {
      const response = await fetch(base + path, { headers: { Authorization: "Bearer " + token } });
      if (!response.ok) throw new Error((await response.text()) || "Download failed");
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(objectUrl);
    } catch (e) { setMessage(e instanceof Error ? e.message : "Download failed"); }
  }
  async function retry(jobId: string) {
    try { await request(`/api/v1/jobs/${jobId}/retry`, { method: "POST" }); setMessage("Retry queued."); await refresh(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Retry failed"); }
  }
  function saveConnection() {
    const clean = apiDraft.trim().replace(/\/+$/, "");
    if (!/^https?:\/\//i.test(clean)) { setMessage("Enter a complete API URL starting with https://."); return; }
    localStorage.setItem("ft_api_base", clean);
    localStorage.setItem("ft_token", tokenDraft);
    setApiBase(clean); setToken(tokenDraft); setShowConnection(false); setJobs([]); setMessage("Connection settings saved."); 
  }
  const fmt = (n: number) => n < 1024 ? n + " B" : n < 1048576 ? (n/1024).toFixed(1)+" KB" : n < 1073741824 ? (n/1048576).toFixed(1)+" MB" : (n/1073741824).toFixed(2)+" GB";
  return <main className="shell">
    <header><a className="brand" href="#"><span className="brandmark"><FileVideo2 size={20}/></span><span>frame<span className="accent">theivery</span></span></a><div className="header-right"><span className="secure"><ShieldCheck size={14}/> PRIVATE INSTANCE</span><button className="icon-button" onClick={()=>setShowConnection(true)} title="Connection settings"><Settings2 size={17}/></button><button className="icon-button" onClick={refresh} title="Refresh queue"><RefreshCw size={17}/></button></div></header>
    <section className="hero"><div className="eyebrow">PERSONAL MEDIA RECOVERY</div><h1>Bring your memories<br/><span className="muted">back together.</span></h1><p>Queue public video links in bulk. FrameTheivery retrieves the available media and keeps every transfer organised.</p></section>
    <section className="composer panel">
      <div className="section-title"><div><span className="step">01</span><h2>Video URLs</h2></div><span className="count">{parsed.length} URL{parsed.length===1?"":"s"} detected</span></div>
      <textarea value={urls} onChange={e=>setUrls(e.target.value)} placeholder={"Paste one YouTube video URL per line…\nhttps://www.youtube.com/watch?v=…\nhttps://youtu.be/…\n\nDirect media URLs work too."} spellCheck={false}/>
      <div className="composer-footer"><span>One URL per line · duplicates removed automatically · up to 200 per batch</span><button className="primary" disabled={!parsed.length || busy} onClick={submit}>{busy?<LoaderCircle className="spin" size={16}/>:<ArrowDownToLine size={16}/>} Queue {parsed.length || ""} download{parsed.length===1?"":"s"}</button></div>
      {message && <div className="notice"><CircleAlert size={15}/>{message}</div>}
      <div className="source-note">YouTube links must be publicly playable. Only submit videos you own or are authorised to download. Retrieved streams may differ from your original upload files.</div>
    </section>
    <section className="stats">
      <div className="stat panel"><span>IN QUEUE</span><strong>{active}</strong><small><Clock3 size={13}/> Active transfers</small></div>
      <div className="stat panel"><span>COMPLETED</span><strong>{completed}</strong><small><CheckCircle2 size={13}/> Successfully saved</small></div>
      <div className="stat panel"><span>FAILED</span><strong>{failed}</strong><small><CircleAlert size={13}/> Need attention</small></div>
    </section>
    <section className="queue panel"><div className="section-title"><div><span className="step">02</span><h2>Transfer queue</h2></div><button className="text-button" onClick={refresh}><RefreshCw size={14}/> Refresh</button></div>
      {!jobs.length ? <div className="empty"><div className="empty-icon"><Link2 size={22}/></div><strong>{base && token ? "Nothing in the queue yet" : "Connect your download server"}</strong><span>{base && token ? "Paste your first batch of URLs above." : "Deploy the backend separately, then add its API URL in connection settings."}</span></div> : <div className="job-list">{jobs.map(job=><article className="job" key={job.id}><div className="file-icon"><FileVideo2 size={18}/></div><div className="job-info"><strong>{job.result?.filename || job.url || job.id.slice(0,8)}</strong><small>{job.result ? fmt(job.result.bytes) + " · SHA-256 " + job.result.sha256.slice(0,12) : job.error || (job.phase === "extracting" ? "Reading YouTube video…" : job.phase === "processing" ? "Merging audio and video…" : job.phase === "connecting" ? "Connecting…" : job.downloaded_bytes ? fmt(job.downloaded_bytes) + (job.total_bytes ? " / " + fmt(job.total_bytes) : " downloaded") : "Waiting for worker")}</small>{job.status==="started" && <div className="progress"><span style={{width: (job.progress ?? 0) + "%"}}/></div>}</div><div className="job-actions"><span className={"status "+job.status}>{job.progress != null && job.status==="started" ? job.progress+"%" : job.status}</span>{job.status==="finished" && <button className="mini-button" title="Download file" onClick={()=>download(`/api/v1/jobs/${job.id}/file`, job.result?.filename || "video") }><ArrowDownToLine size={15}/></button>}{job.status==="failed" && <button className="mini-button" title="Retry" onClick={()=>retry(job.id)}><RotateCcw size={15}/></button>}</div></article>)}</div>}
    </section>
    {batches.size > 0 && <section className="queue panel"><div className="section-title"><div><span className="step">03</span><h2>Batch exports</h2></div></div>{[...batches.entries()].map(([id,items])=><div className="batch-row" key={id}><div><strong>{id.slice(0,8)}</strong><small>{items.length} files · {items.filter(j=>j.status==="finished").length} complete</small></div><button className="text-button" disabled={items.some(j=>j.status!=="finished")} onClick={()=>download(`/api/v1/batches/${id}/archive`, `frametheivery-${id.slice(0,8)}.zip`)}><FileArchive size={15}/> Download ZIP</button></div>)}</section>}
    <footer><span>FRAMETHEIVERY · SELF-HOSTED MEDIA TOOL</span><span>Files stay on your server.</span></footer>
    {showConnection && <div className="modal-backdrop"><div className="modal panel"><div className="eyebrow">SERVER CONNECTION</div><h2>Connect your instance</h2><p>Netlify hosts this interface. Your API, queue and video workers run on your own server.</p><label>Backend API URL</label><input value={apiDraft} onChange={e=>setApiDraft(e.target.value)} placeholder="https://api.your-domain.com" type="url"/><label>API token</label><input value={tokenDraft} onChange={e=>setTokenDraft(e.target.value)} placeholder="Your server API token" type="password"/><button className="primary full" onClick={saveConnection} disabled={!apiDraft.trim() || !tokenDraft.trim()}><Server size={16}/> Save connection</button></div></div>}
  </main>;
}
