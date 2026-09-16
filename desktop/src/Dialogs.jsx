import React, { useEffect, useState } from "react";
import { AlertCircle, Bell, Clock3, Plus, Trash2, X } from "lucide-react";

function Modal({ title, description, icon: Icon, children, onClose }) {
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-heading">
          <span className="modal-icon">
            <Icon size={18} />
          </span>
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button className="modal-close" onClick={onClose}>
            <X size={17} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

export function SessionDialog({ onChoose }) {
  return (
    <Modal
      title="Saved sessions found"
      description="Choose how this run should use the sessions stored in the workflow file."
      icon={AlertCircle}
      onClose={() => onChoose(null)}
    >
      <div className="modal-body">
        <p>
          Resume keeps each provider conversation where it left off. Start fresh
          clears captured session IDs from this workflow in memory.
        </p>
      </div>
      <div className="modal-actions">
        <button className="quiet-button" onClick={() => onChoose("fresh")}>
          Start fresh
        </button>
        <button className="primary-button" onClick={() => onChoose("resume")}>
          Resume sessions
        </button>
      </div>
    </Modal>
  );
}

export function AttentionDialog({ request, onChoose }) {
  return (
    <Modal
      title={request.title || "Attention required"}
      description="This branch is waiting for your decision."
      icon={Bell}
      onClose={() => onChoose(false)}
    >
      <div className="modal-body">
        <p>{request.message}</p>
      </div>
      <div className="modal-actions">
        <button className="quiet-button" onClick={() => onChoose(false)}>
          Stop workflow
        </button>
        <button className="primary-button" onClick={() => onChoose(true)}>
          Continue workflow
        </button>
      </div>
    </Modal>
  );
}

export function UsageDialog({ event, onClose, onChangeModel, onSchedule }) {
  const [when, setWhen] = useState("");
  return (
    <Modal
      title="Provider usage limit"
      description="The workflow stopped at this node."
      icon={Clock3}
      onClose={onClose}
    >
      <div className="modal-body">
        <p className="usage-error">{event.error}</p>
        <label className="field">
          <span>Resume automatically at</span>
          <input
            type="datetime-local"
            value={when}
            onChange={(change) => setWhen(change.target.value)}
          />
        </label>
      </div>
      <div className="modal-actions">
        <button className="quiet-button" onClick={onClose}>
          Stop
        </button>
        <button className="quiet-button" onClick={onChangeModel}>
          Change model
        </button>
        <button
          className="primary-button"
          disabled={!when}
          onClick={() => onSchedule(new Date(when).getTime())}
        >
          Schedule resume
        </button>
      </div>
    </Modal>
  );
}

export function TemplatesDialog({ state, onSave, onOneOff, onClose }) {
  const [templates, setTemplates] = useState(state.templates || []);
  const [defaults, setDefaults] = useState(state.default_template_ids || []);
  const [oneOff, setOneOff] = useState(state.one_off_text || "");
  const [placement, setPlacement] = useState(
    state.one_off_placement || "append",
  );
  useEffect(() => {
    setTemplates(state.templates || []);
    setDefaults(state.default_template_ids || []);
  }, [state.templates, state.default_template_ids]);
  const update = (index, patch) =>
    setTemplates((current) =>
      current.map((item, at) => (at === index ? { ...item, ...patch } : item)),
    );
  const remove = (index) =>
    setTemplates((current) => current.filter((_, at) => at !== index));
  const toggleDefault = (id) =>
    setDefaults((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  const add = () =>
    setTemplates((current) => [
      ...current,
      {
        template_id: crypto.randomUUID(),
        name: "New template",
        content: "",
        placement: "append",
        built_in: false,
      },
    ]);
  const save = async () => {
    await onSave({ templates, default_template_ids: defaults });
    await onOneOff({ text: oneOff, placement });
    onClose();
  };
  return (
    <Modal
      title="Prompt templates"
      description="Set reusable context and a one time addition for the next run."
      icon={Plus}
      onClose={onClose}
    >
      <div className="modal-body template-body">
        <div className="template-section-label">SAVED TEMPLATES</div>
        {templates.map((template, index) => (
          <div className="template-card" key={template.template_id}>
            <div className="template-top">
              <label className="template-default">
                <input
                  type="checkbox"
                  checked={defaults.includes(template.template_id)}
                  onChange={() => toggleDefault(template.template_id)}
                />{" "}
                Default on
              </label>
              <select
                value={template.placement}
                onChange={(event) =>
                  update(index, { placement: event.target.value })
                }
              >
                <option value="prepend">Prepend</option>
                <option value="append">Append</option>
              </select>
              {!template.built_in && (
                <button title="Delete template" onClick={() => remove(index)}>
                  <Trash2 size={15} />
                </button>
              )}
            </div>
            <input
              className="template-name"
              value={template.name}
              disabled={template.built_in}
              onChange={(event) => update(index, { name: event.target.value })}
            />
            <textarea
              value={template.content}
              disabled={template.built_in}
              rows={3}
              onChange={(event) =>
                update(index, { content: event.target.value })
              }
            />
          </div>
        ))}
        <button className="field-action" onClick={add}>
          <Plus size={14} /> Add template
        </button>
        <div className="template-section-label">NEXT RUN ONLY</div>
        <textarea
          className="one-off-input"
          value={oneOff}
          rows={4}
          onChange={(event) => setOneOff(event.target.value)}
          placeholder="Extra context for the next run"
        />
        <select
          className="one-off-select"
          value={placement}
          onChange={(event) => setPlacement(event.target.value)}
        >
          <option value="prepend">Before prompt</option>
          <option value="append">After prompt</option>
        </select>
      </div>
      <div className="modal-actions">
        <button className="quiet-button" onClick={onClose}>
          Cancel
        </button>
        <button className="primary-button" onClick={save}>
          Save settings
        </button>
      </div>
    </Modal>
  );
}
