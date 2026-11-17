"""视频封面抽帧模块 cover.py：二进制探测、命令拼装、输出类型校验（不依赖真实 ffmpeg）。"""
import subprocess

import app.media.cover as cover_mod


def _reset_cache():
    cover_mod._bin = None
    cover_mod._bin_resolved = False


def test_find_ffmpeg_env_override(monkeypatch, tmp_path):
    """FFMPEG_BIN 指向存在的可执行文件时优先使用。"""
    _reset_cache()
    exe = tmp_path / "ffmpeg"
    exe.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setenv("FFMPEG_BIN", str(exe))
    assert cover_mod.find_ffmpeg() == str(exe)


def test_find_ffmpeg_none_when_unavailable(monkeypatch):
    """env / imageio 包 / PATH 都找不到时返回 None（封面任务据此静默跳过）。"""
    _reset_cache()
    monkeypatch.setenv("FFMPEG_BIN", "")
    monkeypatch.setattr(cover_mod.shutil, "which", lambda _name: None)
    # 模拟 imageio_ffmpeg 未安装
    monkeypatch.setitem(__import__("sys").modules, "imageio_ffmpeg", None)
    assert cover_mod.find_ffmpeg() is None


def test_extract_cover_returns_none_without_binary():
    _reset_cache()
    cover_mod._bin = None
    cover_mod._bin_resolved = True
    assert cover_mod.extract_cover(b"not-a-video") is None


def test_run_ffmpeg_builds_command_and_accepts_jpeg(monkeypatch):
    """命令行参数包含 seek / 单帧 / 缩放 / 质量；JPEG magic 开头即认可输出。"""
    captured = {}
    jpeg = b"\xff\xd8\xff\xe0" + b"K" * 64

    class _Proc:
        returncode = 0
        stdout = jpeg
        stderr = b""

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(subprocess, "run", _run)
    out = cover_mod._run_ffmpeg("/bin/ffmpeg", "src.mp4", 0.3, 400, 5)
    assert out == jpeg
    cmd = captured["cmd"]
    assert "-ss" in cmd and "0.30" in cmd
    assert "-frames:v" in cmd and "1" in cmd
    assert "-vf" in cmd and "scale=400:-2" in cmd
    assert "-q:v" in cmd and "5" in cmd


def test_run_ffmpeg_rejects_non_jpeg(monkeypatch):
    """输出不是 JPEG（如错误页 / PNG）时丢弃，不写成封面对象。"""
    class _Proc:
        returncode = 0
        stdout = b"\x89PNG\r\n\x1a\n" + b"0" * 32
        stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc())
    assert cover_mod._run_ffmpeg("/bin/ffmpeg", "src.mp4", 0.3, 400, 5) is None


def test_run_ffmpeg_returns_none_on_nonzero_exit(monkeypatch):
    class _Proc:
        returncode = 1
        stdout = b""
        stderr = b"something broke"

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc())
    assert cover_mod._run_ffmpeg("/bin/ffmpeg", "src.mp4", 0.3, 400, 5) is None
