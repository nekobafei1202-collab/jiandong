"""Download the sherpa-onnx Chinese KWS model and generate keywords.txt.

Output layout under models/kws/ (copied verbatim into app assets/kws/ by
prepare_android_bridge._copy_kws_models):

    encoder.onnx / decoder.onnx / joiner.onnx   (int8, from the -mobile pack)
    tokens.txt
    keywords.txt                                (generated, see KEYWORDS)

Source: https://github.com/k2-fsa/sherpa-onnx/releases/tag/kws-models
Model:  sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01-mobile.tar.bz2

keywords.txt follows the sherpa-onnx format: one keyword per line,
``<token> <token> ... :<boosting_score> #<threshold> @<keyword text>``.
This wenetspeech KWS model tokenizes speech as tone-marked pinyin
syllables (initial + final), so KEYWORDS below spells every command in
pinyin tokens, each validated against tokens.txt at generation time.
"""

from __future__ import annotations

import socket
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# urlretrieve has no timeout; keep slow/blocked endpoints from hanging forever.
socket.setdefaulttimeout(60)

_URLS = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/"
    "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01-mobile.tar.bz2",
)

# ModelScope mirror of the same pack (CN fallback) — individual files.
_MS_BASE = (
    "https://modelscope.cn/api/v1/models/pkufool/"
    "sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01/repo?FilePath="
)
_MS_FILES = {
    "encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx": "encoder.onnx",
    "decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx": "decoder.onnx",
    "joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx": "joiner.onnx",
    "tokens.txt": "tokens.txt",
}

# 口令 → (sherpa tokens 序列, threshold, boosting_score)。
# 该模型 tokens 是带声调拼音（声母/韵母分词），每词逐 token 对 tokens.txt 校验。
# 训练口令全部 4 字以上抗误触发；选课短口令阈值略高、boost 略低。
KEYWORDS: dict[str, tuple[str, float, float]] = {
    # AI 助手唤醒/退出
    "小健小健": ("x iǎo j iàn x iǎo j iàn", 0.22, 1.8),
    "退出助手": ("t uì ch ū zh ù sh ǒu", 0.22, 1.6),
    # 登录页
    "登录": ("d ēng l ù", 0.30, 1.3),
    # 训练阶段
    "开始训练": ("k āi sh ǐ x ùn l iàn", 0.20, 1.5),
    "暂停训练": ("z àn t íng x ùn l iàn", 0.20, 1.5),
    "继续训练": ("j ì x ù x ùn l iàn", 0.20, 1.5),
    "结束训练": ("j ié sh ù x ùn l iàn", 0.20, 1.5),
    "帮助": ("b āng zh ù", 0.30, 1.2),
    "再说一遍": ("z ài sh uō y í b iàn", 0.25, 1.3),
    "下一个动作": ("x ià y í g è d òng z uò", 0.25, 1.3),
    "上一个动作": ("sh àng y í g è d òng z uò", 0.25, 1.3),
    # 选课阶段
    "腿部": ("t uǐ b ù", 0.30, 1.2),
    "核心": ("h é x īn", 0.30, 1.2),
    "上肢": ("sh àng zh ī", 0.30, 1.2),
    "背部": ("b èi b ù", 0.30, 1.2),
    "全身": ("q uán sh ēn", 0.30, 1.2),
    "确认": ("q uè r èn", 0.30, 1.2),
    "换一个": ("h uàn y í g è", 0.25, 1.3),
}


def _kws_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "models" / "kws"


def _pick_member(names: list[str], kind: str) -> str:
    """Prefer int8 mobile weights, fall back to the fp32 ones."""
    int8 = [n for n in names if n.endswith(f"{kind}-epoch-12-avg-2-chunk-16-left-64.int8.onnx")]
    if int8:
        return int8[0]
    plain = [n for n in names if n.endswith(f"{kind}-epoch-12-avg-2-chunk-16-left-64.onnx")]
    if plain:
        return plain[0]
    any_kind = [n for n in names if f"/{kind}" in n and n.endswith(".onnx")]
    if any_kind:
        return any_kind[0]
    raise RuntimeError(f"no {kind} onnx in archive: {names}")


def download() -> Path:
    dest = _kws_dir()
    dest.mkdir(parents=True, exist_ok=True)
    wanted = ("encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt")
    if all((dest / name).exists() for name in wanted):
        print(f"Already present: {dest}")
        return dest
    last_err: Exception | None = None
    for url in _URLS:
        try:
            print(f"Downloading {url}")
            with tempfile.NamedTemporaryFile(suffix=".tar.bz2", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                urllib.request.urlretrieve(url, tmp_path)
                with tarfile.open(tmp_path) as tar:
                    names = tar.getnames()
                    mapping = {
                        _pick_member(names, "encoder"): "encoder.onnx",
                        _pick_member(names, "decoder"): "decoder.onnx",
                        _pick_member(names, "joiner"): "joiner.onnx",
                        next(n for n in names if n.endswith("tokens.txt")): "tokens.txt",
                    }
                    for member, out_name in mapping.items():
                        src = tar.extractfile(member)
                        if src is None:
                            raise RuntimeError(f"unreadable member {member}")
                        (dest / out_name).write_bytes(src.read())
                        print(f"  {member} -> {out_name}")
            finally:
                tmp_path.unlink(missing_ok=True)
            return dest
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"  failed: {exc}")
    # GitHub release CDN 不可达时的 ModelScope 回退（逐文件下载）。
    try:
        for src_name, out_name in _MS_FILES.items():
            url = _MS_BASE + src_name
            print(f"Downloading {url}")
            urllib.request.urlretrieve(url, dest / out_name)
            print(f"  {src_name} -> {out_name}")
        return dest
    except Exception as exc:  # noqa: BLE001
        last_err = exc
        print(f"  failed: {exc}")
    raise RuntimeError("Could not download the KWS model") from last_err


def generate_keywords(dest: Path | None = None) -> Path:
    """Write keywords.txt, validating every pinyin token against tokens.txt."""
    dest = dest or _kws_dir()
    tokens: set[str] = set()
    for line in (dest / "tokens.txt").read_text(encoding="utf-8").splitlines():
        token = line.split()[0] if line.split() else ""
        if token:
            tokens.add(token)
    out = dest / "keywords.txt"
    lines = []
    for keyword, (token_seq, threshold, boosting) in KEYWORDS.items():
        missing = [t for t in token_seq.split() if t not in tokens]
        if missing:
            raise RuntimeError(f"{keyword}: tokens {missing} missing from tokens.txt")
        # sherpa-onnx 规范：增强得分以 : 开头、触发阈值以 # 开头，位于 @关键词 之前。
        lines.append(f"{token_seq} :{boosting} #{threshold} @{keyword}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"keywords.txt -> {out} ({len(lines)} keywords)")
    return out


def main() -> None:
    dest = download()
    generate_keywords(dest)
    print("Done. Run prepare_android_bridge.py to bundle into assets/kws/.")


if __name__ == "__main__":
    main()
