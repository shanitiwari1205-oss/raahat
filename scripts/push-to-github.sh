#!/usr/bin/env bash
# Creates the GitHub repo and pushes this project to it.
# Run this yourself: it reads the token from your shell environment, never
# from a file or command-line argument, so it never lands in this repo,
# shell history, or any tool log.
#
# Usage:
#   export GITHUB_TOKEN=ghp_xxx        # the brother's token -- set this yourself, don't paste it to Claude
#   export GITHUB_OWNER=brothers-username
#   export REPO_NAME=raahat            # optional, defaults to "raahat"
#   ./scripts/push-to-github.sh

set -euo pipefail

: "${GITHUB_TOKEN:?Set GITHUB_TOKEN in your shell first (export GITHUB_TOKEN=...), don't pass it as an argument}"
: "${GITHUB_OWNER:?Set GITHUB_OWNER to the GitHub username/org to create the repo under}"
REPO_NAME="${REPO_NAME:-raahat}"

cd "$(dirname "$0")/.."

echo "Creating repo ${GITHUB_OWNER}/${REPO_NAME} ..."
HTTP_STATUS=$(curl -s -o /tmp/raahat-repo-create.json -w "%{http_code}" \
  -X POST "https://api.github.com/user/repos" \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -d "{\"name\": \"${REPO_NAME}\", \"description\": \"RAAHAT -- EL-02 Intelligent & Transparent Disaster Relief Resource Allocation, ELEVATE 1.0\", \"private\": false}")

if [ "$HTTP_STATUS" = "201" ]; then
  echo "Repo created."
elif [ "$HTTP_STATUS" = "422" ]; then
  echo "Repo already exists under this account -- continuing to push to it."
else
  echo "GitHub API returned HTTP ${HTTP_STATUS}:"
  cat /tmp/raahat-repo-create.json
  exit 1
fi
rm -f /tmp/raahat-repo-create.json

echo "Pushing current branch to GitHub (token used only for this push, not stored in git config) ..."
CURRENT_BRANCH=$(git branch --show-current)
git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_OWNER}/${REPO_NAME}.git" "${CURRENT_BRANCH}:main"

# Point origin at the plain (token-free) URL for future pushes -- you'll need
# your own auth (gh auth login, or an SSH key) for those, this script's token
# is only used for this one push above.
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/${GITHUB_OWNER}/${REPO_NAME}.git"
else
  git remote add origin "https://github.com/${GITHUB_OWNER}/${REPO_NAME}.git"
fi

echo ""
echo "Done. Repo live at: https://github.com/${GITHUB_OWNER}/${REPO_NAME}"
echo "Remember to revoke/rotate GITHUB_TOKEN now that it's done its job."
