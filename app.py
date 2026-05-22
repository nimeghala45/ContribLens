import streamlit as st
from github import Github
from github import Auth
from dotenv import load_dotenv
import os

load_dotenv()

githubToken = os.getenv(
"GITHUB_TOKEN"
)

auth = Auth.Token(
githubToken
)

github = Github(
auth=auth,
per_page=10
)

st.set_page_config(
page_title="ContribLens",
layout="wide"
)


def getFiles(repo):

    files=[]

    try:

        contents=repo.get_contents("")

        for item in contents:

            files.append(
            item.name
            )

    except:

        pass

    return files


def getReadme(repo):

    text=""

    try:

        readme=repo.get_readme()

        text=(
        readme
        .decoded_content
        .decode(
        errors="ignore"
        )
        )

    except:

        pass

    return text


def getIssueCount(repo):

    count=0

    issues=[]

    try:

        repoIssues=repo.get_issues(
        state="open"
        )

        for issue in repoIssues:

            if issue.pull_request:

                continue

            count+=1

            issues.append(
            issue
            )

    except:

        pass

    return count,issues


def scoreRepo(
files,
issueCount
):

    score=0

    reasons=[]

    if "README.md" in files:

        score+=25

        reasons.append(
        "README exists"
        )

    if "CONTRIBUTING.md" in files:

        score+=25

        reasons.append(
        "Contribution guide exists"
        )

    if ".github" in files:

        score+=20

        reasons.append(
        "GitHub workflows exist"
        )

    if "docs" in files:

        score+=15

        reasons.append(
        "Documentation available"
        )

    if issueCount>0:

        score+=15

        reasons.append(
        "Open issues available"
        )

    return score,reasons


def mentorAdvice(
files,
issueCount
):

    mentor=[]

    complexity="Small"

    if len(files)>15:

        complexity="Large"

    elif len(files)>8:

        complexity="Medium"

    mentor.append(
    f"Repository complexity: {complexity}"
    )

    if "README.md" in files:

        mentor.append(
        "Read README first"
        )

    if "CONTRIBUTING.md" in files:

        mentor.append(
        "Read contribution guide"
        )

    if "docs" in files:

        mentor.append(
        "Explore documentation"
        )

    if issueCount==0:

        mentor.append(
        "Look for documentation improvements"
        )

    return mentor


def difficultyLevel(
issue
):

    difficulty="Medium"

    labels=[]

    try:

        for label in issue.labels:

            labels.append(
            label.name.lower()
            )

    except:

        pass

    if (
    "good first issue"
    in labels
    ):

        difficulty="Easy"

    elif (
    "bug"
    in labels
    ):

        difficulty="Medium"

    if len(
    issue.body or ""
    )>1500:

        difficulty="Hard"

    return difficulty


st.title(
"ContribLens"
)

st.markdown(
"""
Turn intimidating repositories into contributor friendly journeys.
"""
)

st.caption(
"Recommendations are guidance only. Review repository documentation before contributing."
)

repoInput=st.text_input(
"Enter GitHub Repo",
"HydPy/meetup-nvidia-nemotron-3-super"
)

tab1,tab2,tab3=st.tabs(
[
"Overview",
"Mentor",
"Issues"
]
)

if st.button(
"Analyze Repo"
):

    repo=github.get_repo(
    repoInput
    )

    files=getFiles(
    repo
    )

    readme=getReadme(
    repo
    )

    issueCount,issues=(
    getIssueCount(
    repo
    )
    )

    score,reasons=(
    scoreRepo(
    files,
    issueCount
    )
    )

    mentor=mentorAdvice(
    files,
    issueCount
    )

    with tab1:

        c1,c2,c3,c4=st.columns(4)

        c1.metric(
        "Stars",
        repo.stargazers_count
        )

        c2.metric(
        "Forks",
        repo.forks_count
        )

        c3.metric(
        "Watchers",
        repo.subscribers_count
        )

        c4.metric(
        "Issues",
        issueCount
        )

        st.progress(
        score/100
        )

        st.metric(
        "Friendliness",
        f"{score}/100"
        )
        if score>=80:

            st.success(
            "🟢 Beginner Friendly"
            )

        elif score>=60:

            st.warning(
            "🟡 Intermediate"
            )

        else:

            st.error(
            "🔴 Advanced Repository"
            )

        for reason in reasons:

            st.write(
            f"✓ {reason}"
            )

        st.subheader(
        "Files"
        )

        st.write(
        files
        )

    with tab2:

        for item in mentor:

            st.info(
            item
            )

    with tab3:

        shown=0

        for issue in issues:

            level=(
            difficultyLevel(
            issue
            )
            )

            st.info(
f"""
{issue.title}

Difficulty:
{level}
"""
)

            shown+=1

            if shown>=5:

                break

        if shown==0:

            st.info(
"No issues found"
)