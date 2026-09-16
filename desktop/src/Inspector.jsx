import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  MessageSquareText,
  Settings2,
  TerminalSquare,
} from "lucide-react";
import { nodeKinds } from "./GraphNode.jsx";
const MarkdownMessage = React.lazy(() => import("./MarkdownMessage.jsx"));

function TextField({
  label,
  value,
  onCommit,
  multiline = false,
  placeholder = "",
}) {
  const [draft, setDraft] = useState(value ?? "");
  useEffect(() => setDraft(value ?? ""), [value]);
  const props = {
    value: draft,
    placeholder,
    onChange: (event) => setDraft(event.target.value),
    onBlur: () => {
      if (draft !== (value ?? "")) onCommit(draft);
    },
  };
  return (
    <label className="field">
      <span>{label}</span>
      {multiline ? <textarea {...props} rows={7} /> : <input {...props} />}
    </label>
  );
}

function SelectField({ label, value, options, onChange }) {
  return (
    <label className="field">
      <span>{label}</span>
      <span className="select-wrap">
        <select
          value={value || ""}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown size={15} />
      </span>
    </label>
  );
}

function Toggle({ label, checked, onChange, hint }) {
  return (
    <label className="toggle-field">
      <span>
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
      <input
        type="checkbox"
        checked={!!checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <i />
    </label>
  );
}

function ChatOutput({ node }) {
  const [active, setActive] = useState(0);
  useEffect(
    () => setActive(Math.max(0, (node.conversations?.length || 1) - 1)),
    [node.id, node.conversations?.length],
  );
  const chats = node.conversations || [];
  const chat = chats[active];
  if (!chats.length)
    return (
      <div className="empty-output">
        <MessageSquareText size={30} />
        <strong>No conversations yet</strong>
        <span>
          Run this node to see prompts, tool activity, and replies here.
        </span>
      </div>
    );
  return (
    <div className="chat-output">
      <div className="chat-tabs">
        {chats.map((item, index) => (
          <button
            key={item.id}
            className={active === index ? "active" : ""}
            onClick={() => setActive(index)}
          >
            Chat {index + 1}
          </button>
        ))}
      </div>
      <div className="chat-items">
        {chat?.items.map((item, index) => (
          <div
            key={`${item.item_id}-${index}`}
            className={`chat-item kind-${item.kind}`}
          >
            <div className="chat-item-heading">
              {item.kind === "user"
                ? item.sender || "Prompt sent"
                : item.kind === "assistant"
                  ? "Assistant"
                  : item.kind === "tool"
                    ? item.name || "Tool activity"
                    : "Note"}
              {item.status && <span>{item.status}</span>}
            </div>
            {item.command && <code>{item.command}</code>}
            {item.path && <code>{item.path}</code>}
            {item.text && (
              <div className="chat-text">
                {item.kind === "assistant" ? (
                  <React.Suspense fallback={<span>Rendering reply...</span>}>
                    <MarkdownMessage text={item.text} />
                  </React.Suspense>
                ) : (
                  item.text
                )}
              </div>
            )}
            {item.output && (
              <details>
                <summary>Output</summary>
                <pre>{item.output}</pre>
              </details>
            )}
            {item.error && <div className="chat-error">{item.error}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Inspector({
  node,
  state,
  onPatch,
  onBrowseScript,
  onNodeTemplates,
}) {
  const [tab, setTab] = useState("settings");
  useEffect(() => setTab("settings"), [node?.id]);
  const providers = state.models || [];
  const modelOptions = useMemo(
    () =>
      providers.flatMap((provider) =>
        provider.models.map((model) => ({
          value: model.id,
          label: `${provider.label} · ${model.label}${provider.installed ? "" : " (CLI missing)"}`,
          provider: provider.name,
          model,
        })),
      ),
    [providers],
  );
  if (!node)
    return (
      <aside className="inspector">
        <div className="inspector-head">
          <div className="eyebrow">WORKFLOW</div>
          <h2>Overview</h2>
          <p>Select a node to edit its settings and see its output.</p>
        </div>
        <div className="overview-stat">
          <strong>{state.nodes?.length || 0}</strong>
          <span>Nodes</span>
        </div>
        <div className="overview-stat">
          <strong>{state.connections?.length || 0}</strong>
          <span>Connections</span>
        </div>
        <div className="overview-path">
          PROJECT FOLDER
          <br />
          <span>
            {state.project_folder || "Choose a project folder to run workflows"}
          </span>
        </div>
      </aside>
    );
  const patch = (key, value) => onPatch(node.id, { [key]: value });
  const kind = nodeKinds[node.node_type] || nodeKinds.llm;
  const selectedModel = modelOptions.find(
    ({ value }) => node.model === value || node.model?.startsWith(`${value}:`),
  );
  const provider = providers.find(
    ({ name }) => name === selectedModel?.provider,
  );
  const effort = node.model?.split(":")[1] || "";
  const hasOutput = node.node_type === "llm" || !!node.output;
  const effectiveTemplates = (side) => {
    const global = state.default_template_ids || [];
    const local = node[`${side}_template_ids`] || [];
    const disabled = node[`${side}_disabled_global_template_ids`] || [];
    return [
      ...new Set([...global.filter((id) => !disabled.includes(id)), ...local]),
    ];
  };
  const toggleTemplate = (side, id) => {
    const current = effectiveTemplates(side);
    onNodeTemplates(
      node.id,
      side,
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  };
  return (
    <aside className="inspector">
      <div className="inspector-head">
        <div className="eyebrow">{kind.label}</div>
        <h2>{node.name}</h2>
        <p>
          {node.status === "running"
            ? "Running now"
            : node.invalid
              ? "Complete the highlighted settings before running"
              : "Ready to run"}
        </p>
      </div>
      <div className="inspector-tabs">
        <button
          className={tab === "settings" ? "active" : ""}
          onClick={() => setTab("settings")}
        >
          <Settings2 size={15} /> Settings
        </button>
        <button
          className={tab === "output" ? "active" : ""}
          onClick={() => setTab("output")}
        >
          <TerminalSquare size={15} /> Output
        </button>
      </div>
      {tab === "output" ? (
        node.node_type === "llm" ? (
          <ChatOutput node={node} />
        ) : (
          <div className="plain-output">
            {hasOutput ? (
              <pre>{node.output}</pre>
            ) : (
              <div className="empty-output">
                <TerminalSquare size={30} />
                <strong>No output yet</strong>
                <span>Run this node to see its activity.</span>
              </div>
            )}
          </div>
        )
      ) : (
        <div className="inspector-fields" key={node.id}>
          {node.validation?.length > 0 && (
            <div className="validation-note">
              <AlertCircle size={16} />
              <span>{node.validation.join(" · ")}</span>
            </div>
          )}
          <TextField
            label="Name"
            value={node.name}
            onCommit={(value) => patch("name", value)}
          />
          {node.node_type === "llm" && (
            <>
              <SelectField
                label="Model"
                value={selectedModel?.value || ""}
                options={[
                  { value: "", label: "Select a model" },
                  ...modelOptions,
                ]}
                onChange={(value) => {
                  const choice = modelOptions.find(
                    (option) => option.value === value,
                  );
                  patch(
                    "model",
                    choice?.model.variants.length
                      ? `${value}:${choice.model.default_variant || choice.model.variants[0].id}`
                      : value,
                  );
                }}
              />
              {selectedModel?.model.variants.length > 0 && (
                <SelectField
                  label="Effort"
                  value={effort}
                  options={selectedModel.model.variants.map((item) => ({
                    value: item.id,
                    label: item.label,
                  }))}
                  onChange={(value) =>
                    patch("model", `${selectedModel.value}:${value}`)
                  }
                />
              )}
              {provider?.profiles.length > 0 && (
                <SelectField
                  label="Profile"
                  value={node.profile_name || ""}
                  options={[
                    { value: "", label: "Default account" },
                    ...provider.profiles.map((name) => ({
                      value: name,
                      label: name,
                    })),
                  ]}
                  onChange={(value) => patch("profile_name", value)}
                />
              )}
              <div className="field-group-title">SESSION</div>
              <Toggle
                label="Resume previous session"
                checked={node.resume_session_enabled}
                onChange={(value) => patch("resume_session_enabled", value)}
              />
              <Toggle
                label="Save named session"
                checked={node.save_session_enabled}
                onChange={(value) => patch("save_session_enabled", value)}
              />
              {node.save_session_enabled && (
                <>
                  <TextField
                    label="Session name"
                    value={node.save_session_name}
                    onCommit={(value) => patch("save_session_name", value)}
                  />
                  <Toggle
                    label="Restart at this node"
                    checked={node.restart_session_enabled}
                    onChange={(value) =>
                      patch("restart_session_enabled", value)
                    }
                  />
                </>
              )}
              <SelectField
                label="Resume named session"
                value={node.resume_named_session_name || ""}
                options={[
                  { value: "", label: "None" },
                  ...(node.available_named_sessions || []).map((name) => ({
                    value: name,
                    label: name,
                  })),
                ]}
                onChange={(value) => patch("resume_named_session_name", value)}
              />
              <div className="field-group-title">PROMPT</div>
              <TextField
                label="Prompt"
                value={node.prompt}
                onCommit={(value) => patch("prompt", value)}
                multiline
                placeholder="What should this model do?"
              />
              {(state.templates || []).length > 0 && (
                <div className="template-picks">
                  <div className="field-group-title">PROMPT TEMPLATES</div>
                  {["prepend", "append"].map((side) => (
                    <div key={side}>
                      <strong>
                        {side === "prepend" ? "Before prompt" : "After prompt"}
                      </strong>
                      {state.templates.map((template) => (
                        <label key={`${side}-${template.template_id}`}>
                          <input
                            type="checkbox"
                            checked={effectiveTemplates(side).includes(
                              template.template_id,
                            )}
                            onChange={() =>
                              toggleTemplate(side, template.template_id)
                            }
                          />
                          {template.name}
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
              )}
              <div className="field">
                <span>Prompt preview</span>
                <div className="prompt-preview">
                  {Array.isArray(node.preview)
                    ? node.preview[0]
                    : node.preview || "Write a prompt to see its preview."}
                </div>
                {Array.isArray(node.preview) && node.preview[1]?.length > 0 && (
                  <small className="warning-text">
                    {node.preview[1].join(" · ")}
                  </small>
                )}
              </div>
            </>
          )}
          {["create_file", "truncate_file", "delete_file"].includes(
            node.node_type,
          ) && (
            <>
              <SelectField
                label="Operation"
                value={node.node_type}
                options={[
                  { value: "create_file", label: "Create file" },
                  { value: "truncate_file", label: "Truncate file" },
                  { value: "delete_file", label: "Delete file" },
                ]}
                onChange={(value) => patch("node_type", value)}
              />
              <TextField
                label="Filename"
                value={node.filename}
                onCommit={(value) => patch("filename", value)}
              />
            </>
          )}
          {node.node_type === "conditional" && (
            <>
              <SelectField
                label="Condition"
                value={node.condition_type}
                options={[
                  { value: "file_empty", label: "File is empty" },
                  { value: "git_changes", label: "Git has changes" },
                ]}
                onChange={(value) => patch("condition_type", value)}
              />
              {node.condition_type === "file_empty" && (
                <TextField
                  label="Filename"
                  value={node.filename}
                  onCommit={(value) => patch("filename", value)}
                />
              )}
            </>
          )}
          {node.node_type === "loop" && (
            <label className="field">
              <span>Iterations</span>
              <input
                type="number"
                min="1"
                value={node.loop_count || 1}
                onChange={(event) =>
                  patch("loop_count", Number(event.target.value))
                }
              />
            </label>
          )}
          {node.node_type === "join" && (
            <label className="field">
              <span>Wait for arrivals</span>
              <input
                type="number"
                min="2"
                value={node.wait_for_count || 2}
                onChange={(event) =>
                  patch("wait_for_count", Number(event.target.value))
                }
              />
            </label>
          )}
          {node.node_type === "attention" && (
            <TextField
              label="Message"
              value={node.message}
              onCommit={(value) => patch("message", value)}
              multiline
            />
          )}
          {node.node_type === "variable" && (
            <>
              <TextField
                label="Variable name"
                value={node.variable_name}
                onCommit={(value) => patch("variable_name", value)}
              />
              <SelectField
                label="Value type"
                value={node.variable_type}
                options={[
                  { value: "text", label: "Text" },
                  { value: "number", label: "Number" },
                ]}
                onChange={(value) => patch("variable_type", value)}
              />
              <TextField
                label="Value"
                value={node.variable_value}
                onCommit={(value) => patch("variable_value", value)}
              />
            </>
          )}
          {node.node_type === "git_action" && (
            <>
              <SelectField
                label="Action"
                value={node.git_action}
                options={[
                  { value: "git_add", label: "Add" },
                  { value: "git_commit", label: "Commit" },
                  { value: "git_push", label: "Push" },
                ]}
                onChange={(value) => patch("git_action", value)}
              />
              {node.git_action === "git_commit" && (
                <>
                  <SelectField
                    label="Message source"
                    value={node.msg_source}
                    options={[
                      { value: "static", label: "Text" },
                      { value: "from_file", label: "File" },
                    ]}
                    onChange={(value) => patch("msg_source", value)}
                  />
                  <TextField
                    label={
                      node.msg_source === "from_file"
                        ? "Message file"
                        : "Commit message"
                    }
                    value={
                      node.msg_source === "from_file"
                        ? node.commit_msg_file
                        : node.commit_msg
                    }
                    onCommit={(value) =>
                      patch(
                        node.msg_source === "from_file"
                          ? "commit_msg_file"
                          : "commit_msg",
                        value,
                      )
                    }
                  />
                </>
              )}
            </>
          )}
          {node.node_type === "script_runner" && (
            <>
              <TextField
                label="Script path"
                value={node.script_path}
                onCommit={(value) => patch("script_path", value)}
              />
              <button
                className="field-action"
                onClick={() => onBrowseScript(node.id)}
              >
                Browse project scripts
              </button>
              <Toggle
                label="Send Enter automatically"
                checked={node.auto_send_enter}
                onChange={(value) => patch("auto_send_enter", value)}
              />
            </>
          )}
        </div>
      )}
    </aside>
  );
}
