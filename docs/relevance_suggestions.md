# Machine suggestions ? unverified

These shortlists reuse recorded BM25 and MiniLM vector retrieval. They are suggestions for human relevance review, not approved labels or independent ground truth. No new model/provider call or database write occurred. The blind packet and original benchmark results are unchanged.

The full suggestions are in `data/processed/validation/phase4_relevance_suggestions.json`. Each case retains pending status, an empty relevant-ID list and pending answerability. Review the full 500-candidate corpus; top-ranked passages may be unrelated, and the shortlist cannot prove that no relevant document exists.

RRF scores combine lexical and semantic ranks. Hybrid ranks are displayed for traceability but are not counted as independent evidence. Scores are not relevance probabilities. The existing subset contains card-conduct and cybersecurity sources; some other topic queries may have no relevant document.

Below are the first three candidates per query. This preview truncates long quotes at 400 characters; complete source quotes and every suggested candidate are in the JSON.

## probe-0 ? customer identity verification and ongoing due diligence

Candidate `5ac0a0fd-49fe-435b-bb33-cd4183836b60` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 32?32. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=32).

Recorded ranks: bm25=1, exact_vector=1, hybrid=1.

> The bank shall implement an authentication framework to ensure positive identity
> verification for customers accessing its services and to enable customers to 
> verify the authenticity of the bank, across all delivery channels.

Candidate `6c29e7cc-6afe-4499-9895-8850aa65b816` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 32?32. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=32).

Recorded ranks: bm25=4, exact_vector=2, hybrid=2.

> The bank shall act as the identity provider for identification and authentication of
> customers for access to partner systems using secure authentication 
> technologies.

Candidate `9abf6ecb-0ca2-404c-9ddf-c6dfe3812811` ? **unverified**.

Reserve Bank of India (Commercial Banks – Credit Cards and Debit Cards: Issuance and Conduct) Directions, 2025 (Updated as on October 1, 2026); pages 22?22. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/155MD.PDF#page=22).

Recorded ranks: bm25=3, exact_vector=3, hybrid=3.

> Card-issuers shall carry out due diligence in respect of the co-branding partner entity with
> which they intend to enter into tie-up for issue of such cards to protect themselves against 
> the reputation risk they are exposed to in such an arrangement.

## probe-1 ? outsourcing risk assessment and vendor monitoring

Candidate `74c7cf58-4e19-4ef2-a654-f6a2a442aa3f` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 34?34. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=34).

Recorded ranks: bm25=1, exact_vector=1, hybrid=1.

> The bank shall carefully evaluate the need for outsourcing critical processes and
> selection of vendor / partner based on comprehensive risk assessment.

Candidate `85418f6e-6295-431d-8fe4-03972a46b7de` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 34?34. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=34).

Recorded ranks: bm25=2, exact_vector=3, hybrid=2.

> The bank shall establish appropriate policies and procedures to evaluate,
> assess, approve, review, control and monitor the risks and materiality of all its 
> vendor / outsourcing activities.

Candidate `4a4becb4-ebff-4a3a-923f-c98210a325a1` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 34?34. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=34).

Recorded ranks: exact_vector=2, hybrid=3.

> The bank shall be accountable for ensuring appropriate management and
> assurance on security risks in outsourced and partner arrangements.

## probe-2 ? incident reporting and cybersecurity controls

Candidate `bdc2643d-3411-4d40-ae3d-7b2fb1fc3320` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 48?48. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=48).

Recorded ranks: bm25=1, exact_vector=8, hybrid=1.

> The bank shall encourage the reporting of suspicious behaviour incidents to the
> incident management team.

Candidate `c250841f-7295-4996-a1de-603a77dd0a5f` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 36?39. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=36).

Recorded ranks: bm25=7, exact_vector=7, hybrid=2.

> The ASP shall have a written incident 
> response procedure including the roles of staff / outsourced staff handling 
> such incidents.

Candidate `3537ada3-d7fb-4ed3-a752-b7fcaaf2d03b` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 12?13. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=12).

Recorded ranks: exact_vector=1, hybrid=3.

> The cybersecurity policy shall be distinct and separate from the broader IT 
> policy / Information Security policy so that it can highlight the risks from cyber 
> threats and the measures to address / mitigate these risks.

## probe-3 ? credit card customer consent and dispute resolution

Candidate `9ebd9de9-3852-43b9-8829-d43936ec4279` ? **unverified**.

Reserve Bank of India (Commercial Banks – Credit Cards and Debit Cards: Issuance and Conduct) Directions, 2025 (Updated as on October 1, 2026); pages 7?9. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/155MD.PDF#page=7).

Recorded ranks: exact_vector=1, hybrid=1.

> (iii) Similarly, with regard to retail credit cards, the requisite consent shall be sought from 
> the principal cardholder and not from the add-on cardholders.  
>  
> 9 
> Provided that, for blocking of business or retail credit cards, either the actual cardholder 
> or the principal cardholder can initiate the request. 
> (7) A card-issuer shall not report any credit information relating to a new credit ca

Excerpt truncated; see JSON for the complete quote.

Candidate `f6a5bf40-b1d3-4f90-abfc-f955aaf33410` ? **unverified**.

Reserve Bank of India (Commercial Banks – Credit Cards and Debit Cards: Issuance and Conduct) Directions, 2025 (Updated as on October 1, 2026); pages 7?9. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/155MD.PDF#page=7).

Recorded ranks: bm25=1, hybrid=2.

> If no consent is received for activating the card, the card-issuer is required to 
> close the credit card account without any cost to the customer within seven working days 
> from the date of seeking confirmation from the customer and shall also intimate the 
> customer that the credit card account has been closed.

Candidate `1bda1a34-27c6-44aa-a564-f96acf29b25d` ? **unverified**.

Reserve Bank of India (Commercial Banks – Credit Cards and Debit Cards: Issuance and Conduct) Directions, 2025 (Updated as on October 1, 2026); pages 16?17. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/155MD.PDF#page=16).

Recorded ranks: exact_vector=2, hybrid=3.

> The card-issuers shall 
> reverse the credit transaction to the cardholder’s bank account, if no consent / response 
> is received from the cardholder.

## probe-4 ? digital payment authentication and access review

Candidate `30aa6c1e-6fa1-4216-b393-feb08bc58e60` ? **unverified**.

Reserve Bank of India (Commercial Banks – Credit Cards and Debit Cards: Issuance and Conduct) Directions, 2025 (Updated as on October 1, 2026); pages 7?9. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/155MD.PDF#page=7).

Recorded ranks: bm25=1, exact_vector=1, hybrid=1.

> Alternatively, card-issuers may 
> use other digital modes with multifactor authentication to obtain explicit customer 
> consent.

Candidate `6c29e7cc-6afe-4499-9895-8850aa65b816` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 32?32. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=32).

Recorded ranks: bm25=2, exact_vector=2, hybrid=2.

> The bank shall act as the identity provider for identification and authentication of
> customers for access to partner systems using secure authentication 
> technologies.

Candidate `93349b48-b15e-46c7-88a2-c66c9cb0daaf` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 31?31. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=31).

Recorded ranks: exact_vector=3, hybrid=3.

> The bank shall implement centralised authentication and authorisation system
> for accessing and administering applications, operating systems, databases, 
> network and security devices / systems, point of connectivity (local / remote) 
> including enforcement of strong password policy, and following the principle of 
> least privileges and separation of duties.

## probe-5 ? business continuity and disaster recovery testing

Candidate `152ddf7c-0a23-486e-a0bb-7763ce2f2c3b` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 46?46. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=46).

Recorded ranks: bm25=3, exact_vector=1, hybrid=1.

> The bank shall ensure resilient capabilities in all interconnected systems and
> networks including those of vendors and partners and readiness demonstrated 
> through collaborative and coordinated resilience testing that meets the bank’s 
> recovery time objectives.

Candidate `b13c5583-9fa3-4c61-bf54-9cafe2eab4de` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 24?24. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=24).

Recorded ranks: bm25=1, exact_vector=3, hybrid=2.

> The bank shall put in place appropriate physical and environmental controls for
> securing location of critical assets including Data Centre (DC) and Disaster 
> Recovery (DR) sites from natural and man-made threats.  
> (Note: DC refers to primary data centre for a given application / system and DR 
> refers to its Disaster Recovery site / alternate site.)

Candidate `c86ad436-fd08-4970-b080-449f11656119` ? **unverified**.

Reserve Bank of India (Commercial Banks – Cybersecurity, Technology: Risk, Resilience and Assurance Framework) Directions, 2026 (Updated as on October 01, 2026); pages 44?44. [Official PDF](https://rbidocs.rbi.org.in/rdocs/notification/PDFs/410MD1C1DD4C43C9C49ED9033D64902636D9C.PDF#page=44).

Recorded ranks: bm25=10, exact_vector=2, hybrid=3.

> The bank shall 
> ensure demonstrated readiness through collaborative and co-ordinated 
> resilience testing that meets the bank’s RTO.

## Validation

23 review-packet and retrieval-scorer tests passed. They verify unchanged pending labels, exact source-quote copying, unique suggestions, rejection of modified predictions and exclusion of hybrid from independent fusion votes. No actual relevance labels or Recall scores were generated.
