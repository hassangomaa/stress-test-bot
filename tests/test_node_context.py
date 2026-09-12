import os

from stressbot.node_context import get_node_context, init_node_context


def test_node_context_from_env(monkeypatch):
    get_node_context.cache_clear()
    monkeypatch.setenv("STRESSBOT_NODE_ID", "slt-ocr")
    monkeypatch.setenv("STRESSBOT_EGRESS_IP", "69.62.114.63")
    monkeypatch.setenv("STRESSBOT_PROXY_URL", "http://127.0.0.1:8080")
    ctx = init_node_context()
    assert ctx.node_id == "slt-ocr"
    assert ctx.egress_ip == "69.62.114.63"
    assert ctx.proxy_url == "http://127.0.0.1:8080"
