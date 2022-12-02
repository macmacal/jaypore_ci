import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests
from jaypore_ci.interfaces import Remote
from jaypore_ci.logging import logger


class Gitea(Remote):  # pylint: disable=too-many-instance-attributes
    @classmethod
    def from_env(cls):
        remote = (
            subprocess.check_output(
                "git remote -v | grep push | awk '{print $2}'", shell=True
            )
            .decode()
            .strip()
        )
        assert "https://" in remote, "Only https remotes supported"
        assert ".git" in remote
        remote = urlparse(remote)
        branch = (
            subprocess.check_output(
                r"git branch | grep \* | awk '{print $2}'", shell=True
            )
            .decode()
            .strip()
        )
        sha = subprocess.check_output("git rev-parse HEAD", shell=True).decode().strip()
        owner = Path(remote.path).parts[1]
        repo = Path(remote.path).parts[2].replace(".git", "")
        token = os.environ["JAYPORE_GITEA_TOKEN"]
        return cls(
            root=f"{remote.scheme}://{remote.netloc}",
            owner=owner,
            repo=repo,
            branch=branch,
            token=token,
            sha=sha,
        )

    def __init__(
        self, root, owner, repo, token, branch, sha
    ):  # pylint: disable=too-many-arguments

        self.root = root
        self.api = f"{root}/api/v1"
        self.owner = owner
        self.repo = repo
        self.token = token
        self.branch = branch
        self.sha = sha
        self.timeout = 10

    def logging(self):
        return logger.bind(
            root=self.root, owner=self.owner, repo=self.repo, branch=self.branch
        )

    def get_pr_id(self):
        r = requests.post(
            f"{self.api}/repos/{self.owner}/{self.repo}/pulls",
            params={"access_token": self.token},
            timeout=self.timeout,
            json={
                "base": "main",
                "body": "Branch auto created by JayporeCI",
                "head": self.branch,
                "title": self.branch,
            },
        )
        self.logging().debug("Get PR Id", status_code=r.status_code)
        if r.status_code == 409:
            return r.text.split("issue_id:")[1].split(",")[0].strip()
        if r.status_code == 201:
            return self.get_pr_id()
        raise Exception(r)

    def publish(self, report: str, status: str):
        """
        report: Report to write to remote.
        status: One of ["pending", "success", "error", "failure", "warning"]
        """
        assert status in ("pending", "success", "error", "failure", "warning")
        issue_id = self.get_pr_id()
        # Get existing PR body
        r = requests.get(
            f"{self.api}/repos/{self.owner}/{self.repo}/pulls/{issue_id}",
            timeout=self.timeout,
            params={"access_token": self.token},
        )
        self.logging().debug("Get existing body", status_code=r.status_code)
        assert r.status_code == 200
        body = r.json()["body"]
        body = (line for line in body.split("\n"))
        prefix = []
        for line in body:
            if "<summary>JayporeCi" in line:
                prefix = prefix[:-1]
                break
            prefix.append(line)
        while prefix and prefix[-1].strip() == "":
            prefix = prefix[:-1]
        prefix.append("")
        # Post new body with report
        report = "\n".join(prefix) + "\n" + report
        r = requests.patch(
            f"{self.api}/repos/{self.owner}/{self.repo}/pulls/{issue_id}",
            data={"body": report},
            timeout=self.timeout,
            params={"access_token": self.token},
        )
        self.logging().debug("Published new report", status_code=r.status_code)
        # Set commit status
        r = requests.post(
            f"{self.api}/repos/{self.owner}/{self.repo}/statuses/{self.sha}",
            json={
                "context": "JayporeCi",
                "description": f"Pipeline status is: {status}",
                "state": status,
                "target_url": f"{self.root}/{self.owner}/{self.repo}/pulls/{issue_id}",
            },
            timeout=self.timeout,
            params={"access_token": self.token},
        )
        self.logging().debug(
            "Published new status", status=status, status_code=r.status_code
        )
