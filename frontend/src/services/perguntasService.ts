import api from './api';

export interface MLQuestion {
  id: number;
  text: string;
  status: string;
  date_created: string;
  item_id: string;
  seller_id: number;
  from: { id: number; nickname: string };
  answer: { text: string; date_created: string } | null;
  _account_nickname: string;
  _account_id: string;
}

export interface QuestionsResponse {
  total: number;
  questions: MLQuestion[];
}

export async function listQuestions(
  status = "UNANSWERED",
  limit = 20,
): Promise<QuestionsResponse> {
  const { data } = await api.get<QuestionsResponse>(
    `/perguntas/?status=${status}&limit=${limit}`,
  );
  return data;
}

export async function answerQuestion(
  questionId: number,
  text: string,
  accountId: string,
): Promise<void> {
  await api.post(`/perguntas/${questionId}/answer`, {
    text,
    account_id: accountId,
  });
}
