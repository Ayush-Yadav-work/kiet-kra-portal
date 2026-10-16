export type Role = 'VC' | 'DEAN'
export type DisplayStatus = 'NOT_SUBMITTED' | 'DRAFT' | 'SUBMITTED' | 'REJECTED' | 'APPROVED'

export interface User {
  id: string; username: string; name: string; role: Role
  department: { code: string; name: string } | null; must_change_password: boolean
}
export interface Period { id: number; index: number; label: string; year: string; opens_at: string; closes_at: string; is_open: boolean; is_closed: boolean }
export interface Kra { number: number; activity_text: string; nba_ref: string; naac_ref: string }
export interface Assignment {
  id: string; department: { code: string; name: string }; kra: Kra; year: string; target_text: string
  template: { key: string; version: number; title: string } | null
}
export interface Decision { id: string; decision: 'APPROVE' | 'REJECT' | 'RETURN'; reason: string; reviewer_name: string; granted_reopen: boolean; created_at: string; revision_sequence: number }
export interface SubmissionSummary { id: string | null; display_status: DisplayStatus; status?: string; achievement_text?: string; is_nil?: boolean; latest_decision?: Decision | null }
export interface Grant { id: string; starts_at: string; expires_at: string; source: 'REQUEST' | 'REVIEW'; active: boolean }
export interface ReopenRequest {
  id: string; submission_id: string; reason: string; state: 'PENDING' | 'APPROVED' | 'DENIED'; requested_at: string; requested_by: string
  decided_at: string | null; decided_by: string | null; decision_reason: string; department: string; kra_number: number; period: string; year: string
}
export interface PeriodEntry { period: Period; submission_id: string | null; display_status: DisplayStatus; achievement_text: string; remarks: string; is_nil: boolean }
export interface Activity { [field: string]: unknown }
export interface Payload { activities: Activity[] }
export interface SubmissionDetail {
  id: string; server_time: string; assignment: Assignment; period: Period; status: string; display_status: DisplayStatus
  is_nil: boolean; nil_reason: string; achievement_text: string; remarks: string; payload: Payload; edit_version: number
  editable: boolean; active_grant: Grant | null; grants: Grant[]; reopen_requests: ReopenRequest[]; can_request_reopen: boolean
  current_revision: { id: string; sequence: number; submitted_at: string } | null; latest_decision: Decision | null
  grant_option_available: boolean; period_entries: PeriodEntry[]
}

export type FieldType = 'text' | 'longtext' | 'integer' | 'decimal' | 'date' | 'select' | 'multiselect' | 'checklist' | 'ratings' | 'table' | 'auto'
export interface Field {
  id: string; label: string; type: FieldType; required?: boolean; max_length?: number; min?: number; max?: number
  options?: string[]; items?: string[]; columns?: Field[]; min_rows?: number; max_rows?: number
  guidance?: string; help?: string; placeholder?: string; suggestions?: string[]; width?: string
  decimal_places?: number; scale?: number[]; scale_labels?: string[]; source?: 'year' | 'department'
  when?: { field: string; in: string[] }; editor?: 'grid' | 'cards'
}
export interface Section { id: string; title: string; intro?: string; fields: Field[] }
export interface Schema {
  key: string; version: number; title: string; activity: { label: string; min: number; max: number }
  page: { format: string; landscape?: boolean; style?: string }
  sections: Section[]; evidence: { categories: string[]; required: string[]; note?: string }
}
