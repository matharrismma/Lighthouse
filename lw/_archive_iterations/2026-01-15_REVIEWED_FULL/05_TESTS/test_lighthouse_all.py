import tempfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '04_CODE'))

import lighthouse_all as mod  # noqa: E402


def test_lsp_deterministic():
    text = "In the beginning God created the heavens and the earth.\n" * 10
    cfg = mod.LSPConfig(words_per_page=20)
    lsp1 = mod.build_lsp(text, cfg, source_id="test")
    lsp2 = mod.build_lsp(text, cfg, source_id="test")
    assert lsp1['pages'][0]['sha256'] == lsp2['pages'][0]['sha256']
    assert lsp1['document_sha256'] == lsp2['document_sha256']


def test_packet_sign_verify():
    priv_b64u, pub_b64u = mod.ed25519_generate_keypair()
    packet = mod.example_investment_packet(issuer_pubkey_b64u=pub_b64u, subject_pubkey_b64u=pub_b64u)
    signed = mod.packet_sign(packet, priv_b64u)
    ok, msg = mod.packet_verify(signed)
    assert ok, msg


def test_manifest_generation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / 'a.txt').write_text('hello', encoding='utf-8')
        (root / 'b.txt').write_text('world', encoding='utf-8')
        out = root / 'MANIFEST.json'
        m = mod.build_manifest(root, out)
        assert 'files' in m
        assert len(m['files']) == 2
