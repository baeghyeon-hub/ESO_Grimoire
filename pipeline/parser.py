"""
하위호환 래퍼 — pipeline.parsers.sets 로 이동됨.

기존 `from pipeline.parser import parse_set` 를 유지하기 위한 re-export.
"""
from pipeline.parsers.sets import ParsedSet, SetBonus, parse_set

__all__ = ["ParsedSet", "SetBonus", "parse_set"]
