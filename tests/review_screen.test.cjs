const test = require('node:test');
const assert = require('node:assert/strict');
const {createState, changeCase, approveCase, exportReviews, restoreDraft} = require('../src/regintel/mapping/review_screen.js');

function fixture() {
  // All simulated reviewer actions below are test fixtures, not project approvals.
  const packet = {records: [{id:'a'}, {id:'b'}]};
  const pending = {schema_version:1, packet_sha256:'fixture', cases:[{scenario_id:'fixture-0',query:'Fixture query',split:'test',review_status:'pending', reviewer:null,
    rationale:'', full_corpus_reviewed:false, answerability:'pending', relevant_section_ids:[]}]};
  return createState(packet, pending);
}
test('pending reviews cannot be exported as completed labels', () => {
  const state = fixture();
  assert.throws(() => exportReviews(state,true), /explicitly/);
  assert.equal(JSON.parse(exportReviews(state,false)).cases[0].review_status, 'pending');
});
test('approval requires named review, full-corpus attestation and coherent selection', () => {
  const state = fixture();
  assert.throws(() => approveCase(state,0), /reviewer/);
  changeCase(state,0,{reviewer:'UNIT TEST',rationale:'Fixture source rationale',answerability:'relevant_documents_present', relevant_section_ids:['a']});
  assert.throws(() => approveCase(state,0), /full 500/);
  changeCase(state,0,{full_corpus_reviewed:true});
  approveCase(state,0);
  assert.equal(JSON.parse(exportReviews(state,true)).cases[0].review_status,'approved');
  changeCase(state,0,{rationale:'Changed test decision'});
  assert.throws(() => exportReviews(state,true), /explicitly/);
});
test('no relevant documents needs an empty selection and rejects foreign IDs', () => {
  const state = fixture();
  changeCase(state,0,{reviewer:'UNIT TEST',rationale:'Fixture rationale',full_corpus_reviewed:true,
    answerability:'no_relevant_document_in_subset', relevant_section_ids:['a']});
  assert.throws(() => approveCase(state,0), /consistent/);
  changeCase(state,0,{answerability:'relevant_documents_present', relevant_section_ids:['foreign']});
  assert.throws(() => approveCase(state,0), /Unknown/);
  changeCase(state,0,{answerability:'no_relevant_document_in_subset', relevant_section_ids:[]});
  approveCase(state,0);
  assert.equal(JSON.parse(exportReviews(state,true)).cases[0].answerability,'no_relevant_document_in_subset');
});
test('restored drafts retain decisions but return to pending', () => {
  const state = fixture();
  changeCase(state,0,{reviewer:'UNIT TEST',rationale:'Fixture rationale',full_corpus_reviewed:true,
    answerability:'no_relevant_document_in_subset'});
  approveCase(state,0);
  const draft = JSON.parse(exportReviews(state,true));
  restoreDraft(state,draft);
  assert.equal(state.reviews.cases[0].review_status,'pending');
  assert.equal(draft.cases[0].review_status,'approved');
  assert.throws(() => exportReviews(state,true), /explicitly/);
});
test('stale and malformed drafts leave the current state untouched', () => {
  const state = fixture(), original = exportReviews(state,false);
  const stale = JSON.parse(original); stale.packet_sha256='wrong-packet';
  assert.throws(() => restoreDraft(state,stale), /another packet/);
  const invalid = JSON.parse(original); invalid.cases[0].full_corpus_reviewed='true';
  assert.throws(() => restoreDraft(state,invalid), /Invalid draft/);
  assert.equal(exportReviews(state,false),original);
});
