"""`configs/legal.yaml` 与 `keep` 策略: 法律文书交付件的底线是"不该动的字一个字都不许动"。

背景(实测过的坑): 用 onnx.yaml 跑一份判决书式的材料, 法院名被换成假公司名、审判员/书记员等角色
被抹成 <POSITION_n>、判决日期被当生日抹掉 —— 材料交不出去, 得返工重做。而律师要抹的其实是
身份证/银行卡/手机/住址这类数字型标识与联系方式。
"""
from __future__ import annotations

import pathlib

from docanon_core.config import load_config
from docanon_core.pipeline import process_file
from docanon_core.redaction.mapping import MappingStore

# 判决书式的材料: 机构/案号/角色/日期/金额/信用代码都必须原样保留
JUDGMENT = (
    "北京市朝阳区人民法院\n"
    "民事判决书\n"
    "（2024）京0105民初1234号\n"
    "原告：张某某，男，1980年5月生。\n"
    "委托诉讼代理人：李明，北京华信律师事务所律师。\n"
    "审判员：王某某\n"
    "二〇二四年十月八日\n"
    "判决如下：被告赔偿原告 860000 元。\n"
    "被告某科技有限公司，统一社会信用代码 91110105MA01ABCD2X。\n"
    "原告联系方式：13800001111，邮箱 zhang@example.com，"
    "身份证 11010119900307721X，银行卡 6222020200112233445。\n"
)

KEPT = (
    "北京市朝阳区人民法院",
    "（2024）京0105民初1234号",
    "委托诉讼代理人",
    "审判员",
    "二〇二四年十月八日",
    "860000 元",
    "91110105MA01ABCD2X",
)
ERASED = ("13800001111", "zhang@example.com", "11010119900307721X", "6222020200112233445")


def _legal_config(repo_root: pathlib.Path):
    """legal.yaml 的配置, 但关掉 onnx(它只用来看地址, 需要模型)。

    名字/机构/角色/日期的"不动"不靠模型, 靠 entity_map 里根本没有那些标签 + 策略为 keep,
    所以这份测试在任何环境下(含没装模型的 CI)都有意义。
    """
    cfg = load_config(repo_root / "configs" / "legal.yaml")
    cfg.detectors = {**cfg.detectors, "onnx_ner": False}
    return cfg


def test_legal_preset_has_no_labels_that_could_touch_names_orgs_or_dates():
    """配置层面就把路堵死: onnx 只许产出 LOCATION, 不许产出人名/机构/角色/生日。"""
    cfg = load_config(pathlib.Path(__file__).resolve().parents[3] / "configs" / "legal.yaml")
    assert set(cfg.onnx.entity_map.values()) == {"LOCATION"}, cfg.onnx.entity_map
    for entity_type in ("PERSON", "ORG", "POSITION", "DOB", "AMOUNT", "USCC"):
        assert cfg.strategy_for(entity_type) == "keep", (
            f"{entity_type} 的策略必须是 keep —— 交付件里抹掉它等于把材料作废"
        )
    assert cfg.strategy_for("某个没列出的新类型") == "keep", "DEFAULT 必须是 keep, 否则新类型会被顺手抹掉"


def test_legal_preset_leaves_the_document_usable(repo_root, tmp_path):
    src = tmp_path / "judgment.txt"
    src.write_text(JUDGMENT, encoding="utf-8")
    res = process_file(src, tmp_path / "out", _legal_config(repo_root), MappingStore())
    out = pathlib.Path(res.output_path).read_text(encoding="utf-8")

    for text in KEPT:
        assert text in out, f"不该动的字被抹了: {text}"
    for text in ERASED:
        assert text not in out, f"该抹的没抹: {text}"
    assert not {"PERSON", "ORG", "POSITION", "DOB", "AMOUNT", "USCC"} & set(res.entity_counts)


def test_kept_hits_still_show_up_in_the_trace(repo_root, tmp_path):
    """规则层认得、但配置说"别动"的东西, 必须仍然出现在溯源里。

    否则用户看到产物里留着 860000 元 / 统一社会信用代码, 会以为是漏检 —— 其实是配置保留的。
    """
    src = tmp_path / "judgment.txt"
    src.write_text(JUDGMENT, encoding="utf-8")
    res = process_file(src, tmp_path / "out", _legal_config(repo_root), MappingStore())

    traced = [d for d in res.detections if d["strategy"] == "keep"]
    assert sorted({d["entity_type"] for d in traced}) == ["AMOUNT", "USCC"]
    assert all(d["replacement"] is None for d in traced)
    assert not set(res.entity_counts) & {"AMOUNT", "USCC"}, "保留的不该算进命中数(那是实际抹掉的条数)"

    out = pathlib.Path(res.output_path).read_text(encoding="utf-8")
    assert "860000 元" in out and "91110105MA01ABCD2X" in out
