# Create your own GitHub repository

The source bundle is complete locally. No repository was created or pushed
on your behalf. Use a separate repository for each project.

## First run

1. Extract the ZIP into a normal folder.
2. Open a terminal inside the extracted project.
3. Run the demo and the test command from README.md.
4. Read the generated report and the model limitations.
5. Before editing, optionally run:

       python tools/verify_bundle.py

## Create an actual repository

From inside the project folder:

    git init -b main
    git add .
    git diff --cached --stat
    git commit -m "Add recovered engineering project and tested software core"

Use your own Git identity if Git asks for name/email. Do not invent an author
identity or recreate old commits.

If you use the GitHub CLI, sign in to your own account and create a private
repository. Substitute the repository name recommended in PROJECT_SUBMISSION.md:

    gh auth login
    gh repo create YOUR_REPOSITORY_NAME --private --source . --remote origin --push

Alternatively, create an empty repository in GitHub's website, copy its actual
remote URL, and use:

    git remote add origin YOUR_ACTUAL_REPOSITORY_URL
    git push -u origin main

The ignored recovered_sources folder contains original recovery archives and
does not need to be uploaded. Current code, tests, technical input files and
synthetic examples remain available for code review.

The CI workflow runs on future pushes and pull requests. It has not been run
on GitHub during bundle preparation. Local tests were run on Python 3.12/Linux;
Windows launch scripts are supplied but were not executed here.

## Continue building

Select a task in CONTINUE_BUILDING.md, create a branch, and work in your terminal
with your preferred coding assistant. Keep real review decisions, commands,
failures and follow-up commits. Submit the actual repository URL and accurate
AI-use/ownership description.
