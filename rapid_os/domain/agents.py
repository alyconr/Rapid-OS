from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.core.paths import CURRENT_DIR


def generate_cursor_rules(context, current_dir=CURRENT_DIR):
    DEFAULT_AGENT_REGISTRY.get("cursor").activate(context, current_dir)


def generate_claude_config(context, current_dir=CURRENT_DIR):
    DEFAULT_AGENT_REGISTRY.get("claude").activate(context, current_dir)


def generate_antigravity_config(context, current_dir=CURRENT_DIR):
    DEFAULT_AGENT_REGISTRY.get("antigravity").activate(context, current_dir)


def generate_vscode_instructions(context, current_dir=CURRENT_DIR):
    DEFAULT_AGENT_REGISTRY.get("vscode").activate(context, current_dir)


def generate_agent_contexts(context, tools, current_dir=CURRENT_DIR):
    for adapter in DEFAULT_AGENT_REGISTRY.enabled(tools):
        adapter.activate(context, current_dir)

