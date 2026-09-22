#!/usr/bin/env bash
# Install reddit-find Claude Code skill
# Usage: curl -fsSL https://raw.githubusercontent.com/tomas-butora/reddit-find/master/install-skill.sh | bash

set -e

SKILL_URL="https://raw.githubusercontent.com/tomas-butora/reddit-find/master/skills/reddit-find/SKILL.md"
INSTALL_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills/reddit-find}"

echo "Installing reddit-find skill..."
mkdir -p "$INSTALL_DIR"
curl -fsSL "$SKILL_URL" -o "$INSTALL_DIR/SKILL.md"
echo "Skill installed: $INSTALL_DIR/SKILL.md"
echo ""
echo "Next steps:"
echo "  1. pip install git+https://github.com/tomas-butora/reddit-find.git"
echo "  2. reddit-find search \"cold email\" -s sales --titles-only"
