import { useEffect, useState } from "react";

const STATUS_META = {
  allow: { label: "Suitable", cls: "allow", icon: "✅" },
  warn: { label: "Use with caution", cls: "warn", icon: "⚠️" },
  downgrade: { label: "Caution — not preferred", cls: "downgrade", icon: "⚠️" },
  block: { label: "Not recommended", cls: "block", icon: "❌" },
};

const EXAMPLES = [
  "32, pregnant, severe cramps and fever, history of low BP and high sugar, on warfarin",
  "58 year old man with high blood pressure and type 2 diabetes, on metformin",
  "62 year old with atrial fibrillation and GERD, on clopidogrel and aspirin",
  "28 year old pregnant woman with a urinary tract infection, allergic to penicillin",
  "70 yo with heart failure and chronic kidney disease, on lisinopril",
];

const API = "/api";

export default function Demo() {
  const [mode, setMode] = useState("text");
  const [text, setText] = useState(EXAMPLES[0]);
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  // structured-input state
  const [conds, setConds] = useState([]);
  const [drugs, setDrugs] = useState([]);
  const [form, setForm] = useState({
    age: "", pregnant: false, conditions: [], current_meds: [], allergies: [], renal: "",
  });

  useEffect(() => {
    fetch(`${API}/conditions`).then((r) => r.json()).then((d) => setConds(d.conditions || [])).catch(() => {});
    fetch(`${API}/drugs`).then((r) => r.json()).then((d) => setDrugs(d.drugs || [])).catch(() => {});
  }, []);

  function toggle(field, value) {
    setForm((f) => {
      const has = f[field].includes(value);
      return { ...f, [field]: has ? f[field].filter((x) => x !== value) : [...f[field], value] };
    });
  }

  async function submit() {
    setError("");
    if (!consent) { setError("Please acknowledge the consent note before continuing."); return; }
    setLoading(true); setData(null);
    const body = mode === "text"
      ? { text, consent }
      : {
          consent,
          age: form.age ? Number(form.age) : null,
          pregnant: form.pregnant || null,
          conditions: form.conditions,
          current_meds: form.current_meds,
          allergies: form.allergies,
          renal: form.renal || null,
        };
    try {
      const res = await fetch(`${API}/recommend`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(`Could not reach the MediGuard API on :8000. Start it with "uvicorn mediguard.api.app:app --port 8000". (${e.message})`);
    } finally { setLoading(false); }
  }

  return (
    <div className="demo">
      <h1>Live demo</h1>
      <p className="lead sm">
        Describe a patient. MediGuard extracts their profile, generates candidate
        medications, and shows the safety-checked, explained result. It never
        prescribes — it flags and explains.
      </p>

      <div className="tabs">
        <button className={mode === "text" ? "on" : ""} onClick={() => setMode("text")}>Free text</button>
        <button className={mode === "form" ? "on" : ""} onClick={() => setMode("form")}>Structured form</button>
      </div>

      <section className="card">
        {mode === "text" ? (
          <>
            <label className="lbl">Patient report</label>
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} />
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button key={ex} className="chip" onClick={() => setText(ex)}>{ex.slice(0, 40)}…</button>
              ))}
            </div>
          </>
        ) : (
          <div className="form">
            <div className="frow">
              <label>Age<input type="number" value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} /></label>
              <label className="chk"><input type="checkbox" checked={form.pregnant} onChange={(e) => setForm({ ...form, pregnant: e.target.checked })} /> Pregnant</label>
              <label className="chk"><input type="checkbox" checked={form.renal === "impaired"} onChange={(e) => setForm({ ...form, renal: e.target.checked ? "impaired" : "" })} /> Kidney impairment</label>
            </div>
            <label className="lbl">Conditions</label>
            <div className="pickers">
              {conds.map((c) => (
                <button key={c.code} className={`chip ${form.conditions.includes(c.code) ? "sel" : ""}`} onClick={() => toggle("conditions", c.code)}>{c.display}</button>
              ))}
            </div>
            <label className="lbl">Current medications</label>
            <div className="pickers scroll">
              {drugs.map((d) => (
                <button key={d} className={`chip ${form.current_meds.includes(d) ? "sel" : ""}`} onClick={() => toggle("current_meds", d)}>{d}</button>
              ))}
            </div>
            <label className="lbl">Allergies</label>
            <div className="pickers">
              <button className={`chip ${form.allergies.includes("penicillin allergy") ? "sel" : ""}`} onClick={() => toggle("allergies", "penicillin allergy")}>Penicillin allergy</button>
            </div>
          </div>
        )}

        <label className="consent">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          I understand this is advisory only and I will consult a doctor before acting.
        </label>
        <button className="btn primary" onClick={submit} disabled={loading}>
          {loading ? "Analyzing…" : "Get recommendations"}
        </button>
        {error && <p className="err">{error}</p>}
      </section>

      {data && <Results data={data} />}
    </div>
  );
}

function Results({ data }) {
  const p = data.profile;
  return (
    <section className="results">
      <div className="profile card">
        <h3>Understood patient profile</h3>
        <div className="pgrid">
          <Field k="Age" v={p.age} />
          <Field k="Pregnant" v={p.pregnant === null ? "—" : String(p.pregnant)} />
          <Field k="Conditions" v={(p.conditions || []).map((c) => c.display || c.code).join(", ") || "—"} />
          <Field k="Current meds" v={(p.current_meds || []).map((m) => m.name).join(", ") || "—"} />
          <Field k="Allergies" v={(p.allergies || []).map((a) => a.display || a.code).join(", ") || "—"} />
        </div>
      </div>

      {data.results.length === 0 && <div className="card">No recognized conditions to act on. Try an example.</div>}

      {data.results.map((cond) => (
        <div key={cond.condition_code} className="card">
          <h3>{cond.condition_display} <span className="code">({cond.condition_code})</span></h3>
          {cond.abstain && <div className="abstain">🧑‍⚕️ Defer to clinician: {cond.abstain_reason}</div>}
          <div className="recs">
            {cond.recommendations.map((rec, i) => {
              const meta = STATUS_META[rec.status] || STATUS_META.warn;
              return (
                <div key={i} className={`rec ${meta.cls}`}>
                  <div className="rec-head">
                    <span className="drug">{meta.icon} {rec.drug}</span>
                    <span className={`badge ${meta.cls}`}>{meta.label}</span>
                    {rec.abstain && <span className="badge muted">deferred</span>}
                    <span className="conf">confidence {(rec.confidence * 100).toFixed(0)}%</span>
                  </div>
                  {rec.reasons.length > 0 && (
                    <ul className="reasons">
                      {rec.reasons.map((r, j) => <li key={j} className={`sev-${r.severity}`}>{r.message}</li>)}
                    </ul>
                  )}
                  <details><summary>Explanation</summary><pre className="rationale">{rec.rationale}</pre></details>
                </div>
              );
            })}
          </div>
        </div>
      ))}
      <p className="disclaimer">{data.disclaimer}</p>
    </section>
  );
}

function Field({ k, v }) {
  return <div className="field"><span className="fk">{k}</span><span className="fv">{v === null || v === undefined || v === "" ? "—" : v}</span></div>;
}
