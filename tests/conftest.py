import os
from pathlib import Path
import unittest

import pytest
import tests.subprocess_mock  # pylint: disable=unused-import
import tests.docker_mock  # pylint: disable=unused-import
from tests.requests_mock import add_gitea_mocks, add_github_mocks, Mock
import tests.jayporeci_patch  # pylint: disable=unused-import

from jaypore_ci import jci, executors, remotes, reporters, repos

from typing import Callable
from jaypore_ci.interfaces import Repo, Remote, Executor, Reporter


def idfn(x):
    name = []
    for _, item in sorted(x.items()):
        what, _, cls = str(item).replace(">", "").split(".")[-3:]
        name.append(".".join([what, cls]))
    return str(name)


def factory(
    *,
    repo: Repo,
    remote: Remote,
    remote_url: str,
    executor: Executor,
    reporter: Reporter
) -> Callable:
    "Return a new pipeline every time the builder function is called"

    repo._get_remote_url = lambda: remote_url

    def build() -> jci.Pipeline:
        r = repo.from_env()
        return jci.Pipeline(
            poll_interval=0,
            repo=r,
            remote=remote.from_env(repo=r),
            executor=executor(),
            reporter=reporter(),
        )

    return build


def set_env_keys():
    os.environ["JAYPORE_GITEA_TOKEN"] = "fake_gitea_token"
    os.environ["JAYPORE_GITHUB_TOKEN"] = "fake_github_token"
    os.environ["JAYPORE_EMAIL_ADDR"] = "fake@email.com"
    os.environ["JAYPORE_EMAIL_PASSWORD"] = "fake_email_password"
    os.environ["JAYPORE_EMAIL_TO"] = "fake.to@mymailmail.com"


@pytest.fixture(
    scope="function",
    params=list(
        jci.Pipeline.env_matrix(
            executor=[executors.Docker],
            reporter=[reporters.Text, reporters.Markdown],
            remote=[
                remotes.Mock,
                remotes.Email,
                remotes.GitRemote,
                remotes.Gitea,
                remotes.Github,
            ],
            remote_url=[
                "https://fake_remote.com/fake_owner/fake_repo.git",
                "user@fake_remote.com:fake_owner/fake_repo.git",
            ],
            repo=[repos.Git],
        )
    ),
    ids=idfn,
)
def pipeline(request):
    set_env_keys()
    builder = factory(
        repo=request.param["repo"],
        remote=request.param["remote"],
        remote_url=request.param["remote_url"],
        executor=request.param["executor"],
        reporter=request.param["reporter"],
    )
    if request.param["remote"] == remotes.Gitea and not Mock.gitea_added:
        add_gitea_mocks(builder().remote)
    if request.param["remote"] == remotes.Github and not Mock.github_added:
        add_github_mocks(builder().remote)
    if request.param["remote"] == remotes.Email:
        with unittest.mock.patch("smtplib.SMTP_SSL", autospec=True):
            yield builder
    else:
        yield builder


@pytest.fixture(
    scope="function",
    params=list((Path(__name__) / "../docs/source/examples").resolve().glob("*.py")),
    ids=str,
)
def doc_example_filepath(request):
    set_env_keys()
    yield request.param
