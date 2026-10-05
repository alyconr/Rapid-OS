import sys
from pathlib import Path

# Add parent directory to path to import rapid
sys.path.append(str(Path(__file__).parent.parent))

try:
    import rapid

    print(f"DEBUG: SCRIPT_DIR (from rapid) = {rapid.SCRIPT_DIR}")
    print(f"DEBUG: TEMPLATES_DIR (from rapid) = {rapid.TEMPLATES_DIR}")

    stacks_dir = rapid.TEMPLATES_DIR / "stacks"
    if stacks_dir.exists():
        print(f"DEBUG: Listing files in {stacks_dir}:")
        for f in stacks_dir.glob("*.md"):
            print(f"  - {f.name}")
    else:
        print(f"DEBUG: Stacks directory not found at {stacks_dir}")

except ImportError as e:
    print(f"Error importing rapid: {e}")
except Exception as e:
    print(f"Error checking rapid config: {e}")
