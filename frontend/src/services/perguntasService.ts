import api from './api';

// ─── Types ────────────────────────────────────────────────────────────────

export interface QuestionDB {
  id: string;
  ml_question_id: number;
  ml_account_id: string;
  mlb_id: string;
  item_title: string | null;
  item_thumbnail: string | null;
  text: string;
  status: string;
  buyer_id: number | null;
  buyer_nickname: string | null;
  date_created: string;
  answer_text: string | null;
  answer_date: string | null;
  answer_source: string | null;
  ai_suggestion_text: string | null;
  ai_suggestion_confidence: string | null;
  ai_suggested_at: string | null;
  synced_at: string;
  created_at: string;
  updated_at: string;
}

export interface QuestionsListResponse {
  total: number;
  page: number;
  limit: number;
  questions: QuestionDB[];
}

export interface QuestionStats {
  total: number;
  unanswered: number;
  answered: number;
  urgent: number;
  avg_response_time_hours: number | null;
  by_account: Record<string, number>;
}

export interface AISuggestion {
  suggestion: string;
  confidence: 'high' | 'medium' | 'low';
  question_type: string | null;
  cached: boolean;
  latency_ms: number | null;
}

export interface SyncResult {
  synced: number;
  new: number;
  updated: number;
  errors: number;
}

// ─── API Calls ────────────────────────────────────────────────────────────

export async function listQuestions(params: {
  status?: string;
  ml_account_id?: string;
  mlb_id?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<QuestionsListResponse> {
  const { data } = await api.get('/perguntas/', { params });
  return data;
}

export async function getQuestionStats(mlAccountId?: string): Promise<QuestionStats> {
  const params = mlAccountId ? { ml_account_id: mlAccountId } : {};
  const { data } = await api.get('/perguntas/stats', { params });
  return data;
}

export async function syncQuestions(): Promise<SyncResult> {
  const { data } = await api.post('/perguntas/sync');
  return data;
}

export async function answerQuestion(
  questionId: string,
  text: string,
  accountId: string,
  source: 'manual' | 'ai' | 'template' = 'manual',
  suggestionWasEdited = false,
): Promise<void> {
  await api.post(`/perguntas/${questionId}/answer`, {
    text,
    account_id: accountId,
    source,
    suggestion_was_edited: suggestionWasEdited,
  });
}

export async function getSuggestion(
  questionId: string,
  regenerate = false,
): Promise<AISuggestion> {
  const { data } = await api.post(`/perguntas/${questionId}/suggest`, { regenerate });
  return data;
}

export async function getQuestionsByListing(mlbId: string): Promise<QuestionsListResponse> {
  const { data } = await api.get(`/perguntas/by-listing/${mlbId}`);
  return data;
}
