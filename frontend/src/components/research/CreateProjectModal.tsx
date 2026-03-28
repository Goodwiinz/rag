'use client';

import { useState } from 'react';
import { Loader2, Plus, X } from 'lucide-react';
import type { ProjectCreate } from '@/services/projectService';

type CreateProjectPayload = Omit<ProjectCreate, 'workspace_id'>;

export interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (payload: CreateProjectPayload) => Promise<void>;
}

export function CreateProjectModal({
  isOpen,
  onClose,
  onCreate,
}: CreateProjectModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [projectType, setProjectType] = useState<CreateProjectPayload['project_type']>('research');
  const [deadline, setDeadline] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleAddTag = () => {
    const next = tagInput.trim();
    if (!next || tags.includes(next)) return;
    setTags((prev) => [...prev, next]);
    setTagInput('');
  };

  const handleRemoveTag = (tag: string) => {
    setTags((prev) => prev.filter((t) => t !== tag));
  };

  const reset = () => {
    setName('');
    setDescription('');
    setProjectType('research');
    setDeadline('');
    setTagInput('');
    setTags([]);
  };

  const handleClose = () => {
    if (submitting) return;
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim() || undefined,
        project_type: projectType,
        deadline: deadline || undefined,
        tags,
      });
      reset();
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-mono font-bold text-[#D4A039]">Create Research Project</h2>
          <button onClick={handleClose} className="p-1 text-gray-500 hover:text-gray-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Project Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., ML Healthcare"
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#D4A039]"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short project summary"
              rows={3}
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#D4A039] resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
                Project Type
              </label>
              <select
                value={projectType}
                onChange={(e) =>
                  setProjectType(
                    e.target.value as CreateProjectPayload['project_type']
                  )
                }
                className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#D4A039]"
              >
                <option value="research">Research</option>
                <option value="literature_review">Literature Review</option>
                <option value="thesis">Thesis</option>
                <option value="paper">Paper</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
                Deadline
              </label>
              <input
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#D4A039]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Tags
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddTag();
                  }
                }}
                placeholder="Add tag and press Enter"
                className="flex-1 px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#D4A039]"
              />
              <button
                onClick={handleAddTag}
                type="button"
                aria-label="add tag"
                className="px-3 py-2 bg-[#D4A039]/10 text-[#D4A039] border border-[#D4A039]/30 rounded hover:bg-[#D4A039]/20 transition-colors"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {tags.map((tag) => (
                  <button
                    type="button"
                    key={tag}
                    onClick={() => handleRemoveTag(tag)}
                    className="px-2 py-1 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 hover:border-red-400 hover:text-red-300"
                  >
                    {tag}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || submitting}
            className="flex items-center gap-2 px-4 py-2 bg-[#D4A039]/10 text-[#D4A039] border border-[#D4A039]/30 rounded font-mono text-sm hover:bg-[#D4A039]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Create Project
          </button>
        </div>
      </div>
    </div>
  );
}

export default CreateProjectModal;
