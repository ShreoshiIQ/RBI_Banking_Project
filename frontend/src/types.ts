export type Role = "viewer" | "admin" | "compliance_officer";

export interface User {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
}

export interface GapReportListItem {
  report_id: string;
  regulatory_reference: string;
  assessment_status: string;
  review_status: string;
  created_at: string;
}

export interface Evidence {
  section_id: string;
  section_number: string;
  section_title: string;
  quote: string;
}

export interface Finding {
  requirement: string;
  status: "supported" | "partial" | "missing" | "potential_conflict";
  explanation: string;
  evidence: Evidence[];
  suggested_action: string;
}

export interface GapReportDetail {
  report_id: string;
  regulatory_reference: string;
  assessment_status: string;
  review_status: string;
  report: {
    findings: Finding[];
    overall_explanation: string;
    summary: { total: number; supported: number; partial: number; missing: number; potential_conflicts: number };
    generated_at: string;
  };
}

export interface RemediationAction {
  kind: string;
  description: string;
  owner_role: string;
}

export interface RegisterItem {
  gap_id: string;
  requirement: string;
  status?: string;
  risk: { score: number; band: string; contributions: Record<string, number>; target_days: number; domain: string };
  applicability: { status: string; basis?: { rule: string } };
  remediation: { actions: RemediationAction[]; policy_redline: string | null; method: string };
}

export interface RemediationRegister {
  items: RegisterItem[];
  human_queue: { gap_id: string; score: number; reasons: string[] }[];
  risk_model: { version: string };
  trace: { step: string; ms: number }[];
}

export interface ReviewEvent {
  id: number;
  reviewer_id: string;
  previous_status: string;
  new_status: string;
  comment: string;
  reviewed_at: string;
}
