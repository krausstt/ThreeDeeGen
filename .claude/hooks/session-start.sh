#!/bin/bash
# Install Python deps for ThreeDeeGen in Claude Code on the web sessions.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt
echo "export PYTHONPATH=\"$CLAUDE_PROJECT_DIR\${PYTHONPATH:+:\$PYTHONPATH}\"" >> "$CLAUDE_ENV_FILE"
python3 -c "import tdg, manifold3d, trimesh, numba, skimage; print('ThreeDeeGen deps OK')"
