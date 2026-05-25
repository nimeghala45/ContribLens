import streamlit as st
from github import Github
from github import Auth
from dotenv import load_dotenv
import os
import requests

load_dotenv()

githubToken = os.getenv("GITHUB_TOKEN")
nemotronKey = os.getenv("NVIDIA_API_KEY")

auth = Auth.Token(githubToken)
github = Github(auth=auth, per_page=10)

st.set_page_config(
    page_title="ContribLens",
    page_icon="🔍",
    layout="wide"
)


@st.cache_data(ttl=300)
def getFiles(repoName):
    files = []
    try:
        repo = github.get_repo(repoName)
        contents = repo.get_contents("")
        for item in contents:
            files.append(item.name)
    except:
        pass
    return files


@st.cache_data(ttl=300)
def getReadme(repoName):
    text = ""
    try:
        repo = github.get_repo(repoName)
        readme = repo.get_readme()
        text = readme.decoded_content.decode(errors="ignore")
    except:
        pass
    return text


@st.cache_data(ttl=300)
def getIssues(repoName):
    issues = []
    try:
        repo = github.get_repo(repoName)
        repoIssues = repo.get_issues(state="open")
        for issue in repoIssues:
            if issue.pull_request:
                continue
            labels = [l.name.lower() for l in issue.labels]
            issues.append({
                "number": issue.number,
                "title": issue.title,
                "body": issue.body or "",
                "url": issue.html_url,
                "labels": labels
            })
    except:
        pass
    return issues


@st.cache_data(ttl=300)
def getRepoMeta(repoName):
    try:
        repo = github.get_repo(repoName)
        return {
            "full_name": repo.full_name,
            "description": repo.description or "",
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "watchers": repo.subscribers_count,
            "language": repo.language or "Not specified"
        }
    except:
        return None


def scoreRepo(files, issueCount):
    score = 0
    reasons = []
    missing = []

    if "README.md" in files:
        score += 25
        reasons.append("README.md found (+25)")
    else:
        missing.append("README.md not found (-25)")

    if "CONTRIBUTING.md" in files:
        score += 25
        reasons.append("CONTRIBUTING.md found (+25)")
    else:
        missing.append("CONTRIBUTING.md not found (-25)")

    if ".github" in files:
        score += 20
        reasons.append(".github/ folder found (+20)")
    else:
        missing.append("No .github/ folder (-20)")

    if "docs" in files:
        score += 15
        reasons.append("docs/ folder found (+15)")
    else:
        missing.append("No docs/ folder (-15)")

    if issueCount > 0:
        score += 15
        reasons.append(f"{issueCount} open issues found (+15)")
    else:
        missing.append("No open issues (-15)")

    return score, reasons, missing


def mentorAdvice(files, issueCount):
    advice = []
    complexity = "Small"

    if len(files) > 15:
        complexity = "Large"
    elif len(files) > 8:
        complexity = "Medium"

    advice.append(f"Repository complexity: {complexity} ({len(files)} root items)")

    if "README.md" in files:
        advice.append("Read README.md first — it explains the project purpose and setup")

    if "CONTRIBUTING.md" in files:
        advice.append("Read CONTRIBUTING.md — it has the exact rules for submitting contributions")

    if "docs" in files:
        advice.append("Browse docs/ — architecture and setup guides are usually here")

    if issueCount == 0:
        advice.append("No open issues — try improving docs or setup instructions as a first contribution")

    return advice, complexity


def difficultyLevel(issue):
    difficulty = "Medium"
    evidence = []
    confidence = "Medium"
    labels = issue["labels"]
    body = issue["body"]

    if "good first issue" in labels:
        difficulty = "Easy"
        evidence.append("Label: good first issue")
        confidence = "High"
    elif "documentation" in labels:
        difficulty = "Easy"
        evidence.append("Label: documentation")
        confidence = "High"
    elif "bug" in labels:
        difficulty = "Medium"
        evidence.append("Label: bug")
        confidence = "Medium"
    elif "enhancement" in labels:
        difficulty = "Medium"
        evidence.append("Label: enhancement")
        confidence = "Medium"
    elif "help wanted" in labels:
        difficulty = "Medium"
        evidence.append("Label: help wanted")
        confidence = "Medium"

    if len(body) > 1500:
        difficulty = "Hard"
        evidence.append(f"Long description ({len(body)} chars)")
        confidence = "High"
    elif len(body) < 100 and not evidence:
        evidence.append("Very short description — hard to estimate")
        confidence = "Low"

    if not evidence:
        evidence.append("No labels — estimated from description length only")
        confidence = "Low"

    return difficulty, evidence, confidence


def callNemotron(systemPrompt, userPrompt, maxTokens=600):
    if not nemotronKey:
        return None, "NVIDIA_API_KEY not found in .env file"

    headers = {
        "Authorization": f"Bearer {nemotronKey}",
        "Content-Type": "application/json"
    }

    primaryModel = "nvidia/llama-3.3-nemotron-super-49b-v1"
    fallbackModel = "meta/llama-3.1-8b-instruct"

    for attempt, model in enumerate([primaryModel, fallbackModel]):
        try:
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": systemPrompt},
                    {"role": "user", "content": userPrompt}
                ],
                "max_tokens": maxTokens,
                "temperature": 0.2
            }

            waitTime = 40 if attempt == 0 else 20

            response = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=waitTime
            )

            if response.status_code != 200:
                continue

            data = response.json()
            result = data["choices"][0]["message"]["content"]

            if attempt == 1:
                result = result + "\n\n*(Response)*"

            return result, None

        except requests.exceptions.Timeout:
            if attempt == 0:
                continue
            return None, "Both models timed out. Try again in a moment."

        except Exception as e:
            if attempt == 0:
                continue
            return None, str(e)

    return None, "Could not get a response. Check your API key and try again."


def buildMentorPrompt(repoName, files, readme, issueCount, score, reasons, missing, complexity):
    fileList = ", ".join(files[:20])
    readmeSnippet = readme[:1200] if readme else "No README found"
    foundText = "\n".join(f"  + {r}" for r in reasons)
    missingText = "\n".join(f"  - {m}" for m in missing)

    return f"""You are reviewing the GitHub repository: {repoName}

ACTUAL REPOSITORY DATA — base your entire response on this only:
- Root files/folders: {fileList}
- Complexity: {complexity} ({len(files)} items at root)
- Open issues: {issueCount}
- Contributor friendliness score: {score}/100

What exists:
{foundText}

What is missing:
{missingText}

README (first 1200 chars):
{readmeSnippet}

Give a beginner contributor:
1. PROJECT: One sentence — what does this project do?
2. START HERE: Which specific file from the list above should they read first, and exactly why?
3. FIRST CONTRIBUTION: One realistic task grounded in what actually exists. If CONTRIBUTING.md is missing, say so.
4. WATCH OUT: What will confuse a new contributor based on what is missing or unclear?

Only reference files that appear in the list above. If something is missing, say it is missing."""


def buildPRDraftPrompt(repoName, issue, files, readme):
    readmeSnippet = readme[:600] if readme else "No README"
    fileList = ", ".join(files[:15])
    labelList = ", ".join(issue["labels"]) if issue["labels"] else "none"

    return f"""You are helping a beginner contributor write their first GitHub comment expressing interest in an issue.

Repository: {repoName}
Issue #{issue['number']}: {issue['title']}
Labels: {labelList}
Issue description: {issue['body'][:500] if issue['body'] else 'No description'}

Repository files: {fileList}
README snippet: {readmeSnippet}

Write a short, friendly GitHub comment (3-4 sentences) that:
1. Expresses genuine interest in working on this issue
2. Briefly describes their approach based on what they can actually see in the repo
3. Asks one clarifying question if the issue is unclear

Sound like a real person, not a bot. No corporate language."""


def buildMaintainerPrompt(repoName, files, readme, issues, score, reasons, missing):
    fileList = ", ".join(files[:20])
    readmeSnippet = readme[:1000] if readme else "No README found"
    foundText = "\n".join(f"  + {r}" for r in reasons)
    missingText = "\n".join(f"  - {m}" for m in missing)

    issuesSample = ""
    for issue in issues[:5]:
        labelText = ", ".join(issue["labels"]) if issue["labels"] else "no labels"
        issuesSample += f"  - #{issue['number']}: {issue['title']} [{labelText}]\n"

    if not issuesSample:
        issuesSample = "  No open issues found."

    return f"""You are an open source community advisor reviewing the repository: {repoName}

You are speaking to the MAINTAINER (repo owner), not a contributor.

ACTUAL REPOSITORY STATE:
- Root files: {fileList}
- Friendliness score: {score}/100
- What exists: {foundText}
- What is missing: {missingText}

Current open issues (sample):
{issuesSample}

README (first 1000 chars):
{readmeSnippet}

Give the maintainer an honest report with exactly these sections:

1. BIGGEST BARRIER: What is the single thing most likely to stop a new contributor right now?

2. QUICK WINS (3 items): Specific changes they can make this week to improve contributor onboarding. Reference actual missing files.

3. ISSUE HEALTH: Are their open issues labeled well? What label categories are missing? Suggest 3-5 labels they should add.

4. README GAPS: What sections are missing from their README that contributors typically need? (setup, contributing, architecture, etc.)

5. DRAFT CONTRIBUTING.MD: Write a short starter CONTRIBUTING.md they can add to the repo right now (keep it under 150 words).

Be direct and honest. This is a health report, not praise."""


def buildJourneyPrompt(repoName, files, readme, issues, score, reasons, missing):
    fileList = ", ".join(files[:20])
    readmeSnippet = readme[:800] if readme else "No README found"
    labeledIssues = [i for i in issues if i["labels"]]
    unlabeledIssues = [i for i in issues if not i["labels"]]
    hasContributing = "CONTRIBUTING.md" in files
    hasReadme = "README.md" in files
    hasDocs = "docs" in files

    return f"""You are simulating the experience of a brand new contributor arriving at: {repoName}

Walk through their journey step by step, based ONLY on this actual repository data:

Repository data:
- Files at root: {fileList}
- README exists: {hasReadme}
- CONTRIBUTING.md exists: {hasContributing}
- docs/ folder exists: {hasDocs}
- Open issues: {len(issues)} total, {len(labeledIssues)} labeled, {len(unlabeledIssues)} unlabeled
- Friendliness score: {score}/100
- Missing: {", ".join(missing) if missing else "nothing"}

README preview: {readmeSnippet}

Simulate the journey as numbered steps. For each step show:
- What the contributor DOES
- What they FIND (based on actual data above)
- Whether they get BLOCKED or can CONTINUE
- The FRICTION level: None / Low / Medium / High

Example format:
Step 1: Lands on repository homepage
Finds: README.md exists ✓
Result: Can continue
Friction: None

Step 2: Looks for contribution guide
Finds: No CONTRIBUTING.md ✗
Result: BLOCKED — unclear how to contribute
Friction: High

Continue until they either successfully find a first issue or get permanently blocked.

End with:
OVERALL FRICTION: Low / Medium / High
ESTIMATED TIME TO FIRST CONTRIBUTION: X hours/days
TOP BLOCKER: The single biggest thing causing friction

Be honest. If the repo has gaps, show the contributor getting blocked. Do not invent files."""


def buildComparePrompt(repo1, repo2, files1, files2, score1, score2, issues1, issues2, readme1, readme2):
    return f"""You are helping a beginner decide which of two GitHub repositories to contribute to first.

REPOSITORY 1: {repo1}
- Score: {score1}/100
- Files: {", ".join(files1[:15])}
- Open issues: {len(issues1)}
- README preview: {readme1[:400] if readme1 else "No README"}

REPOSITORY 2: {repo2}
- Score: {score2}/100
- Files: {", ".join(files2[:15])}
- Open issues: {len(issues2)}
- README preview: {readme2[:400] if readme2 else "No README"}

Give a clear recommendation:
1. RECOMMENDATION: Which repo should a beginner contribute to first, and the single most important reason why?
2. REPO 1 STRENGTHS: What makes {repo1} good for beginners (be specific to the data)?
3. REPO 2 STRENGTHS: What makes {repo2} good for beginners (be specific to the data)?
4. FIRST STEP: What is the very first thing they should do in the recommended repo?

Be direct. Pick one winner. Ground everything in the actual data above."""


# ── UI ──────────────────────────────────────────────────────────────────────

st.title("🔍 ContribLens")
st.markdown("Turn intimidating repositories into beginner-friendly contribution journeys.")
st.caption("All recommendations grounded in actual repository data — powered by Nemotron 3 Super.")
st.divider()

tab_contributor, tab_maintainer, tab_compare = st.tabs([
    "🧑‍💻 Contributor Mode",
    "🛠️ Maintainer Mode",
    "⚖️ Compare Repos"
])


# ── TAB 1: CONTRIBUTOR MODE ─────────────────────────────────────────────────

with tab_contributor:

    col1, col2 = st.columns([3, 1])

    with col1:
        repoInput = st.text_input(
            "GitHub repository to analyze",
            "HydPy/meetup-nvidia-nemotron-3-super",
            placeholder="owner/repository-name",
            key="contributor_repo"
        )

    with col2:
        st.write("")
        st.write("")
        analyzeBtn = st.button("Analyze Repo", type="primary", use_container_width=True, key="analyze_contributor")

    inner1, inner2, inner3, inner4 = st.tabs(["📊 Overview", "🧭 AI Mentor", "🐛 Issues + Draft PR", "🚶 Journey Simulation"])

    if analyzeBtn or "files" in st.session_state:

        if analyzeBtn:
            with st.spinner("Fetching repository data..."):
                try:
                    repo = github.get_repo(repoInput)
                except Exception as e:
                    st.error(f"Could not find repository: {repoInput}. Check the name and try again.")
                    st.stop()

                files = getFiles(repoInput)
                readme = getReadme(repoInput)
                issues = getIssues(repoInput)
                issueCount = len(issues)
                score, reasons, missing = scoreRepo(files, issueCount)
                advice, complexity = mentorAdvice(files, issueCount)

                st.session_state["repoInput"] = repoInput
                st.session_state["files"] = files
                st.session_state["readme"] = readme
                st.session_state["issues"] = issues
                st.session_state["issueCount"] = issueCount
                st.session_state["score"] = score
                st.session_state["reasons"] = reasons
                st.session_state["missing"] = missing
                st.session_state["advice"] = advice
                st.session_state["complexity"] = complexity

        else:
            repoInput = st.session_state["repoInput"]
            files = st.session_state["files"]
            readme = st.session_state["readme"]
            issues = st.session_state["issues"]
            issueCount = st.session_state["issueCount"]
            score = st.session_state["score"]
            reasons = st.session_state["reasons"]
            missing = st.session_state["missing"]
            advice = st.session_state["advice"]
            complexity = st.session_state["complexity"]
            repo = github.get_repo(repoInput)

        with inner1:
            st.subheader(repo.full_name)

            if repo.description:
                st.write(repo.description)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("⭐ Stars", repo.stargazers_count)
            c2.metric("🍴 Forks", repo.forks_count)
            c3.metric("👁 Watchers", repo.subscribers_count)
            c4.metric("🐛 Open Issues", issueCount)

            st.divider()
            st.subheader("Contributor Friendliness Score")
            st.progress(min(score, 100) / 100)
            st.metric("Score", f"{score}/100")

            if score >= 80:
                st.success("🟢 Beginner Friendly — strong documentation and active issues")
            elif score >= 60:
                st.warning("🟡 Intermediate — some onboarding material present")
            elif score >= 40:
                st.warning("🟠 Moderate — limited onboarding, will take effort to get started")
            else:
                st.error("🔴 Advanced — minimal onboarding documentation found")

            col_a, col_b = st.columns(2)

            with col_a:
                st.write("**Found:**")
                for r in reasons:
                    st.write(f"✓ {r}")
                if not reasons:
                    st.write("Nothing detected.")

            with col_b:
                st.write("**Missing:**")
                for m in missing:
                    st.write(f"✗ {m}")
                if not missing:
                    st.write("All clear!")

            st.divider()
            st.subheader("Root Files")
            st.write(files)

        with inner2:
            st.subheader("Contributor Guidance")

            for item in advice:
                st.info(item)

            st.divider()
            st.subheader("🤖 Nemotron AI Mentor")
            st.caption("nvidia/llama-3.3-nemotron-super-49b-v1 · 120B hybrid Mamba-Transformer MoE · reasoning over actual repo data")

            if nemotronKey:
                with st.spinner("Nemotron is reasoning over repository data..."):
                    sysPrompt = "You are an open source contribution mentor. Ground every recommendation strictly in the repository data provided. Never reference files not in the list. If something is missing, say it is missing."
                    userPrompt = buildMentorPrompt(repoInput, files, readme, issueCount, score, reasons, missing, complexity)
                    mentorResponse, mentorError = callNemotron(sysPrompt, userPrompt)

                if mentorResponse:
                    st.success(mentorResponse)
                    with st.expander("What data was Nemotron given?"):
                        st.write(f"**Repo:** {repoInput}")
                        st.write(f"**Files passed:** {', '.join(files[:20])}")
                        st.write(f"**Score breakdown:** {reasons}")
                        st.write(f"**Missing items:** {missing}")
                        st.write(f"**README chars:** {len(readme)}")
                        st.write(f"**Issues count:** {issueCount}")
                        st.caption("Nemotron's response is grounded in this data only.")
                else:
                    st.error(f"Nemotron error: {mentorError}")
            else:
                st.warning("Add NVIDIA_API_KEY to your .env file to unlock AI mentor guidance.")

        with inner3:
            st.subheader("Contribution Opportunities")

            if not issues:
                st.info("No open issues. Try improving docs or setup instructions as a first contribution.")
            else:
                easy = [i for i in issues if difficultyLevel(i)[0] == "Easy"]
                medium = [i for i in issues if difficultyLevel(i)[0] == "Medium"]
                hard = [i for i in issues if difficultyLevel(i)[0] == "Hard"]

                c1, c2, c3 = st.columns(3)
                c1.metric("🟢 Easy", len(easy))
                c2.metric("🟡 Medium", len(medium))
                c3.metric("🔴 Hard", len(hard))

                st.caption("Start with Easy issues if you are new to this repo.")
                st.divider()

            shown = 0

            for issue in issues:
                level, evidence, confidence = difficultyLevel(issue)
                evidenceText = " · ".join(evidence)
                warningNote = ""

                if confidence == "Low":
                    warningNote = "\n\n⚠️ Low confidence — no labels. Check carefully before starting."

                content = f"""**#{issue['number']} — {issue['title']}**

Difficulty: {level} · Confidence: {confidence}

Evidence: {evidenceText}{warningNote}

[View on GitHub]({issue['url']})"""

                if level == "Easy":
                    st.success(content)
                elif level == "Hard":
                    st.error(content)
                else:
                    st.warning(content)

                if nemotronKey:
                    if st.button(f"✍️ Draft my first comment for #{issue['number']}", key=f"draft_{issue['number']}"):
                        with st.spinner("Nemotron is drafting your comment..."):
                            draftSys = "You help beginner open source contributors write their first GitHub comments. Sound human, friendly, and concise. No corporate language."
                            draftUser = buildPRDraftPrompt(repoInput, issue, files, readme)
                            draftResponse, draftError = callNemotron(draftSys, draftUser, maxTokens=300)

                        if draftResponse:
                            st.code(draftResponse, language=None)
                            st.caption("AI generated draft. Review before posting.")
                        else:
                            st.error(f"Draft error: {draftError}")

                shown += 1
                if shown >= 5:
                    break

        with inner4:
            st.subheader("🚶 Contributor Journey Simulation")

            friction = 0
            if "README.md" not in files:
                friction += 50
            if "CONTRIBUTING.md" not in files:
                friction += 30
            if "docs" not in files:
                friction += 20
            if len(issues) == 0:
                friction += 15
            friction = min(friction, 100)

            fc1, fc2 = st.columns(2)
            fc1.metric("Contributor Friction Score", f"{friction}/100")
            if friction >= 70:
                fc2.error("🔴 High friction — new contributors will struggle")
            elif friction >= 40:
                fc2.warning("🟡 Medium friction — some barriers exist")
            else:
                fc2.success("🟢 Low friction — fairly easy to get started")

            st.write("See exactly what a brand new contributor experiences when they arrive at this repo — step by step.")
            st.caption("Powered by Nemotron 3 Super reasoning over actual repository structure.")

            if not nemotronKey:
                st.warning("Add NVIDIA_API_KEY to your .env file to run the journey simulation.")
            else:
                if st.button("▶ Simulate Contributor Journey", type="primary", key="journey_btn"):
                    with st.spinner("Nemotron is simulating the contributor journey..."):
                        journeySys = "You simulate the realistic step-by-step experience of a new open source contributor. Be honest about friction and blockers. Ground every step in actual repository data provided."
                        journeyUser = buildJourneyPrompt(repoInput, files, readme, issues, score, reasons, missing)
                        journeyResponse, journeyError = callNemotron(journeySys, journeyUser, maxTokens=700)

                    if journeyResponse:
                        st.info(journeyResponse)

                        with st.expander("What data was Nemotron given for this simulation?"):
                            st.write(f"**Repo:** {repoInput}")
                            st.write(f"**Files:** {', '.join(files[:20])}")
                            st.write(f"**README exists:** {'README.md' in files}")
                            st.write(f"**CONTRIBUTING.md exists:** {'CONTRIBUTING.md' in files}")
                            st.write(f"**Issues:** {len(issues)} total")
                            st.write(f"**Score:** {score}/100")
                            st.write(f"**Missing:** {missing}")
                            st.caption("Every step in the simulation is grounded in this data.")
                    else:
                        st.error(f"Journey simulation error: {journeyError}")


# ── TAB 2: MAINTAINER MODE ──────────────────────────────────────────────────

with tab_maintainer:

    st.subheader("🛠️ Maintainer Health Report")
    st.write("You maintain a repository. Get an honest report on what's stopping new contributors — and what to fix first.")

    col1, col2 = st.columns([3, 1])

    with col1:
        maintainerRepo = st.text_input(
            "Your repository",
            placeholder="owner/your-repository-name",
            key="maintainer_repo"
        )

    with col2:
        st.write("")
        st.write("")
        maintainerBtn = st.button("Get Health Report", type="primary", use_container_width=True, key="analyze_maintainer")

    if maintainerBtn and maintainerRepo:

        with st.spinner("Analyzing your repository from a contributor's perspective..."):
            try:
                mRepo = github.get_repo(maintainerRepo)
            except Exception as e:
                st.error(f"Could not find repository: {maintainerRepo}")
                st.stop()

            mFiles = getFiles(maintainerRepo)
            mReadme = getReadme(maintainerRepo)
            mIssues = getIssues(maintainerRepo)
            mIssueCount = len(mIssues)
            mScore, mReasons, mMissing = scoreRepo(mFiles, mIssueCount)

        st.subheader(f"Health Report: {mRepo.full_name}")

        col_score, col_lang = st.columns(2)
        col_score.metric("Contributor Friendliness", f"{mScore}/100")
        col_lang.metric("Primary Language", mRepo.language or "Not specified")

        if mScore >= 80:
            st.success("🟢 Your repo is beginner friendly")
        elif mScore >= 60:
            st.warning("🟡 Your repo has room to improve onboarding")
        else:
            st.error("🔴 New contributors will struggle with this repo")

        col_a, col_b = st.columns(2)

        with col_a:
            st.write("**What you have:**")
            for r in mReasons:
                st.write(f"✓ {r}")

        with col_b:
            st.write("**What's missing:**")
            for m in mMissing:
                st.write(f"✗ {m}")

        st.divider()

        if nemotronKey:
            st.subheader("🤖 Nemotron Maintainer Recommendations")
            st.caption("Nemotron 3 Super analyzing your repo from a new contributor's perspective")

            with st.spinner("Nemotron is preparing your maintainer report..."):
                maintSys = "You are an open source community advisor. Be direct and honest. Give actionable advice grounded strictly in the repository data provided."
                maintUser = buildMaintainerPrompt(maintainerRepo, mFiles, mReadme, mIssues, mScore, mReasons, mMissing)
                maintResponse, maintError = callNemotron(maintSys, maintUser, maxTokens=800)

            if maintResponse:
                st.info(maintResponse)
                with st.expander("What data was Nemotron given?"):
                    st.write(f"**Repo:** {maintainerRepo}")
                    st.write(f"**Files:** {', '.join(mFiles[:20])}")
                    st.write(f"**Issues sample:** {[i['title'] for i in mIssues[:5]]}")
                    st.write(f"**Score:** {mScore}/100")
            else:
                st.error(f"Nemotron error: {maintError}")
        else:
            st.warning("Add NVIDIA_API_KEY to your .env file to unlock the maintainer health report.")

    elif maintainerBtn and not maintainerRepo:
        st.warning("Please enter a repository name.")


# ── TAB 3: COMPARE REPOS ───────────────────────────────────────────────────

with tab_compare:

    st.subheader("⚖️ Compare Two Repositories")
    st.write("Not sure which repo to contribute to? Compare two and get a clear recommendation.")

    col1, col2 = st.columns(2)

    with col1:
        repo1Input = st.text_input(
            "First repository",
            placeholder="owner/repo-one",
            key="compare_repo1"
        )

    with col2:
        repo2Input = st.text_input(
            "Second repository",
            placeholder="owner/repo-two",
            key="compare_repo2"
        )

    compareBtn = st.button("Compare", type="primary", key="compare_btn")

    if compareBtn and repo1Input and repo2Input:

        with st.spinner("Fetching both repositories..."):
            try:
                r1 = github.get_repo(repo1Input)
                r2 = github.get_repo(repo2Input)
            except Exception as e:
                st.error(f"Could not fetch one of the repositories. Check both names.")
                st.stop()

            files1 = getFiles(repo1Input)
            files2 = getFiles(repo2Input)
            readme1 = getReadme(repo1Input)
            readme2 = getReadme(repo2Input)
            issues1 = getIssues(repo1Input)
            issues2 = getIssues(repo2Input)
            score1, reasons1, missing1 = scoreRepo(files1, len(issues1))
            score2, reasons2, missing2 = scoreRepo(files2, len(issues2))

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader(r1.full_name)
            st.metric("Friendliness Score", f"{score1}/100")
            st.metric("Open Issues", len(issues1))
            st.progress(min(score1, 100) / 100)
            for r in reasons1:
                st.write(f"✓ {r}")
            for m in missing1:
                st.write(f"✗ {m}")

        with col_b:
            st.subheader(r2.full_name)
            st.metric("Friendliness Score", f"{score2}/100")
            st.metric("Open Issues", len(issues2))
            st.progress(min(score2, 100) / 100)
            for r in reasons2:
                st.write(f"✓ {r}")
            for m in missing2:
                st.write(f"✗ {m}")

        st.divider()

        if nemotronKey:
            st.subheader("🤖 Nemotron Recommendation")

            with st.spinner("Nemotron is comparing both repositories..."):
                compSys = "You help beginner open source contributors pick the right repository. Be direct. Pick one winner. Ground everything in actual data."
                compUser = buildComparePrompt(repo1Input, repo2Input, files1, files2, score1, score2, issues1, issues2, readme1, readme2)
                compResponse, compError = callNemotron(compSys, compUser, maxTokens=500)

            if compResponse:
                st.success(compResponse)
            else:
                st.error(f"Nemotron error: {compError}")
        else:
            st.warning("Add NVIDIA_API_KEY to your .env to get AI comparison.")

    elif compareBtn:
        st.warning("Please enter both repository names.")