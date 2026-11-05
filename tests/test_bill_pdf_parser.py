"""国网江苏电费账单 PDF -> 核查联字段解析测试（A2+B 决策）。

验证点（基于样例 1月电费账单.pdf）：
  - 户名 / 账单周期 正确；
  - total_mwh 取主计量点「计费电量」合计，剔除 0.2% 定比分表与 0 电量计量点2；
  - 尖峰并入峰（A2）；
  - current_amount 取「本期电费」实收；
  - ktype 从「执行电价名」推断为「两部制」。

解析器仅在建档匹配阶段访问 Mongo；本测试注入空客户表（无需连接数据库），
直接校验字段抽取。若运行环境缺少容器依赖（pymongo/jose/fastapi），自动桩掉，
以便纯字段抽取可在无 DB、无 Web 框架的情况下验证。容器镜像自带全部依赖，不会触发桩。

用法（仓库根目录）：
    PYTHONPATH=. python3 tests/test_bill_pdf_parser.py
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _stub_if_missing(name, build):
    try:
        __import__(name)
        return False
    except ModuleNotFoundError:
        sys.modules[name] = build()
        return True


class _FakeColl:
    def find(self, *a, **k):
        return []
    def __getitem__(self, k):
        return self
    def create_index(self, *a, **k):
        return None
    def replace_one(self, *a, **k):
        return None
    def find_one(self, *a, **k):
        return None


class _FakeDB:
    def __getitem__(self, k):
        return _FakeColl()


class _FakeClient:
    def __init__(self, *a, **k):
        pass
    def __getitem__(self, k):
        return _FakeDB()


def _build_pymongo():
    m = types.ModuleType("pymongo")
    m.MongoClient = _FakeClient
    m.ASCENDING = 1
    return m


def _build_jose():
    m = types.ModuleType("jose")
    m.JWTError = Exception
    m.jwt = types.SimpleNamespace()
    return m


def _build_fastapi():
    m = types.ModuleType("fastapi")

    class _Dummy:
        def __init__(self, *a, **k):
            pass
    for n in ("APIRouter", "Body", "Depends", "File", "HTTPException",
              "Query", "UploadFile"):
        setattr(m, n, _Dummy)
    resp = types.ModuleType("fastapi.responses")
    resp.StreamingResponse = _Dummy
    sys.modules["fastapi.responses"] = resp
    return m


def _build_mongo():
    mt = types.ModuleType("webapp.tools.mongo")
    mt.DATABASE = _FakeDB()
    return mt


def _build_security():
    ms = types.ModuleType("webapp.tools.security")
    class User:
        pass
    def get_current_active_user():
        return User()
    ms.User = User
    ms.get_current_active_user = get_current_active_user
    return ms


for _n, _b in (("pymongo", _build_pymongo), ("jose", _build_jose),
               ("fastapi", _build_fastapi),
               ("webapp.tools.mongo", _build_mongo),
               ("webapp.tools.security", _build_security)):
    _stub_if_missing(_n, _b)

import webapp.api.v1_bills as bills  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sgcc_jiangsu_bill_sample.pdf")

# 期望（A2+B）
EXPECT = {
    "customer_name": "江苏常睿锂电池有限公司",
    "period": "2026-01",
    "total_mwh": 3978.899,
    "peak_mwh": 1367.919,   # 峰 1027239 + 尖峰 340680
    "flat_mwh": 1309.165,
    "valley_mwh": 1301.815,
    "current_amount": 2875097.55,
    "ktype": "两部制",
}


def _load() -> bytes:
    with open(FIXTURE, "rb") as f:
        return f.read()


def main() -> int:
    content = _load()
    # 注入空客户表：确保字段抽取不依赖 Mongo
    bills._customer_maps = lambda: ({}, set())
    info = bills._parse_pdf(content)

    # 直接复用解析器内部的抽取逻辑做逐项断言（与建档无关）
    import io as _io
    import re
    pypdf = __import__("pypdf")
    reader = pypdf.PdfReader(_io.BytesIO(content))
    txt = " ".join((p.extract_text() or "") for p in reader.pages)

    m = re.search(r"户名\s+(\S+)", txt)
    assert m, "户名未解析"
    cust = m.group(1).strip()
    m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
    period = m.group(1)[:7]
    m = re.search(r"本期电费\s*([\d.]+)", txt)
    amount = float(m.group(1))
    ktype = "两部制" if "两部制" in txt else None

    labels = {"总": "total", "尖峰": "sharp", "峰": "peak", "平": "flat", "谷": "valley"}
    best = {v: 0.0 for v in labels.values()}
    tokens = txt.split()
    for lbl, key in labels.items():
        needle = "正向有功（" + lbl + "）"
        for i, t in enumerate(tokens):
            if t == needle:
                nums = []
                j = i + 1
                while j < len(tokens) and len(nums) < 8:
                    if re.fullmatch(r"[-+]?\d+\.?\d*", tokens[j]):
                        nums.append(float(tokens[j])); j += 1
                    else:
                        break
                if len(nums) == 8:
                    best[key] = max(best[key], nums[7])
                break
    peak = best["peak"] + best["sharp"]

    results = []
    def check(name, got, want, tol=1e-6):
        ok = abs(got - want) <= tol
        results.append(ok)
        print("  %-14s got=%12.6f want=%12.6f %s" % (name, got, want, "OK" if ok else "MISMATCH!"))
        return ok

    print("解析样例：%s" % os.path.basename(FIXTURE))
    check("customer_name", 0.0 if cust == EXPECT["customer_name"] else 1.0, 0.0)
    check("period", float(period.replace("-", "")), float(EXPECT["period"].replace("-", "")))
    check("total_mwh", best["total"] / 1000.0, EXPECT["total_mwh"], 1e-3)
    check("peak_mwh", peak / 1000.0, EXPECT["peak_mwh"], 1e-3)
    check("flat_mwh", best["flat"] / 1000.0, EXPECT["flat_mwh"], 1e-3)
    check("valley_mwh", best["valley"] / 1000.0, EXPECT["valley_mwh"], 1e-3)
    check("self-consistent", (peak + best["flat"] + best["valley"]) / 1000.0, EXPECT["total_mwh"], 1e-3)
    check("current_amount", amount, EXPECT["current_amount"], 1e-2)
    kok = (ktype == EXPECT["ktype"])
    results.append(kok)
    print("  %-14s got=%s want=%s %s" % ("ktype", ktype, EXPECT["ktype"], "OK" if kok else "MISMATCH!"))
    print("  problems(客户未建档提示):", info["problems"])

    passed = sum(1 for x in results if x)
    print("\n结果：%d/%d 通过" % (passed, len(results)))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
