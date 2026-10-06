import os
from unittest.mock import Mock, patch

import pytest

from sentinelseo.wp.client import WPClient, WPConflictError
from sentinelseo.wp.fixes import WPFixer


@patch("sentinelseo.wp.client.httpx.Client")
@patch("sentinelseo.wp.client.Fernet")
def test_detect_seo_plugins_conflict(mock_fernet, mock_client):
    # Mock Fernet
    mock_f_instance = Mock()
    mock_f_instance.decrypt.return_value = b"decrypted"
    mock_fernet.return_value = mock_f_instance

    os.environ["SCRAWLY_ENCRYPTION_KEY"] = "some_key_here"

    client = WPClient("http://localhost", "user", "enc_pass")

    # Mock httpx response for plugins
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"plugin": "wordpress-seo/wp-seo.php"},
        {"plugin": "seo-by-rank-math/rank-math.php"},
    ]
    client.client.get.return_value = mock_resp

    with pytest.raises(WPConflictError) as excinfo:
        client.detect_seo_plugins()

    assert "Both Yoast and RankMath are active" in str(excinfo.value)


@patch("sentinelseo.wp.client.httpx.Client")
@patch("sentinelseo.wp.client.Fernet")
def test_apply_fix_idempotent(mock_fernet, mock_client):
    mock_f_instance = Mock()
    mock_f_instance.decrypt.return_value = b"decrypted"
    mock_fernet.return_value = mock_f_instance
    os.environ["SCRAWLY_ENCRYPTION_KEY"] = "some_key_here"

    client = WPClient("http://localhost", "user", "enc_pass")

    # Setup mock to return yoast
    client._active_seo_plugin = "yoast"
    fixer = WPFixer(client)

    # First call: target state matches desired state
    mock_post_resp = Mock()
    mock_post_resp.status_code = 200
    mock_post_resp.json.return_value = {"meta": {"_yoast_wpseo_title": "Desired Title"}}
    client.client.get.return_value = mock_post_resp

    token1 = fixer.apply_meta_fix(1, "title", "Desired Title")
    assert token1["action"] == "none_idempotent"
    assert token1["before_val"] == "Desired Title"
    assert not client.client.post.called
