# Plan: Ignore /conductor Directory

## Objective
Update `.gitignore` to exclude the `/conductor` directory from version control and prepare a branch for a Pull Request against `dev`.

## Key Files
- `.gitignore`

## Implementation Steps
1. **Sync with Base Branch**:
   - Checkout `dev`.
   - Pull the latest changes from `origin dev`.
2. **Create Feature Branch**:
   - Create and switch to a new branch named `task/ignore-conductor`.
3. **Update .gitignore**:
   - Add `/conductor` to the end of the `.gitignore` file.
4. **Verification**:
   - Run `git status` to ensure files in `/conductor` are no longer tracked/staged.
   - Run `git check-ignore conductor/some-file.md` to confirm the ignore rule is active.
5. **Commit and Push**:
   - Stage the updated `.gitignore`.
   - Commit with message: `chore: ignore /conductor directory`.
   - Push the branch `task/ignore-conductor` to `origin`.

## Verification & Testing
- **Command**: `git status`
  - *Expected*: `/conductor` directory should not appear in untracked files.
- **Command**: `git check-ignore conductor/`
  - *Expected*: Output should show `conductor/`.
