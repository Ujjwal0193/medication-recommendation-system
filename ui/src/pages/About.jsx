export default function About() {
  return (
    <div className="prose">
      <h1>About MediGuard</h1>

      <p className="lead sm">
        MediGuard is a clinical decision-support system built for an M.Tech project at
        NIT Rourkela. It is deliberately <strong>safe by construction</strong>: the
        machine understands and suggests, but deterministic rules — and ultimately a
        qualified doctor — decide.
      </p>

      <h2>What it does</h2>
      <ol>
        <li>Takes a <strong>medicine knowledge base</strong> — purpose, salt, dose, timing, route, side effects, "good with" / "harmful with".</li>
        <li>Takes a <strong>patient profile</strong> — free text ("32, pregnant, cramps and fever, low BP, high sugar") <em>and</em> structured fields.</li>
        <li>Produces a <strong>ranked, explained recommendation</strong> with drug–drug and drug–condition safety checks, dosing and timing, and a mandatory consult-a-doctor note.</li>
      </ol>

      <h2>Hard boundaries</h2>
      <ul className="bounds">
        <li>❌ It does <strong>not</strong> diagnose.</li>
        <li>❌ It does <strong>not</strong> replace a prescriber — it flags issues and suggests options for discussion.</li>
        <li>✅ Every output ends with a disclaimer and a doctor-review directive.</li>
        <li>✅ It is a research prototype, <strong>not</strong> a certified medical device.</li>
      </ul>

      <h2>Why this architecture</h2>
      <div className="compare">
        <div><span className="x">✗</span> A pure LLM hallucinates dosages and contraindications — unsafe.</div>
        <div><span className="x">✗</span> A pure black-box model is accurate but unexplainable, and needs restricted hospital data.</div>
        <div><span className="x">✗</span> Pure rules are safe but can't read free text.</div>
        <div><span className="ok">✓</span> The hybrid: NLP reads the patient, rules + knowledge graph guarantee safety, a model adds novelty as warnings, and a constrained explainer makes it all transparent.</div>
      </div>

      <h2>The safety guarantee</h2>
      <p>
        The Safety Authority is the only component that decides safety. Its verdict can
        <strong> block</strong> or <strong>downgrade</strong> any candidate. The machine-learning
        interaction model contributes <strong>warnings only</strong> — a confidence gate
        makes it structurally impossible for a model prediction to turn a blocked drug
        into an actionable recommendation. This invariant is enforced in three
        independent places in the code and verified against an adversarial "always
        certain" model in the test suite.
      </p>

      <h2>Scope &amp; honest limitations</h2>
      <ul>
        <li>Small curated set of ~40 common outpatient drugs (diabetes, hypertension, pain/fever, common infections). Extensibility to thousands is future work.</li>
        <li>No real clinical validation; evaluated on synthetic patients only.</li>
        <li>Interaction and contraindication facts are compiled from public references for a prototype and must be validated against authoritative databases (DDInter, DailyMed) before any real use.</li>
        <li>Framed as an <em>educational / decision-support</em> tool that lets a human independently review the basis of every recommendation.</li>
      </ul>
    </div>
  );
}
