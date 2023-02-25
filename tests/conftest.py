import os
import unittest

import pytest
import tests.subprocess_mock  # pylint: disable=unused-import
import tests.docker_mock  # pylint: disable=unused-import
from tests.requests_mock import add_gitea_mocks, add_github_mocks, Mock

from jaypore_ci import jci, executors, remotes, reporters, repos


def idfn(x):
    name = []
    for _, item in sorted(x.items()):
        what, _, cls = str(item).replace(">", "").split(".")[-3:]
        name.append(".".join([what, cls]))
    return str(name)


def factory(*, repo, remote, executor, reporter):
    "Return a new pipeline every time the builder function is called"

    def build():
        r = repo.from_env()
        return jci.Pipeline(
            poll_interval=0,
            repo=r,
            remote=remote.from_env(repo=r),
            executor=executor(),
            reporter=reporter(),
        )

    return build


@pytest.fixture(
    scope="function",
    params=list(
        jci.Pipeline.env_matrix(
            reporter=[reporters.Text, reporters.Markdown],
            remote=[
                remotes.Mock,
                remotes.Email,
                remotes.GitRemote,
                remotes.Gitea,
                remotes.Github,
            ],
            repo=[repos.Git],
            executor=[executors.Docker],
        )
    ),
    ids=idfn,
)
def pipeline(request):
    os.environ["JAYPORE_GITEA_TOKEN"] = "fake_gitea_token"
    os.environ["JAYPORE_GITHUB_TOKEN"] = "fake_github_token"
    os.environ["JAYPORE_EMAIL_ADDR"] = "fake@email.com"
    os.environ["JAYPORE_EMAIL_PASSWORD"] = "fake_email_password"
    os.environ["JAYPORE_EMAIL_TO"] = "fake.to@mymailmail.com"
    builder = factory(
        repo=request.param["repo"],
        remote=request.param["remote"],
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
