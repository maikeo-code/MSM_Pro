/**
 * Service para gerenciar templates de resposta rápida no módulo de Atendimento.
 */
import api from "./api";

export interface ResponseTemplate {
  id: string;
  name: string;
  text: string;
  category: "general" | "pergunta" | "reclamacao" | "devolucao" | "mensagem";
  variables?: string[];
  use_count: number;
  created_at: string;
  updated_at: string;
}

export interface ResponseTemplateInput {
  name: string;
  text: string;
  category: "general" | "pergunta" | "reclamacao" | "devolucao" | "mensagem";
  variables?: string[];
}

/**
 * Lista templates de resposta do usuário.
 */
export async function listTemplates(
  category?: string
): Promise<ResponseTemplate[]> {
  const params = new URLSearchParams();
  if (category) params.append("category", category);

  const url =
    params.toString() === ""
      ? "/api/v1/atendimento/templates"
      : `/api/v1/atendimento/templates?${params}`;

  const response = await api.get(url);
  return response.data;
}

/**
 * Obtém um template específico.
 */
export async function getTemplate(templateId: string): Promise<ResponseTemplate> {
  const response = await api.get(`/api/v1/atendimento/templates/${templateId}`);
  return response.data;
}

/**
 * Cria um novo template.
 */
export async function createTemplate(
  data: ResponseTemplateInput
): Promise<ResponseTemplate> {
  const response = await api.post("/api/v1/atendimento/templates", data);
  return response.data;
}

/**
 * Atualiza um template existente.
 */
export async function updateTemplate(
  templateId: string,
  data: ResponseTemplateInput
): Promise<ResponseTemplate> {
  const response = await api.put(
    `/api/v1/atendimento/templates/${templateId}`,
    data
  );
  return response.data;
}

/**
 * Deleta um template.
 */
export async function deleteTemplate(templateId: string): Promise<void> {
  await api.delete(`/api/v1/atendimento/templates/${templateId}`);
}

/**
 * Extrai variáveis do texto de um template (formato {nome}).
 */
export function extractVariables(text: string): string[] {
  const regex = /\{([a-z_]+)\}/gi;
  const matches: string[] = [];
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (!matches.includes(match[1])) {
      matches.push(match[1]);
    }
  }

  return matches;
}

/**
 * Preenche um template com valores de variáveis.
 * Ex: fillTemplate("Olá {nome}", { nome: "João" }) => "Olá João"
 */
export function fillTemplate(
  template: string,
  variables: Record<string, string>
): string {
  let result = template;
  for (const [key, value] of Object.entries(variables)) {
    result = result.replace(new RegExp(`\\{${key}\\}`, "gi"), value);
  }
  return result;
}
