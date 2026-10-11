/* Local, self-reported relevance review. No server or automatic approvals. */
"use strict";

function createState(packet, pending) {
  return {packet, reviews: JSON.parse(JSON.stringify(pending))};
}

function validateCase(state, entry) {
  const known = new Set(state.packet.records.map(r => r.id));
  if (!entry.reviewer || !entry.reviewer.trim()) throw new Error("Enter the reviewer name.");
  if (!entry.rationale || !entry.rationale.trim()) throw new Error("Record a source-backed rationale.");
  if (entry.full_corpus_reviewed !== true) throw new Error("Confirm review of the full 500-candidate subset.");
  const ids = entry.relevant_section_ids;
  if (!Array.isArray(ids) || new Set(ids).size !== ids.length || ids.some(id => !known.has(id))) {
    throw new Error("Unknown or duplicate candidate IDs.");
  }
  if (entry.answerability === "relevant_documents_present" && ids.length > 0) return;
  if (entry.answerability === "no_relevant_document_in_subset" && ids.length === 0) return;
  throw new Error("Choose an answerability decision consistent with the selected candidates.");
}

function changeCase(state, index, changes) {
  const entry = state.reviews.cases[index];
  Object.assign(entry, changes);
  entry.review_status = "pending";
}

function approveCase(state, index) {
  validateCase(state, state.reviews.cases[index]);
  state.reviews.cases[index].review_status = "approved";
}

function exportReviews(state, requireComplete) {
  if (requireComplete) {
    for (const entry of state.reviews.cases) {
      if (entry.review_status !== "approved") throw new Error("Complete and explicitly mark each query reviewed before exporting final labels.");
      validateCase(state, entry);
    }
  }
  return JSON.stringify(state.reviews, null, 2);
}

function restoreDraft(state, value) {
  const draft = JSON.parse(JSON.stringify(value));
  if (draft.schema_version !== 1 || draft.packet_sha256 !== state.reviews.packet_sha256 || !Array.isArray(draft.cases) || draft.cases.length !== state.reviews.cases.length) throw new Error("Draft belongs to another packet.");
  const known = new Set(state.packet.records.map(r => r.id));
  for (let i = 0; i < draft.cases.length; i++) {
    const row = draft.cases[i], expected = state.reviews.cases[i];
    if (row.scenario_id !== expected.scenario_id || row.query !== expected.query || row.split !== "test" || !Array.isArray(row.relevant_section_ids) || typeof row.rationale !== "string" || typeof row.full_corpus_reviewed !== "boolean" || !["pending", "relevant_documents_present", "no_relevant_document_in_subset"].includes(row.answerability) || (row.reviewer !== null && typeof row.reviewer !== "string")) throw new Error("Invalid draft case.");
    if (new Set(row.relevant_section_ids).size !== row.relevant_section_ids.length || row.relevant_section_ids.some(id => !known.has(id))) throw new Error("Invalid candidate selection.");
    row.review_status = "pending";
  }
  state.reviews = draft;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {createState, changeCase, approveCase, exportReviews, restoreDraft};
}

if (typeof document !== "undefined") {
  const data = JSON.parse(document.getElementById("review-data").textContent);
  const state = createState(data.packet, data.pending);
  let active = 0, page = 0;
  const byId = id => document.getElementById(id);
  const message = text => { byId("message").textContent = text; };
  const querySelect = byId("query");
  state.reviews.cases.forEach((entry, index) => {
    const option = document.createElement("option");
    option.value = index; option.textContent = entry.scenario_id + ": " + entry.query;
    querySelect.append(option);
  });
  function renderCandidates() {
    const text = byId("search").value.toLowerCase();
    const records = state.packet.records.filter(r => (r.id + " " + r.text + " " + state.packet.sources[r.content_hash].title).toLowerCase().includes(text));
    page = Math.min(page, Math.max(0, Math.ceil(records.length / 25) - 1));
    const container = byId("candidates"); container.replaceChildren();
    const selected = new Set(state.reviews.cases[active].relevant_section_ids);
    for (const record of records.slice(page * 25, page * 25 + 25)) {
      const article = document.createElement("article");
      const label = document.createElement("label");
      const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.checked = selected.has(record.id);
      checkbox.addEventListener("change", () => {
        const ids = new Set(state.reviews.cases[active].relevant_section_ids);
        if (checkbox.checked) ids.add(record.id); else ids.delete(record.id);
        changeCase(state, active, {relevant_section_ids: [...ids].sort()}); updateStatus();
      });
      label.append(checkbox, document.createTextNode(" Relevant: " + record.id)); article.append(label);
      const source = state.packet.sources[record.content_hash];
      const citation = document.createElement("p");
      citation.textContent = source.title + " — pages " + record.start_page + "–" + record.end_page + ". ";
      const url = new URL(source.source_url);
      if (url.protocol === "https:" && ["www.rbi.org.in", "rbi.org.in", "rbidocs.rbi.org.in"].includes(url.hostname)) {
        const link = document.createElement("a"); link.href = url.href + "#page=" + record.start_page;
        link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "Official PDF"; citation.append(link);
      }
      const quote = document.createElement("pre"); quote.textContent = record.text;
      article.append(citation, quote); container.append(article);
    }
    byId("paging").textContent = records.length + " matching candidates; page " + (page + 1) + " of " + Math.max(1, Math.ceil(records.length / 25));
    byId("previous").disabled = page === 0;
    byId("next").disabled = (page + 1) * 25 >= records.length;
  }
  function updateStatus() {
    const entry = state.reviews.cases[active];
    byId("status").textContent = entry.review_status + "; " + entry.relevant_section_ids.length + " selected. " + state.reviews.cases.filter(c => c.review_status === "approved").length + "/6 queries reviewed.";
  }
  function render() {
    const entry = state.reviews.cases[active];
    byId("reviewer").value = entry.reviewer || "";
    byId("rationale").value = entry.rationale;
    byId("answerability").value = entry.answerability;
    byId("full-corpus").checked = entry.full_corpus_reviewed;
    updateStatus(); renderCandidates();
  }
  querySelect.addEventListener("change", () => {active = Number(querySelect.value); page = 0; byId("search").value = ""; message(""); render();});
  byId("search").addEventListener("input", () => {page = 0; renderCandidates();});
  byId("previous").addEventListener("click", () => {page--; renderCandidates();});
  byId("next").addEventListener("click", () => {page++; renderCandidates();});
  for (const [id, field] of [["reviewer","reviewer"],["rationale","rationale"],["answerability","answerability"]]) {
    byId(id).addEventListener("input", () => {changeCase(state, active, {[field]: byId(id).value}); updateStatus();});
  }
  byId("full-corpus").addEventListener("change", () => {changeCase(state, active, {full_corpus_reviewed: byId("full-corpus").checked}); updateStatus();});
  byId("approve").addEventListener("click", () => {
    try {approveCase(state, active); updateStatus(); message("Your review is recorded for this query. Source obligations remain pending.");}
    catch (error) {message(error.message);}
  });
  function download(complete) {
    try {
      const content = exportReviews(state, complete);
      const url = URL.createObjectURL(new Blob([content], {type: "application/json"}));
      const link = document.createElement("a"); link.href = url;
      link.download = complete ? "reviewed_relevance.json" : "relevance_draft.json"; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      message("JSON exported. Save the draft before closing; edits are held only in this tab.");
    } catch (error) {message(error.message);}
  }
  byId("draft").addEventListener("click", () => download(false));
  byId("export").addEventListener("click", () => download(true));
  byId("import").addEventListener("change", async event => {
    try {
      const file = event.target.files[0]; if (!file) return;
      if (file.size > 1000000) throw new Error("Draft exceeds 1 MB.");
      const draft = JSON.parse(await file.text());
      restoreDraft(state, draft); render(); message("Draft restored. Confirm each query's review again before final export.");
    } catch (error) {message(error.message);}
    event.target.value = "";
  });
  render();
}
