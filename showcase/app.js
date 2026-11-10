/* Dhago showcase: renders four invented applications from examples.json and re-checks
   their audit hashes in the browser. No framework, no build step. */
"use strict";

const NUM = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const npr = (v) => `NPR ${NUM.format(Math.round(Number(v) || 0))}`;
const pct = (v, d = 1) => `${(Number(v) * 100).toFixed(d)}%`;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const icon = (name) => `<svg aria-hidden="true" focusable="false"><use href="#i-${name}"></use></svg>`;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const PURPOSE = {
  home_repair: "Home repair", small_trade: "Stock for a small trade", vehicle_purchase: "Buying a vehicle",
  agricultural_input: "Seeds, feed and other farm inputs", livestock_purchase: "Buying livestock",
  agri_land_development: "Farm land improvement", irrigation_equipment: "Irrigation equipment",
  education: "Education", emergency_medical: "Medical emergency", microenterprise_startup: "Starting a small business",
};
const SOURCE = {
  remittance_agent: "Remittances through a transfer company",
  wallet_topup: "Cash deposited into the wallet",
  other_wallet_inflows: "Payments received in the wallet",
  COOPERATIVE_SALES: "Sales through a cooperative",
};
const RULE_NAME = {
  BLACKLIST: "Blacklist screen", AML_SCREEN: "Anti-money-laundering screen", KYC_TIER_LIMIT: "KYC tier ceiling",
  COLLATERAL_REQUIRED: "Collateral for large loans", AGRI_LOAN_TO_INCOME: "Farm loan size",
  EXISTING_LOANS: "Existing loans", DSTI_CAP: "Debt-service cap", INCOME_MISMATCH: "Declared versus observed income",
};
const PROVENANCE = {
  hackathon_field: "Source: a screening result supplied with the hackathon data",
  hackathon_rule: "Source: a simulated rule from the hackathon's data manual",
  regulator_reported: "Source: modelled on a Nepal Rastra Bank cap, as reported in the press",
  design: "Source: our own design choice",
};
const STAGE_NAME = { income_node: "Income", compliance_node: "Rules", scoring_node: "Risk", decision_node: "Recommendation" };

let DATA = null;
let current = null;
const audit = { lines: [], keptHead: "", edited: new Set(), mode: "original" };

/* ---------------------------------------------------------------- boot */
async function boot() {
  try {
    const res = await fetch("examples.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    DATA = await res.json();
  } catch (err) {
    document.getElementById("choices").innerHTML =
      `<p class="loading">The examples did not load (${esc(err.message)}). Serve this folder over HTTP, for example with <code>python -m http.server</code>; browsers block data files opened straight from disk.</p>`;
    return;
  }
  renderPicker();
  const fromHash = DATA.examples.find((x) => x.key === location.hash.slice(1));
  select((fromHash || DATA.examples[0]).key, { animate: false });
  window.addEventListener("hashchange", () => {
    const hit = DATA.examples.find((x) => x.key === location.hash.slice(1));
    if (hit && hit.key !== current?.key) select(hit.key, { animate: true });
  });
  document.getElementById("t-income").addEventListener("click", () => tamper("income"));
  document.getElementById("t-forge").addEventListener("click", () => tamper("forge"));
  document.getElementById("t-delete").addEventListener("click", () => tamper("delete"));
  document.getElementById("t-restore").addEventListener("click", () => tamper("restore"));
}

function outcomeLine(e) {
  const d = e.decision.decision;
  if (d === "approve") return "Approved";
  if (d === "conditional") return "Approved for a smaller amount";
  if (d === "decline") return "Declined by a veto rule";
  const fired = e.compliance.traces.filter((t) => t.triggered && t.action === "refer").length;
  if (fired) return `${fired === 1 ? "A rule sends" : "Two rules send"} it to an officer`;
  if (e.income.confidence < DATA.decision_rules.min_income_confidence) return "Thin file, sent to an officer";
  return "Sent to an officer";
}

function renderPicker() {
  const box = document.getElementById("choices");
  box.innerHTML = `<legend class="visually-hidden">Choose an applicant</legend>` + DATA.examples.map((e) => `
    <label class="choice">
      <input type="radio" name="applicant" id="pick-${esc(e.key)}" value="${esc(e.key)}">
      <span><strong>${esc(e.label)}</strong><em>${esc(outcomeLine(e))}</em></span>
    </label>`).join("");
  box.addEventListener("change", (ev) => {
    if (ev.target.name === "applicant") select(ev.target.value, { animate: true });
  });
}

function select(key, { animate }) {
  const e = DATA.examples.find((x) => x.key === key);
  if (!e) return;
  current = e;
  const radio = document.getElementById(`pick-${key}`);
  if (radio) radio.checked = true;
  try { history.replaceState(null, "", `#${key}`); } catch (_) { /* some frames forbid it */ }

  document.getElementById("body-application").innerHTML = renderApplication(e);
  document.getElementById("body-income").innerHTML = renderIncome(e);
  document.getElementById("body-rules").innerHTML = renderRules(e);
  document.getElementById("body-risk").innerHTML = renderRisk(e);
  document.getElementById("body-recommendation").innerHTML = renderRecommendation(e);
  document.querySelector('[data-stage="risk"]').classList.toggle("skipped", !e.score);
  document.getElementById("announce").textContent =
    `${e.label}. Recommendation: ${decisionWord(e.decision.decision)}.`;

  const flow = document.getElementById("flow");
  flow.classList.remove("drawing");
  if (animate && !reduceMotion.matches) {
    void flow.offsetWidth; // restart the animation
    flow.classList.add("drawing");
  }
  loadAudit(e);
}

/* ---------------------------------------------------------------- stages */
function monthsText(range) {
  if (!range) return "";
  const [a, b] = range.map((m) => m.split("-").map(Number));
  const from = MONTHS[a[1] - 1], to = MONTHS[b[1] - 1];
  return a[0] === b[0] ? `${from} to ${to} ${b[0]}` : `${from} ${a[0]} to ${to} ${b[0]}`;
}

function listText(parts) {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

function plural(n, one, many) { return `${NUM.format(n)} ${n === 1 ? one : many}`; }

function renderApplication(e) {
  const a = e.application;
  const collateral = a.collateral_type === "land" ? `Land worth ${npr(a.collateral_value_nrs)}` : "None";
  return `
    <p class="story">${esc(e.story)}</p>
    <dl class="facts">
      <div><dt>Says they earn</dt><dd>${npr(a.declared_monthly_income)} a month</dd></div>
      <div><dt>Asks for</dt><dd>${npr(a.requested_amount_nrs)} over ${a.requested_tenure_months} months</dd></div>
      <div><dt>For</dt><dd>${esc(PURPOSE[a.loan_purpose] || a.loan_purpose)}</dd></div>
      <div><dt>Collateral</dt><dd>${esc(collateral)}</dd></div>
      <div><dt>Existing loans</dt><dd>${a.existing_loan_count ? NUM.format(a.existing_loan_count) : "None"}</dd></div>
      <div><dt>Credit bureau record</dt><dd>${a.has_bureau_score ? "Yes" : "None"}</dd></div>
    </dl>`;
}

function renderIncome(e) {
  const inc = e.income, r = e.records, rules = DATA.decision_rules;
  const parts = [];
  if (r.remittance) parts.push(plural(r.remittance, "remittance", "remittances"));
  if (r.wallet) parts.push(plural(r.wallet, "wallet transaction", "wallet transactions"));
  if (r.utility) parts.push(plural(r.utility, "utility bill", "utility bills"));
  const coop = r.coop_sales ? `, plus ${plural(r.coop_sales, "year", "years")} of cooperative sales` : "";

  const declared = e.application.declared_monthly_income, observed = inc.observed_monthly || 0;
  const top = Math.max(declared, observed, 1);
  const sources = inc.sources.map((s) => {
    const how = s.source === "COOPERATIVE_SALES" ? "average yearly sales divided by 12" : `over ${plural(s.months, "month", "months")}`;
    // the pipeline truncates its income estimate to whole rupees, so show sources the same way
    return `<li><span>${esc(SOURCE[s.source] || s.source)}</span><span><b>${npr(Math.floor(s.monthly))}</b> a month, ${esc(how)}</span></li>`;
  }).join("");

  const onTime = Math.round((inc.on_time_rate ?? 0) * r.utility);
  const adjust = inc.on_time_rate >= 0.8 ? "adds 0.07" : inc.on_time_rate < 0.5 ? "subtracts 0.10" : "leaves it unchanged";
  const thin = rules.min_income_confidence;
  const band = e.compliance.traces.find((t) => t.rule_id === "INCOME_MISMATCH");
  const high = band && band.threshold ? band.threshold.high : 3;
  const ratioLine = inc.imr == null
    ? "Too little observed income to compare with the declared figure."
    : `Declared income is ${inc.imr.toFixed(2)} times what the records show. The rules allow 0.3 to ${high}${high === 5 ? ", because most of this household's income arrives as remittances" : ""}.`;

  return `
    <p>Dhago read ${listText(parts)} from ${esc(monthsText(r.months))}${coop}.</p>
    <div class="compare" role="img" aria-label="Declared ${npr(declared)} a month, observed ${npr(observed)} a month">
      <div class="compare-row"><span class="label">Declared</span><div class="track"><div class="bar claim" style="--w:${(declared / top * 100).toFixed(1)}%"></div></div><span class="value">${npr(declared)}</span></div>
      <div class="compare-row"><span class="label">Observed</span><div class="track"><div class="bar fact" style="--w:${(observed / top * 100).toFixed(1)}%"></div></div><span class="value">${npr(observed)}</span></div>
    </div>
    <p>${ratioLine}</p>
    <ul class="sources">${sources}</ul>
    <div class="meter">
      <div class="meter-top"><span>Strength of the income evidence</span><span class="figure">${inc.confidence.toFixed(2)}</span></div>
      <div class="meter-track" role="img" aria-label="Confidence ${inc.confidence.toFixed(2)} on a scale from 0 to 1; files below ${thin.toFixed(2)} go to an officer">
        <div class="meter-fill" style="--w:${(inc.confidence * 100).toFixed(1)}%"></div>
        <div class="meter-tick" style="--at:${(thin * 100).toFixed(1)}%"></div>
      </div>
      <div class="meter-scale" aria-hidden="true"><span style="left:0">0</span><span style="left:${(thin * 100).toFixed(1)}%">${thin.toFixed(2)} thin file</span><span style="left:100%">1</span></div>
      <p class="small">It combines how reliable each source is with how many months of history there are. Paying ${NUM.format(onTime)} of ${plural(r.utility, "utility bill", "utility bills")} on time ${adjust}. Below ${thin.toFixed(2)} a file is too thin to decide on, so it goes to an officer instead of being declined.</p>
    </div>`;
}

function ruleStatus(t) {
  if (t.note === "not screened") return ["refer", "Not screened, refers"];
  if (!t.applicable) return ["na", "Not applicable"];
  if (!t.triggered) return ["pass", "Passes"];
  return { veto: ["veto", "Vetoes"], refer: ["refer", "Refers"], flag: ["flag", "Flags"] }[t.action] || ["refer", "Refers"];
}

function ruleDetail(t) {
  const o = t.observed, th = t.threshold;
  switch (t.rule_id) {
    case "BLACKLIST":
      if (t.note === "not screened") return "No screening result came with the application, so it cannot pass.";
      return o ? "The screening result supplied with the application lists this applicant." : "The screening result supplied with the application is clear.";
    case "AML_SCREEN":
      if (t.note === "not screened") return "No screening result came with the application, so it cannot pass.";
      return o ? "Screening returned a possible match." : "Screening returned no match.";
    case "KYC_TIER_LIMIT":
      return th == null ? `${npr(o.requested)} requested. The ${o.tier} KYC tier has no ceiling.`
        : `${npr(o.requested)} requested. The ${o.tier} KYC tier allows up to ${npr(th)}.`;
    case "COLLATERAL_REQUIRED":
      return o.requested > th ? `${npr(o.requested)} requested against ${npr(o.collateral)} of collateral. Collateral is required above ${npr(th)}.`
        : `${npr(o.requested)} requested. Collateral is required only above ${npr(th)}.`;
    case "AGRI_LOAN_TO_INCOME":
      return t.applicable ? `The loan is ${Number(o).toFixed(1)} times monthly observed income. The limit is ${th} times.`
        : "Applies only to farm loans.";
    case "EXISTING_LOANS":
      return `${o ? plural(o, "existing loan", "existing loans") : "No existing loans"}. The officer is alerted at ${th} or more.`;
    case "DSTI_CAP":
      return o == null ? "No observed income to compare the instalment with."
        : `The new instalment would take ${pct(o)} of observed monthly income. The cap is ${pct(th, 0)}.`;
    case "INCOME_MISMATCH":
      return o == null ? "Not checked: too little observed income or no declared income."
        : `Declared income is ${Number(o).toFixed(2)} times observed. The allowed band is ${th.low} to ${th.high}.`;
    default:
      return "";
  }
}

function renderRules(e) {
  const traces = e.compliance.traces;
  const fired = traces.filter((t) => t.triggered || t.note === "not screened");
  let summary;
  if (e.compliance.status === "veto") summary = `The ${RULE_NAME[fired.find((t) => t.action === "veto").rule_id].toLowerCase()} vetoes the application.`;
  else if (!fired.length) summary = `All ${traces.length} rules pass.`;
  else summary = `${fired.length === 1 ? "One rule sends" : `${fired.length === 2 ? "Two" : fired.length} rules send`} the case to an officer: ${listText(fired.map((t) => RULE_NAME[t.rule_id].toLowerCase()))}.`;
  const rows = traces.map((t) => {
    const [cls, word] = ruleStatus(t);
    return `<li class="rule${cls === "na" ? " is-na" : ""}">
      <span class="st-${cls}">${icon(cls)}</span>
      <span class="rule-name">${esc(RULE_NAME[t.rule_id] || t.rule_id)}</span>
      <span class="rule-status st-${cls}">${esc(word)}</span>
      <span class="rule-detail">${esc(ruleDetail(t))}</span>
      <span class="rule-source">${esc(PROVENANCE[t.provenance] || "")}</span>
    </li>`;
  }).join("");
  return `<p class="verdict-line">${esc(summary)}</p><ol class="rules">${rows}</ol>
    <p class="small">The rules live in one YAML file. Changing it changes the policy version that is written into the audit log with every decision.</p>`;
}

function driverValue(d) {
  const v = Number(d.value);
  switch (d.feature) {
    case "remittance_monthly_avg": case "esewa_net_monthly": case "cooperative_monthly_sales":
    case "monthly_income_est": return `${npr(v)} a month`;
    case "util_arrears_total_nrs": case "utility_avg_bill_nrs": case "requested_amount_nrs":
    case "collateral_value_nrs": return npr(v);
    case "collateral_coverage": return `${v.toFixed(1)} times the loan`;
    case "loan_to_annual_income": return `${v.toFixed(2)} times yearly income`;
    case "instalment_to_income": case "overall_on_time_rate": return pct(v, 0);
    case "existing_loan_count": case "income_signal_count": case "credit_bureau_score": return NUM.format(v);
    default: return Math.abs(v) >= 100 ? NUM.format(v) : v.toFixed(2);
  }
}

function renderRisk(e) {
  if (!e.score) {
    return `<p class="skip-note">Not scored. A veto rule fired, so the case skips the model and goes straight to the recommendation.</p>`;
  }
  const s = e.score, grades = DATA.model.grades;
  const cap = 0.08; // the scale shown runs to 8%; grade E covers everything above 6%
  const edges = [0, ...grades.map((g) => Math.min(g.pd_below, cap))];
  const widths = grades.map((g, i) => edges[i + 1] - edges[i]);
  const cols = widths.map((w) => `${(w / cap * 100).toFixed(2)}fr`).join(" ");
  const cells = grades.map((g) => `<span class="${g.grade === s.risk_grade ? "on" : ""}">${g.grade}</span>`).join("");
  const ticks = grades.slice(0, -1).map((g) => `<span style="left:${(g.pd_below / cap * 100).toFixed(2)}%">${(g.pd_below * 100).toFixed(1)}%</span>`).join("");
  const at = Math.min(s.pd, cap) / cap * 100;
  const maxShap = Math.max(...s.drivers.map((d) => Math.abs(d.shap)), 0.01);
  const drivers = s.drivers.map((d) => {
    const w = (Math.abs(d.shap) / maxShap * 100).toFixed(1);
    const bar = `<div class="driver-bar ${d.shap < 0 ? "lowers" : "raises"}" style="--w:${w}%"></div>`;
    return `<div class="driver">
      <div class="driver-label"><b>${esc(d.label)}</b><span>${esc(driverValue(d))}, ${esc(d.direction)}</span></div>
      <div class="driver-track" aria-hidden="true"><div>${d.shap < 0 ? bar : ""}</div><div>${d.shap >= 0 ? bar : ""}</div></div>
    </div>`;
  }).join("");
  return `
    <div class="pd"><span class="figure">${pct(s.pd)}</span><span>estimated chance of default. Grade ${esc(s.risk_grade)}, score ${NUM.format(s.credit_score)} on a 300 to 850 scale.</span></div>
    <div class="grades">
      <div class="grade-track" style="--cols:${cols}" role="img" aria-label="Grade ${esc(s.risk_grade)}: ${pct(s.pd)} sits in the ${esc(s.risk_grade)} band">${cells}<i class="grade-marker" style="--at:${at.toFixed(2)}%"></i></div>
      <div class="grade-scale" aria-hidden="true">${ticks}</div>
    </div>
    <div class="drivers">
      <p>The five inputs that moved this estimate most:</p>
      <div class="drivers-axis" aria-hidden="true"><span>lowers risk</span><span>raises risk</span></div>
      ${drivers}
    </div>
    <p class="small">A gradient-boosted model trained on the hackathon's synthetic loans. Seven inputs, such as collateral cover and on-time payments, are constrained so they can move risk in one direction only.</p>`;
}

function decisionWord(d) {
  return { approve: "approve", conditional: "approve a smaller amount", refer: "refer to a loan officer", decline: "decline" }[d] || d;
}

function renderRecommendation(e) {
  const d = e.decision, a = e.application;
  const badge = { approve: ["pass", "Approve"], conditional: ["pass", "Approve a smaller amount"], refer: ["refer", "Refer to a loan officer"], decline: ["veto", "Decline"] }[d.decision];
  const amount = d.approved_amount_nrs ? `<p>${npr(d.approved_amount_nrs)} over ${a.requested_tenure_months} months.</p>` : "";
  const reasons = (d.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("");
  let offer = "";
  const c = d.counter_offer;
  if (c) {
    const full = c.tenure_needed_for_full_amount
      ? `The full amount would fit over ${c.tenure_needed_for_full_amount} months.`
      : `The full amount does not fit even over ${DATA.decision_rules.counter_offer_max_tenure_months} months.`;
    offer = `<p class="offer">The officer also gets an affordable offer: up to ${npr(c.max_amount_at_requested_tenure)} over ${c.requested_tenure_months} months, an instalment of ${npr(c.affordable_monthly_instalment)}, which is half of observed income at an assumed 14% a year. ${full}</p>`;
  }
  const versions = d.model_version
    ? `Policy version ${esc(d.policy_version)} and model version ${esc(d.model_version)} are recorded with this recommendation.`
    : `Policy version ${esc(d.policy_version)} is recorded with this recommendation. The model did not run.`;
  return `
    <div class="decision">
      <span class="decision-badge d-${esc(d.decision)}">${icon(badge[0])}${esc(badge[1])}</span>
      ${amount}
    </div>
    <ul class="reasons">${reasons}</ul>
    ${offer}
    <p class="small">${versions} Dhago recommends and the officer decides. It declines only when a written veto rule fires.</p>`;
}

/* ---------------------------------------------------------------- audit log */
const HASH_KEY = '"hash":"';

function splitLine(line) {
  const i = line.indexOf(HASH_KEY);
  return { hash: line.slice(i + 8, i + 72), body: line.slice(0, i) + line.slice(i + 74), at: i };
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function verifyLines(lines) {
  let prev = "0".repeat(64);
  for (const line of lines) {
    const { hash, body } = splitLine(line);
    const entry = JSON.parse(line);
    if (entry.prev_hash !== prev || (await sha256(body)) !== hash) return { ok: false, bad: entry.seq, head: null };
    prev = hash;
  }
  return { ok: true, bad: null, head: prev };
}

function entrySummary(entry) {
  const p = entry.payload || {};
  switch (entry.agent) {
    case "income_node":
      return [`observed ${npr(p.income_agent_monthly_est)} a month`, `confidence ${Number(p.income_confidence).toFixed(2)}`];
    case "compliance_node":
      return [`status: ${p.compliance_status}`, `policy ${p.policy_version}`];
    case "scoring_node":
      return p.scorecard ? [`chance of default ${pct(p.scorecard.pd)}`, `grade ${p.scorecard.risk_grade}`] : ["not scored"];
    case "decision_node":
      return [`recommendation: ${p.final_decision}`];
    default:
      return [];
  }
}

function loadAudit(e) {
  audit.lines = e.audit_lines.slice();
  audit.keptHead = splitLine(audit.lines[audit.lines.length - 1]).hash;
  audit.edited = new Set();
  audit.mode = "original";
  refreshAudit();
}

async function refreshAudit() {
  const result = await verifyLines(audit.lines);
  const chain = document.getElementById("chain");
  let seenBad = false;
  chain.innerHTML = audit.lines.map((line) => {
    const entry = JSON.parse(line);
    const { hash } = splitLine(line);
    const bad = !result.ok && entry.seq === result.bad;
    const after = seenBad;
    if (bad) seenBad = true;
    const sum = entrySummary(entry).map((s, idx) =>
      audit.edited.has(entry.seq) && idx === 0 ? `<mark>${esc(s)}</mark>` : esc(s)).join(", ");
    return `<li class="entry${bad ? " bad" : ""}${after ? " after-bad" : ""}">
      <span class="bead">${entry.seq}</span>
      <div class="entry-main">
        <div class="entry-title"><b>${esc(STAGE_NAME[entry.agent] || entry.agent)}</b><span class="entry-sum">${sum}</span></div>
        <div class="hashes">hash <code>${hash.slice(0, 16)}</code>, follows <code>${entry.prev_hash.slice(0, 16)}</code></div>
      </div>
    </li>`;
  }).join("");

  const verdict = document.getElementById("verdict");
  const n = audit.lines.length;
  if (!result.ok) {
    verdict.className = "verdict bad";
    verdict.innerHTML = `${icon("veto")}<p>Broken at entry ${result.bad}. <span>Its contents no longer match its hash, so anyone re-checking the log sees the change.</span></p>`;
  } else if (result.head !== audit.keptHead) {
    verdict.className = "verdict bad";
    const why = audit.mode === "delete"
      ? `The remaining ${n} entries still chain correctly. The deletion shows because the last hash no longer matches the copy kept outside the log.`
      : `The forged entry chains correctly, because its hash was recomputed. The forgery shows because the last hash no longer matches the copy kept outside the log.`;
    verdict.innerHTML = `${icon("veto")}<p>Caught by the kept copy of the last hash. <span>${why}</span></p>`;
  } else {
    verdict.className = "verdict ok";
    verdict.innerHTML = `${icon("pass")}<p>Intact. <span>All ${n} entries match their hashes and link to the entry before. The last hash, ${audit.keptHead.slice(0, 16)}, matches the copy kept outside the log.</span></p>`;
  }
  for (const [id, mode] of [["t-income", "income"], ["t-forge", "forge"], ["t-delete", "delete"]]) {
    document.getElementById(id).setAttribute("aria-pressed", String(audit.mode === mode));
  }
}

async function tamper(mode) {
  if (!current) return;
  audit.lines = current.audit_lines.slice();
  audit.edited = new Set();
  audit.mode = mode;
  if (mode === "income") {
    audit.lines[0] = audit.lines[0].replace(/"income_agent_monthly_est":(\d+(?:\.\d+)?)/, (_, v) => `"income_agent_monthly_est":${Math.round(Number(v) * 3)}`);
    audit.edited.add(1);
  } else if (mode === "forge") {
    const last = audit.lines.length - 1;
    const line = audit.lines[last];
    const was = JSON.parse(line).payload.final_decision;
    const edited = line.replace(/"final_decision":"\w+"/, `"final_decision":"${was === "approve" ? "decline" : "approve"}"`);
    const { body, at } = splitLine(edited);
    const forged = await sha256(body);
    audit.lines[last] = edited.slice(0, at) + HASH_KEY + forged + edited.slice(at + 72);
    audit.edited.add(JSON.parse(line).seq);
  } else if (mode === "delete") {
    audit.lines.pop();
  } else {
    audit.mode = "original";
  }
  refreshAudit();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
