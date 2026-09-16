"""Run-validation rules for workflow nodes, mixed into WorkflowCanvas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Sequence

from src.gui.conditional_node import CONDITION_REGISTRY, ConditionalNode, condition_requires_filename
from src.gui.control_flow.join_node import JoinNode
from src.gui.file_op_node import AttentionNode, FileOpNode
from src.gui.llm_node import WorkflowNode
from src.gui.script_runner.script_node import ALLOWED_SCRIPT_SUFFIXES, ScriptNode
from src.gui.variables import VariableNode
from src.gui.workflow_io import get_provider_for_model
from src.llm.cli_detection import is_provider_installed

if TYPE_CHECKING:
    from src.gui.canvas import WorkflowCanvas
GraphNode = WorkflowNode


class _ValidationMixin:
    """Pre-run validation plus the continuous invalid-node marker refresh."""

    def _node_validation_errors(
        self: "WorkflowCanvas",
        node: GraphNode,
        allowed_node_ids: set[str] | None = None,
    ) -> List[str]:
        from src.gui.loop_node import LoopNode
        from src.gui.git_action_node import GitActionNode

        valid_git_actions = {"git_add", "git_commit", "git_push"}
        valid_msg_sources = {"static", "from_file"}
        reasons: List[str] = []

        if isinstance(node, ConditionalNode):
            if condition_requires_filename(node.condition_type) and not node.filename.strip():
                reasons.append("has no filename set")
            if node.condition_type not in CONDITION_REGISTRY:
                reasons.append(f'has unknown condition type "{node.condition_type}"')
            return reasons

        if isinstance(node, AttentionNode):
            if not node.message_text.strip():
                reasons.append("has no attention message set")
            return reasons

        if isinstance(node, FileOpNode):
            if not node.filename.strip():
                reasons.append("has no filename set")
            return reasons

        if isinstance(node, ScriptNode):
            script_path = node.script_path.strip()
            if not script_path:
                reasons.append("has no script selected")
            else:
                suffix = script_path.lower()
                if not suffix.endswith(ALLOWED_SCRIPT_SUFFIXES):
                    reasons.append("must use a .bat, .cmd, or .ps1 script")
            return reasons

        if isinstance(node, VariableNode):
            return self.variable_validation_errors(node)

        if isinstance(node, LoopNode):
            return reasons
        if isinstance(node, JoinNode):
            return reasons

        if isinstance(node, GitActionNode):
            if node.git_action not in valid_git_actions:
                reasons.append(f'has unknown git action "{node.git_action}"')
                return reasons
            if node.msg_source not in valid_msg_sources:
                reasons.append(f'has unknown message source "{node.msg_source}"')
                return reasons
            if node.git_action == "git_commit":
                if node.msg_source == "static" and not node.commit_msg.strip():
                    reasons.append("has no commit message set")
                elif node.msg_source == "from_file" and not node.commit_msg_file.strip():
                    reasons.append("has no commit message file set")
            return reasons

        if not node.prompt_text.strip():
            reasons.append("has no prompt")
        reasons.extend(
            self.llm_variable_validation_errors(node, allowed_node_ids=allowed_node_ids)
        )
        if not node.model_id:
            reasons.append("has no model selected")
        else:
            provider = get_provider_for_model(node.model_id)
            if provider is None:
                reasons.append(f'has unknown model "{node.model_id}"')
            elif not is_provider_installed(provider):
                reasons.append(
                    f'needs the "{provider.cli_executable}" CLI, which is not installed'
                )
        return reasons

    def _validation_errors_by_node(
        self: "WorkflowCanvas",
        nodes: Sequence[GraphNode],
        allowed_node_ids: set[str] | None = None,
    ) -> Dict[str, List[str]]:
        errors: Dict[str, List[str]] = {}
        for node in nodes:
            reasons = self._node_validation_errors(node, allowed_node_ids=allowed_node_ids)
            if reasons:
                errors[node.node_id] = reasons
        return errors

    def refresh_node_validation_state(self: "WorkflowCanvas") -> Dict[str, List[str]]:
        """Update each canvas node's invalid marker based on current run validation rules."""
        errors_by_node = self._validation_errors_by_node(list(self._nodes.values()))
        for node in self._nodes.values():
            node.set_invalid(node.node_id in errors_by_node)
        return errors_by_node

    def _validate_nodes(self: "WorkflowCanvas", nodes: Sequence[GraphNode]) -> List[str]:
        node_ids = {node.node_id for node in nodes}
        errors_by_node = self._validation_errors_by_node(nodes, allowed_node_ids=node_ids)
        return [
            f'\u2022 "{getattr(node, "title", node.node_id)}" {reason}.'
            for node in nodes
            for reason in errors_by_node.get(node.node_id, [])
        ]

