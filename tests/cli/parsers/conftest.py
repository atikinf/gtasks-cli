"""Fixtures shared by the command (parser and handler) tests."""

import argparse
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import Mock

import pytest

from gtasks.cli.cli import build_parser
from gtasks.utils.config import Config, ConfigKey


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """A Config backed by a temp file."""
    return Config(tmp_path / "config.ini", ConfigParser())


@pytest.fixture
def active_config(config: Config) -> Config:
    """A config whose active list is Work (`list1`)."""
    config.set(ConfigKey.ACTIVE_TASKLIST_ID, "list1")
    config.set(ConfigKey.ACTIVE_TASKLIST_TITLE, "Work")
    return config


@pytest.fixture
def mock_client() -> Mock:
    """A mocked API client whose reads are always live (never from a cache)."""
    client = Mock()
    client.tasks_cache_state.return_value = None
    client.tasklists_cache_state.return_value = None
    return client


@pytest.fixture
def parser() -> argparse.ArgumentParser:
    """A fully-built argument parser."""
    return build_parser()
