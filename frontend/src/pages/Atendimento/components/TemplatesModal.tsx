/**
 * Modal para gerenciar templates de resposta rápida.
 * CRUD completo: listar, criar, editar, deletar.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  Edit2,
  X,
  AlertCircle,
  Save,
} from "lucide-react";
import * as templateService from "@/services/atendimentoTemplatesService";
import type { ResponseTemplate } from "@/services/atendimentoTemplatesService";

interface TemplatesModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedCategory?: string;
  onSelectTemplate?: (template: ResponseTemplate) => void;
}

type FormMode = "list" | "create" | "edit";

export function TemplatesModal({
  isOpen,
  onClose,
  selectedCategory,
  onSelectTemplate,
}: TemplatesModalProps) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<FormMode>("list");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    text: "",
    category: selectedCategory || "general",
  });

  // Listar templates
  const { data: templates = [], isLoading } = useQuery({
    queryKey: ["templates", selectedCategory],
    queryFn: () => templateService.listTemplates(selectedCategory),
    enabled: isOpen && mode === "list",
  });

  // Criar template
  const createMutation = useMutation({
    mutationFn: () =>
      templateService.createTemplate({
        name: formData.name,
        text: formData.text,
        category: (formData.category as any) || "general",
        variables: templateService.extractVariables(formData.text),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setFormData({ name: "", text: "", category: selectedCategory || "general" });
      setMode("list");
    },
  });

  // Atualizar template
  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editingId) throw new Error("No template selected");
      return templateService.updateTemplate(editingId, {
        name: formData.name,
        text: formData.text,
        category: (formData.category as any) || "general",
        variables: templateService.extractVariables(formData.text),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      setFormData({ name: "", text: "", category: selectedCategory || "general" });
      setEditingId(null);
      setMode("list");
    },
  });

  // Deletar template
  const deleteMutation = useMutation({
    mutationFn: (templateId: string) =>
      templateService.deleteTemplate(templateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
  });

  const handleCreate = async () => {
    if (!formData.name.trim() || !formData.text.trim()) {
      alert("Preencha nome e texto do template");
      return;
    }
    await createMutation.mutateAsync();
  };

  const handleUpdate = async () => {
    if (!formData.name.trim() || !formData.text.trim()) {
      alert("Preencha nome e texto do template");
      return;
    }
    await updateMutation.mutateAsync();
  };

  const handleEdit = (template: ResponseTemplate) => {
    setEditingId(template.id);
    setFormData({
      name: template.name,
      text: template.text,
      category: template.category,
    });
    setMode("edit");
  };

  const handleSelectTemplate = (template: ResponseTemplate) => {
    if (onSelectTemplate) {
      onSelectTemplate(template);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-semibold text-gray-900">
            {mode === "list"
              ? "Templates de Resposta"
              : mode === "create"
                ? "Novo Template"
                : "Editar Template"}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {mode === "list" ? (
            <div className="space-y-4">
              {isLoading ? (
                <p className="text-sm text-gray-500">Carregando templates...</p>
              ) : templates.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-gray-500">
                  <AlertCircle className="h-10 w-10 opacity-30 mb-2" />
                  <p className="text-sm">Nenhum template criado ainda.</p>
                </div>
              ) : (
                templates.map((template) => (
                  <div
                    key={template.id}
                    className="bg-gray-50 rounded-lg border border-gray-200 p-4 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-900">
                          {template.name}
                        </h3>
                        <p className="text-xs text-gray-500 mt-0.5">
                          Categoria:{" "}
                          <span className="font-mono">{template.category}</span>
                          {template.variables &&
                            template.variables.length > 0 && (
                              <>
                                {" "}
                                • Variáveis:{" "}
                                {template.variables.map((v) => `{${v}}`).join(", ")}
                              </>
                            )}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-gray-400 bg-gray-200 rounded px-2 py-1">
                          {template.use_count}x usada{template.use_count !== 1 ? "s" : ""}
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-gray-700 bg-white rounded p-2 line-clamp-3">
                      {template.text}
                    </p>
                    <div className="flex items-center gap-2 pt-2">
                      {onSelectTemplate && (
                        <button
                          onClick={() => handleSelectTemplate(template)}
                          className="text-xs px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                        >
                          Usar
                        </button>
                      )}
                      <button
                        onClick={() => handleEdit(template)}
                        className="text-xs px-3 py-1.5 rounded bg-gray-200 text-gray-700 hover:bg-gray-300 transition-colors inline-flex items-center gap-1"
                      >
                        <Edit2 className="h-3 w-3" />
                        Editar
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(template.id)}
                        disabled={deleteMutation.isPending}
                        className="text-xs px-3 py-1.5 rounded bg-red-100 text-red-700 hover:bg-red-200 transition-colors inline-flex items-center gap-1 disabled:opacity-50"
                      >
                        <Trash2 className="h-3 w-3" />
                        Deletar
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nome do Template
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="Ex: Resposta padrão para perguntas sobre entrega"
                  className="w-full rounded-lg border border-gray-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Categoria
                </label>
                <select
                  value={formData.category}
                  onChange={(e) =>
                    setFormData({ ...formData, category: e.target.value })
                  }
                  className="w-full rounded-lg border border-gray-200 bg-white text-sm text-gray-900 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="general">Geral</option>
                  <option value="pergunta">Pergunta</option>
                  <option value="reclamacao">Reclamação</option>
                  <option value="devolucao">Devolução</option>
                  <option value="mensagem">Mensagem</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Texto do Template
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Use variáveis como {"{comprador}"}, {"{produto}"} (serão
                  substituídas)
                </p>
                <textarea
                  value={formData.text}
                  onChange={(e) =>
                    setFormData({ ...formData, text: e.target.value })
                  }
                  placeholder="Digite o texto do template com variáveis se necessário..."
                  rows={6}
                  className="w-full rounded-lg border border-gray-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
              </div>

              {templateService.extractVariables(formData.text).length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-xs font-medium text-blue-700">
                    Variáveis detectadas:
                  </p>
                  <p className="text-xs text-blue-600 mt-1">
                    {templateService
                      .extractVariables(formData.text)
                      .map((v) => `{${v}}`)
                      .join(", ")}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-end gap-3">
          {mode !== "list" && (
            <button
              onClick={() => {
                setMode("list");
                setFormData({ name: "", text: "", category: selectedCategory || "general" });
                setEditingId(null);
              }}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            >
              Voltar
            </button>
          )}
          {mode === "list" && (
            <button
              onClick={() => setMode("create")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Novo Template
            </button>
          )}
          {mode === "create" && (
            <button
              onClick={handleCreate}
              disabled={createMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              <Save className="h-4 w-4" />
              Salvar Template
            </button>
          )}
          {mode === "edit" && (
            <button
              onClick={handleUpdate}
              disabled={updateMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              <Save className="h-4 w-4" />
              Atualizar Template
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
