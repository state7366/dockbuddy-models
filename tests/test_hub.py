# -*- coding: utf-8 -*-
"""test_hub.py —— 包核心功能测试(不联网, 用 fake COS / 临时目录)。"""
import io
import os
import shutil
import tarfile
import tempfile
import unittest

from dockbuddy_models import CacheStore, Config, ModelHub, Registry, extract_archive, sha256_file
from dockbuddy_models import paths

# 模型数据配置文件(库根 models.json, 由 export_registry.py 生成)
MODELS_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models.json")


class FakeCos:
    """假 COS 客户端: 记录 download, 写 2KB 占位内容。"""
    def __init__(self, content=b"x" * 2048):
        self.downloaded = []
        self.content = content

    def download(self, key, dest, min_bytes=1):
        if os.path.isfile(dest) and os.path.getsize(dest) >= min_bytes:
            return False
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            f.write(self.content)
        self.downloaded.append((key, dest))
        return True


def _make_tar(members: dict) -> bytes:
    """造一个 tar.gz: {arcname: bytes}。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class TestRegistry(unittest.TestCase):
    def test_load_external(self):
        reg = Registry.load(MODELS_JSON)
        self.assertGreaterEqual(len(reg.models), 20)
        self.assertEqual(reg.get("esm2")["status"], "available")
        w = reg.assets("esm2")["weights"]
        self.assertTrue(w[0]["dest"].startswith("esm2/"))
        self.assertFalse(w[0]["dest"].startswith("/home"))

    def test_empty_registry(self):
        reg = Registry.empty()
        self.assertEqual(len(reg.models), 0)

    def test_source_assets(self):
        reg = Registry.load(MODELS_JSON)
        src = reg.assets("saprot")["source"]
        self.assertTrue(src)
        self.assertEqual(src[0]["cos"], "units/src-saprot.tar.gz")
        self.assertEqual(src[0]["extract"]["strip"], 4)

    def test_register_with_assets(self):
        reg = Registry(models={})
        reg.register({"name": "m", "assets": {"weights": [{"cos": "a/b.pt", "dest": "m/b.pt"}]}})
        self.assertIn("m", reg)
        self.assertEqual(reg.assets("m")["weights"][0]["cos"], "a/b.pt")


class TestSources(unittest.TestCase):
    def test_extract_strip(self):
        tmp = tempfile.mkdtemp()
        try:
            tar = _make_tar({
                "home/ubuntu/dockbuddy/repos/SaProt/a.py": b"a",
                "home/ubuntu/dockbuddy/repos/SaProt/sub/b.py": b"b",
            })
            tar_path = os.path.join(tmp, "src.tar.gz")
            with open(tar_path, "wb") as f:
                f.write(tar)
            extract_archive(tar_path, tmp, {"strip": 4, "to": "repos"})
            self.assertTrue(os.path.isfile(os.path.join(tmp, "repos", "SaProt", "a.py")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "repos", "SaProt", "sub", "b.py")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_sha256(self):
        tmp = tempfile.mkdtemp()
        try:
            p = os.path.join(tmp, "f.bin")
            with open(p, "wb") as f:
                f.write(b"hello")
            self.assertEqual(len(sha256_file(p)), 64)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = Config(root=self.tmp).resolve()
        self.reg = Registry(models={})
        self.reg.register({"name": "m", "assets": {
            "weights": [{"cos": "k/a.pt", "dest": "m/a.pt"}],
            "source": [{"cos": "units/src-m.tar.gz", "dest": "M", "extract": {"strip": 4, "to": "repos"}}],
        }})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_idempotent_and_kinds(self):
        from dockbuddy_models.download import Downloader
        fake = FakeCos()
        dl = Downloader(self.cfg, self.reg, cos=fake)
        r = dl.download("m", kinds=["weights"])
        self.assertEqual(r["n_downloaded"], 1)
        r2 = dl.download("m", kinds=["weights"])
        self.assertEqual(r2["n_downloaded"], 0)
        self.assertEqual(r2["n_skipped"], 1)

    def test_lockfile(self):
        from dockbuddy_models.download import Downloader
        dl = Downloader(self.cfg, self.reg, cos=FakeCos())
        dl.download("m", kinds=["weights"])
        lock = dl.lock()
        self.assertIn("files", lock)
        self.assertEqual(len(lock["files"]), 1)

    def test_sha256_verify_fail(self):
        from dockbuddy_models.download import Downloader
        reg = Registry(models={})
        reg.register({"name": "m", "assets": {"weights": [
            {"cos": "k/a.pt", "dest": "m/a.pt", "sha256": "0" * 64}]}})
        dl = Downloader(self.cfg, reg, cos=FakeCos())
        with self.assertRaises(RuntimeError):
            dl.download("m", kinds=["weights"])


class TestHub(unittest.TestCase):
    def test_hub_v3(self):
        tmp = tempfile.mkdtemp()
        try:
            hub = ModelHub(models=MODELS_JSON, root=tmp)
            self.assertGreaterEqual(len(hub.list_models()), 20)
            self.assertEqual(len(hub.available()), 15)
            self.assertTrue(hub.assets("saprot")["source"])
            self.assertTrue(hub.source_path("saprot", "SaProt").startswith(tmp))
            self.assertTrue(hub.weight_path("esm2", "esm2/a.pt").startswith(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_hub_empty_without_models(self):
        tmp = tempfile.mkdtemp()
        try:
            hub = ModelHub(root=tmp)  # 未传 models → 空注册表
            self.assertEqual(len(hub.list_models()), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCli(unittest.TestCase):
    def test_list_and_info(self):
        from dockbuddy_models.__main__ import main
        import contextlib
        import io as _io
        tmp = tempfile.mkdtemp()
        try:
            buf = _io.StringIO()
            with contextlib.redirect_stdout(buf):
                main(["--models", MODELS_JSON, "--root", tmp, "list", "--available"])
            self.assertIn("esm2", buf.getvalue())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
