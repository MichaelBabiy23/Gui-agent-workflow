import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import {
  Bot,
  CirclePlay,
  Code2,
  FileCode2,
  FilePlus2,
  GitBranch,
  GitMerge,
  Hourglass,
  Megaphone,
  Route,
  Variable,
} from "lucide-react";

export const nodeKinds = {
  llm: { label: "LLM CALL", Icon: Bot, tone: "blue" },
  create_file: { label: "CREATE FILE", Icon: FilePlus2, tone: "green" },
  truncate_file: { label: "TRUNCATE FILE", Icon: FileCode2, tone: "amber" },
  delete_file: { label: "DELETE FILE", Icon: FileCode2, tone: "red" },
  conditional: { label: "CONDITION", Icon: GitBranch, tone: "amber" },
  loop: { label: "LOOP", Icon: Route, tone: "purple" },
  join: { label: "JOIN", Icon: GitMerge, tone: "purple" },
  git_action: { label: "GIT ACTION", Icon: GitBranch, tone: "pink" },
  script_runner: { label: "SCRIPT", Icon: Code2, tone: "cyan" },
  attention: { label: "ATTENTION", Icon: Megaphone, tone: "amber" },
  variable: { label: "VARIABLE", Icon: Variable, tone: "teal" },
  start: { label: "START", Icon: CirclePlay, tone: "green" },
};

function summary(node) {
  switch (node.node_type) {
    case "llm":
      return node.model
        ? `${node.model} · ${node.prompt || "Add a prompt"}`
        : "Select a model";
    case "variable":
      return node.variable_name
        ? `$${node.variable_name} = ${node.variable_value || "empty"}`
        : "Set a variable";
    case "conditional":
      return node.condition_type === "git_changes"
        ? "Git has changes"
        : `File empty · ${node.filename || "Set file"}`;
    case "loop":
      return `Repeat ${node.loop_count || 1} times`;
    case "join":
      return `Wait for ${node.wait_for_count || 2} arrivals`;
    case "git_action":
      return node.git_action?.replaceAll("_", " ") || "Select action";
    case "script_runner":
      return node.script_path || "Select a script";
    case "attention":
      return node.message || "Set a message";
    default:
      return node.filename || "Set a filename";
  }
}

function GraphNode({ data, selected }) {
  const node = data.node;
  const kind = nodeKinds[node.node_type] || nodeKinds.llm;
  const Icon = kind.Icon;
  const isStart = node.node_type === "start";
  return (
    <div
      className={`graph-node tone-${kind.tone} ${isStart ? "is-start" : ""} ${selected ? "selected" : ""} ${node.invalid ? "invalid" : ""} status-${node.status || "idle"}`}
    >
      {!isStart && (
        <Handle
          id="input"
          type="target"
          position={Position.Left}
          className="flow-handle input"
        />
      )}
      <div className="graph-node-top">
        <span className="graph-node-icon">
          <Icon size={15} strokeWidth={2.2} />
        </span>
        <span className="graph-node-kind">{kind.label}</span>
        {node.status === "running" || node.status === "looping" ? (
          <Hourglass size={14} className="spin" />
        ) : null}
        {node.invalid && (
          <span className="node-warning" title={node.validation?.join("\n")}>
            !
          </span>
        )}
      </div>
      <div className="graph-node-name">
        {isStart ? "Start workflow" : node.name}
      </div>
      {!isStart && <div className="graph-node-summary">{summary(node)}</div>}
      {["conditional", "loop"].includes(node.node_type) ? (
        <>
          <Handle
            id={node.node_type === "loop" ? "loop" : "true"}
            type="source"
            position={Position.Right}
            style={{ top: 29 }}
            className="flow-handle positive"
          />
          <Handle
            id={node.node_type === "loop" ? "done" : "false"}
            type="source"
            position={Position.Right}
            style={{ top: 68 }}
            className="flow-handle negative"
          />
          <div className="port-hint top">
            {node.node_type === "loop" ? "LOOP" : "TRUE"}
          </div>
          <div className="port-hint bottom">
            {node.node_type === "loop" ? "DONE" : "FALSE"}
          </div>
        </>
      ) : (
        <Handle
          id="output"
          type="source"
          position={Position.Right}
          className="flow-handle output"
        />
      )}
    </div>
  );
}

export default memo(GraphNode);
