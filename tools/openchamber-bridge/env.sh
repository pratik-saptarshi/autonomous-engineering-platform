# OpenCode-OpenChamber bridge — environment initialization.
#
# Source this from the VM's shell initialization (~/.bashrc) or from any
# session that dispatches bridge work:
#   source tools/openchamber-bridge/env.sh
#
# OPENCHAMBER_BRIDGE_HOME is the bridge's runtime data home: the
# dispatcher writes its ledger (ledger.jsonl) there. Kit-internal files
# (dispatch.py, brief-footer.txt, brief-template.md) always resolve
# relative to the script itself, never via this variable.
#
# Default when unset: the live executing home in the AEP goal workspace
# when it exists, else the directory containing this file.
if [ -z "${OPENCHAMBER_BRIDGE_HOME:-}" ]; then
  _oc_bridge_default="$HOME/workspace/goals/autonomous-code-defense-factory/hidden_files/openchamber-bridge"
  if [ ! -d "$_oc_bridge_default" ]; then
    _oc_bridge_default="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fi
  export OPENCHAMBER_BRIDGE_HOME="$_oc_bridge_default"
  unset _oc_bridge_default
fi
