#!/bin/bash
# Setup script for primordial-rlm-experiment
# Clones RLM dependency and installs requirements

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Clone RLM if not present
if [ ! -d "rlm" ]; then
    echo "Cloning RLM..."
    git clone https://github.com/alexzhang13/rlm.git rlm
    echo "Installing RLM in editable mode..."
    pip install -e rlm
else
    echo "RLM already cloned."
fi

echo ""
echo "Setup complete. Run the experiment with:"
echo "  python run_experiment.py"
echo "  python vanilla_baseline.py"
