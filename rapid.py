#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

from rapid_os.cli.main import (
    CONFIG_FILE,
    CURRENT_DIR,
    PROJECT_RAPID_DIR,
    RAPID_HOME,
    SCRIPT_DIR,
    TEMPLATES_DIR,
    add_visual_reference,
    create_parser,
    deploy_assistant,
    generate_mcp_config,
    generate_prompt,
    init_project,
    main,
    manage_skills,
    refine_standard,
    regenerate_context,
    scope_feature,
    show_guide,
)
from rapid_os.core.config import load_project_config, save_project_config
from rapid_os.core.filesystem import check_node_installed, create_backup
from rapid_os.core.output import (
    clear_screen,
    print_error,
    print_step,
    print_success,
    print_warning,
)
from rapid_os.domain.agents import (
    generate_antigravity_config,
    generate_claude_config,
    generate_cursor_rules,
    generate_vscode_instructions,
)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
