"use strict";
// Bearer tokens remain in memory and disappear on sign-out or page reload.
let token = null;
let offset = 0;
let generation = 0;
let role = null;
let catalogOffset = 0, obligationOffset = 0, selectedVersion = null, catalogGeneration = 0;
const limit = 20;
const element = id => document.getElementById(id);
const message = text => { element("message").textContent = text; };
function textNode(tag, text) { const node = document.createElement(tag); node.textContent = text; return node; }
async function api(path, options = {}) {
  const requestToken = token;
  const response = await fetch(`/api/v1${path}`, { ...options, headers: { ...options.headers, ...(requestToken ? { Authorization: `Bearer ${requestToken}` } : {}) } });
  if (token !== requestToken) throw new Error("Session changed while the request was running.");
  if (response.status === 401) { signOut(); throw new Error("Your session expired or credentials were invalid. Sign in again."); }
  if (!response.ok) throw new Error(`Request failed (${response.status}). Request ID: ${response.headers.get("X-Request-ID") || "unavailable"}`);
  return response.json();
}
function signOut() {
  token = null; role = null; generation++; offset = 0;
  catalogGeneration++; catalogOffset = 0; obligationOffset = 0; selectedVersion = null;
  for (const id of ["catalog-versions", "catalog-obligations"]) element(id).replaceChildren();
  for (const id of ["catalog-previous", "catalog-next", "obligation-previous", "obligation-next"]) element(id).disabled = true;
  element("workspace").hidden = true; element("login-panel").hidden = false;
  for (const id of ["reports", "detail", "history", "identity", "count", "simulation-result", "benchmark-result"]) element(id).replaceChildren();
  element("benchmark-file").value = "";
  element("simulation").reset();
  element("ingestion-preview").reset(); element("ingestion-result").replaceChildren();
  element("evidence-preview").reset(); element("evidence-result").replaceChildren();
}
async function loadReports() {
  const current = ++generation;
  const data = await api(`/gap-reports?limit=${limit}&offset=${offset}`);
  if (current !== generation || !token) return;
  element("reports").replaceChildren();
  element("count").textContent = `${data.total} reports · page ${Math.floor(offset / limit) + 1}`;
  element("previous").disabled = offset === 0;
  element("next").disabled = offset + limit >= data.total;
  if (!data.items.length) element("reports").textContent = "No reports available.";
  for (const report of data.items) {
    const button = textNode("button", report.regulatory_reference);
    button.className = "report";
    button.append(textNode("small", `${report.review_status} · ${report.report_id}`));
    button.addEventListener("click", () => showReport(report.report_id).catch(error => message(error.message)));
    element("reports").append(button);
  }
}
async function showReport(id) {
  const current = ++generation;
  message("");
  const [detail, history] = await Promise.all([api(`/gap-reports/${encodeURIComponent(id)}`), api(`/gap-reports/${encodeURIComponent(id)}/reviews`)]);
  if (current !== generation || !token) return;
  element("detail").replaceChildren(textNode("h3", detail.regulatory_reference), textNode("p", `Assessment: ${detail.assessment_status} · Review: ${detail.review_status}`));
  const findings = detail.report.findings || [];
  for (const finding of findings) {
    const article = document.createElement("article");
    article.append(textNode("h3", `${finding.status}: ${finding.requirement}`), textNode("p", finding.explanation));
    for (const evidence of finding.evidence || []) article.append(textNode("pre", `Section ${evidence.section_number}: ${evidence.section_title}\n${evidence.quote}`));
    element("detail").append(article);
  }
  const raw = document.createElement("details"); raw.append(textNode("summary", "Full report JSON"), textNode("pre", JSON.stringify(detail.report, null, 2))); element("detail").append(raw);
  if (role === "compliance_officer" && detail.review_status === "pending_review") {
    const form = document.createElement("form");
    const label = textNode("label", "Review rationale");
    const comment = document.createElement("textarea"); comment.required = true; comment.maxLength = 2000;
    label.append(comment); form.append(label);
    const decision = document.createElement("select"); decision.setAttribute("aria-label", "Review decision");
    for (const value of ["approved", "rejected"]) { const option = textNode("option", value); option.value = value; decision.append(option); }
    const submit = textNode("button", "Record human decision"); submit.type = "submit"; form.append(decision, submit);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (submit.disabled) return;
      if (!comment.value.trim()) { message("A review rationale is required."); return; }
      submit.disabled = true;
      try {
        await api(`/gap-reports/${encodeURIComponent(id)}/review`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision: decision.value, comment: comment.value.trim() }) });
        await showReport(id); message("Human decision recorded.");
      } catch (error) { message(error.message); submit.disabled = false; }
    });
    element("detail").append(form);
  }
  element("history").replaceChildren();
  if (!history.reviews.length) element("history").textContent = "No human decisions recorded.";
  for (const review of history.reviews) element("history").append(textNode("pre", `${review.previous_status} → ${review.new_status}\nReviewer ${review.reviewer_id} · ${review.reviewed_at}\n${review.comment}`));
}
element("login").addEventListener("submit", async event => {
  event.preventDefault(); message("");
  const form = event.currentTarget; const button = form.querySelector("button");
  if (button.disabled) return;
  button.disabled = true;
  try {
    const result = await api("/auth/login", { method: "POST", body: new URLSearchParams(new FormData(form)) });
    token = result.access_token; form.reset();
    const user = await api("/auth/me");
    role = user.role;
    element("identity").textContent = `Signed in as ${user.username} · ${user.role}`;
    element("workspace").hidden = false; element("login-panel").hidden = true;
    await loadReports();
  } catch (error) { signOut(); message(error.message); } finally { button.disabled = false; }
});
element("logout").addEventListener("click", () => { signOut(); message("Signed out."); });
element("refresh").addEventListener("click", () => loadReports().catch(error => message(error.message)));
element("previous").addEventListener("click", () => { offset = Math.max(0, offset - limit); loadReports().catch(error => message(error.message)); });
element("next").addEventListener("click", () => { offset += limit; loadReports().catch(error => message(error.message)); });
element("simulation").addEventListener("submit", async event => {
  event.preventDefault(); message("");
  if (event.currentTarget.querySelector("button").disabled) return;
  const file = element("scenario").files[0];
  if (!file) return;
  if (file.size > 1000000) { message("Choose a scenario smaller than 1 MB."); return; }
  const button = event.currentTarget.querySelector("button"); button.disabled = true;
  const sessionToken = token;
  element("simulation-result").replaceChildren();
  try {
    const scenario = JSON.parse(await file.text());
    const result = await api("/changes/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(scenario) });
    if (!token || token !== sessionToken) return;
    element("simulation-result").append(textNode("h3", "Hypothetical change-impact report"), textNode("p", "Policy matches are lexical review candidates, not confirmed control failures."), textNode("pre", JSON.stringify(result, null, 2)));
  } catch (error) { if (token === sessionToken) message(error instanceof SyntaxError ? "The selected file is not valid JSON." : error.message); }
  finally { button.disabled = false; }
});
element("benchmark-file").addEventListener("change", async event => {
  const file = event.target.files[0];
  const sessionToken = token;
  const output = element("benchmark-result"); output.replaceChildren(); message("");
  if (!file) return;
  if (file.size > 5000000) { message("Choose a benchmark report smaller than 5 MB."); return; }
  try {
    const report = JSON.parse(await file.text());
    const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
    const names = ["retrieval", "extraction", "gaps", "citations", "mapping", "runtime"];
    if (!object(report) || report.schema_version !== 1 || !object(report.results) || !object(report.inputs) || !Array.isArray(report.components_not_supplied) || !/^[a-f0-9]{64}$/.test(report.config_sha256)) throw new Error("Choose a report produced by the unified benchmark runner.");
    const supplied = Object.keys(report.results);
    if (!supplied.length || supplied.some(name => !names.includes(name) || !object(report.results[name])) || report.components_not_supplied.some(name => !names.includes(name)) || new Set([...supplied, ...report.components_not_supplied]).size !== names.length || supplied.some(name => report.components_not_supplied.includes(name))) throw new Error("The report has inconsistent benchmark components.");
    if (!token || token !== sessionToken) return;
    output.append(textNode("p", "Imported results: supplied-file metrics, not independently verified project performance."), textNode("p", `Components omitted: ${report.components_not_supplied.join(", ") || "none"}`));
    for (const [name, result] of Object.entries(report.results)) {
      const article = document.createElement("article"); article.append(textNode("h3", name));
      const summary = Object.fromEntries(Object.entries(result).filter(([key]) => !["per_case", "errors", "confusion_matrix"].includes(key)));
      article.append(textNode("pre", JSON.stringify(summary, null, 2)));
      const detail = document.createElement("details"); detail.append(textNode("summary", "All metrics and error details"), textNode("pre", JSON.stringify(result, null, 2))); article.append(detail); output.append(article);
    }
    const provenance = document.createElement("details"); provenance.append(textNode("summary", "Input provenance"), textNode("pre", JSON.stringify({ config_sha256: report.config_sha256, inputs: report.inputs }, null, 2))); output.append(provenance);
  } catch (error) { if (token === sessionToken) message(error instanceof SyntaxError ? "The selected benchmark file is not valid JSON." : error.message); }
});
async function loadVersions() {
  const current = ++catalogGeneration;
  const data = await api(`/catalog/versions?limit=20&offset=${catalogOffset}`);
  if (current !== catalogGeneration || !token) return;
  const output = element("catalog-versions"); output.replaceChildren(textNode("p", `${data.total} persisted versions`));
  element("catalog-previous").disabled = catalogOffset === 0;
  element("catalog-next").disabled = catalogOffset + 20 >= data.total;
  for (const version of data.items) {
    const button = textNode("button", version.title); button.className = "report";
    button.append(textNode("small", `${version.clauses} clauses · ${version.obligations} obligations`), textNode("small", `Source hash: ${version.content_hash}`));
    button.addEventListener("click", () => { selectedVersion = version.version_id; obligationOffset = 0; loadObligations().catch(error => message(error.message)); });
    output.append(button);
  }
}
async function loadObligations() {
  if (!selectedVersion) return;
  const current = ++catalogGeneration;
  const data = await api(`/catalog/obligations?version_id=${encodeURIComponent(selectedVersion)}&limit=20&offset=${obligationOffset}`);
  if (current !== catalogGeneration || !token) return;
  const output = element("catalog-obligations"); output.replaceChildren(textNode("p", `${data.total} obligation candidates`));
  element("obligation-previous").disabled = obligationOffset === 0;
  element("obligation-next").disabled = obligationOffset + 20 >= data.total;
  for (const obligation of data.items) {
    const article = document.createElement("article");
    article.append(textNode("h3", `Clause ${obligation.clause_number} · ${obligation.review_status}`), textNode("p", `${obligation.actor}: ${obligation.action}`), textNode("p", `Pages ${obligation.start_page}–${obligation.end_page} · ${obligation.quality_status} · clause ${obligation.clause_status}`), textNode("pre", obligation.evidence_quote));
    const button = textNode("button", "Find candidate policy sections");
    const matches = document.createElement("div");
    button.addEventListener("click", async () => {
      button.disabled = true; matches.replaceChildren(); const sessionToken = token;
      try {
        const result = await api(`/catalog/obligations/${encodeURIComponent(obligation.id)}/policy-matches`);
        if (!token || token !== sessionToken) return;
        matches.append(textNode("p", result.notice));
        if (!result.matches.length) matches.append(textNode("p", "No overlapping policy candidates found. This does not prove a compliance gap."));
        for (const match of result.matches) matches.append(textNode("h4", `${match.policy_code} · Section ${match.section_number}: ${match.section_title}`), textNode("p", `BM25 score: ${match.score.toFixed(3)} · Terms: ${match.matched_terms.join(", ")}`), textNode("pre", match.policy_text));
      } catch (error) { if (token === sessionToken) message(error.message); }
      finally { button.disabled = false; }
    });
    article.append(button, matches);
    output.append(article);
  }
}
element("catalog-refresh").addEventListener("click", () => loadVersions().catch(error => message(error.message)));
element("catalog-previous").addEventListener("click", () => { catalogOffset = Math.max(0, catalogOffset - 20); loadVersions().catch(error => message(error.message)); });
element("catalog-next").addEventListener("click", () => { catalogOffset += 20; loadVersions().catch(error => message(error.message)); });
element("obligation-previous").addEventListener("click", () => { obligationOffset = Math.max(0, obligationOffset - 20); loadObligations().catch(error => message(error.message)); });
element("obligation-next").addEventListener("click", () => { obligationOffset += 20; loadObligations().catch(error => message(error.message)); });
element("ingestion-preview").addEventListener("submit", async event => {
  event.preventDefault(); message("");
  if (event.currentTarget.querySelector("button").disabled) return;
  const file = element("ingestion-file").files[0]; if (!file) return;
  if (file.size > 5000000) { message("PDF preview limit is 5 MB."); return; }
  const button = event.currentTarget.querySelector("button"); button.disabled = true;
  const sessionToken = token; element("ingestion-result").replaceChildren();
  try {
    const body = new FormData(); body.append("file", file);
    const result = await api("/ingestion/preview", { method: "POST", body });
    if (!token || token !== sessionToken) return;
    element("ingestion-result").append(textNode("p", result.notice), textNode("p", `${result.pages} pages · ${result.clauses_found} clauses found · first ${result.preview_limit} shown`), textNode("pre", JSON.stringify(result, null, 2)));
  } catch (error) { if (token === sessionToken) message(error.message); } finally { button.disabled = false; }
});

element("evidence-preview").addEventListener("submit", async event => {
  event.preventDefault(); message("");
  const button = event.currentTarget.querySelector("button");
  if (button.disabled) return;
  const file = element("evidence-file").files[0]; if (!file) return;
  if (file.size > 5000000) { message("Evidence preview limit is 5 MB."); return; }
  const sessionToken = token; button.disabled = true; element("evidence-result").replaceChildren();
  try {
    const body = new FormData(); body.append("file", file);
    const result = await api("/ingestion/evidence-preview", { method: "POST", body });
    if (!token || token !== sessionToken) return;
    element("evidence-result").append(textNode("p", result.notice), textNode("pre", JSON.stringify(result, null, 2)));
  } catch (error) { if (token === sessionToken) message(error.message); }
  finally { button.disabled = false; }
});
