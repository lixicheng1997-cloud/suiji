"""ID 生成：与客户端 genId 同风格（时间戳 base36 + 随机 6 位 base36）。"""
import random
import time

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36(n: int) -> str:
    if n == 0:
        return "0"
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = _ALPHABET[r] + s
    return s


def gen_id(prefix: str = "") -> str:
    t = _base36(int(time.time() * 1000))
    rand = "".join(random.choice(_ALPHABET) for _ in range(6))
    return (prefix + "_" if prefix else "") + t + rand
