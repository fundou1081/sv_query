# Fixtures for integration tests
import pytest
import os

@pytest.fixture
def output_dir(tmp_path):
    """Provide output directory for integration tests"""
    return str(tmp_path)

@pytest.fixture
def project():
    """Dummy project fixture - returns a minimal project dict"""
    return {'name': 'test', 'description': 'test project', 'path': '/tmp'}
