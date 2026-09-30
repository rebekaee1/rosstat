#!/usr/bin/env python3
"""Read every research XLSX value/formula/annotation without importing the app.

Standard-library ZIP/XML only. Never saves or recalculates an XLSX. The optional
JSON output is a local reading intermediate, not proof that every source value
is current or that Excel calculation/rendering has been accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import posixpath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def text(element: ET.Element | None) -> str:
    return "" if element is None else "".join(element.itertext())


def resolve(part: str, target: str) -> str:
    return target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(part), target))


def relations(archive: ZipFile, part: str) -> dict:
    name = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
    if name not in archive.namelist():
        return {}
    return {r.attrib["Id"]: dict(r.attrib) for r in ET.fromstring(archive.read(name))}


def extract(path: Path) -> dict:
    before = path.read_bytes()
    result = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(before), "bytes": len(before), "sheets": []}
    with ZipFile(path) as archive:
        names = archive.namelist()
        result["zip_members"] = [{"path": name, "sha256": sha(archive.read(name)), "bytes": len(archive.read(name))} for name in names]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        wb_rels = relations(archive, "xl/workbook.xml")
        strings = []
        if "xl/sharedStrings.xml" in names:
            strings = ["".join(node.itertext()) for node in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        styles = ET.fromstring(archive.read("xl/styles.xml")) if "xl/styles.xml" in names else None
        result["number_formats"] = [dict(x.attrib) for x in styles.findall("m:numFmts/m:numFmt", NS)] if styles is not None else []
        result["cell_formats"] = [dict(x.attrib) for x in styles.findall("m:cellXfs/m:xf", NS)] if styles is not None else []
        result["defined_names"] = [{"attributes": dict(x.attrib), "formula": text(x)} for x in workbook.findall("m:definedNames/m:definedName", NS)]
        result["calculation_properties"] = dict(workbook.find("m:calcPr", NS).attrib) if workbook.find("m:calcPr", NS) is not None else {}
        result["external_link_parts"] = [name for name in names if name.startswith("xl/externalLinks/")]
        result["media_parts"] = [name for name in names if name.startswith("xl/media/")]
        result["drawing_parts"] = [name for name in names if name.startswith(("xl/drawings/", "xl/charts/", "xl/embeddings/"))]
        for node in workbook.findall("m:sheets/m:sheet", NS):
            target = resolve("xl/workbook.xml", wb_rels[node.attrib[RID]]["Target"])
            source = ET.fromstring(archive.read(target))
            links = relations(archive, target)
            sheet = {"name": node.attrib["name"], "state": node.attrib.get("state", "visible"), "xml_part": target,
                     "dimension": source.find("m:dimension", NS).attrib.get("ref") if source.find("m:dimension", NS) is not None else None,
                     "cells": [], "hidden_rows": [], "hidden_columns": [], "comments": [], "hyperlinks": []}
            for row in source.findall("m:sheetData/m:row", NS):
                if row.attrib.get("hidden") in {"1", "true"}:
                    sheet["hidden_rows"].append(dict(row.attrib))
                for cell in row.findall("m:c", NS):
                    kind = cell.attrib.get("t", "n")
                    v = cell.find("m:v", NS)
                    f = cell.find("m:f", NS)
                    value = text(cell.find("m:is", NS)) if kind == "inlineStr" else text(v)
                    if kind == "s" and value:
                        value = strings[int(value)]
                    if value != "" or f is not None:
                        item = {"cell": cell.attrib["r"], "type": kind, "style": cell.attrib.get("s"), "value": value}
                        if f is not None:
                            item["formula"] = text(f)
                            item["formula_attributes"] = dict(f.attrib)
                        sheet["cells"].append(item)
            sheet["hidden_columns"] = [dict(x.attrib) for x in source.findall("m:cols/m:col", NS) if x.attrib.get("hidden") in {"1", "true"}]
            sheet["merged_ranges"] = [x.attrib.get("ref") for x in source.findall("m:mergeCells/m:mergeCell", NS)]
            for link in source.findall("m:hyperlinks/m:hyperlink", NS):
                item = dict(link.attrib)
                if RID in item:
                    item["relationship"] = links.get(item[RID])
                sheet["hyperlinks"].append(item)
            for rel in links.values():
                if "comments" in rel.get("Type", "").lower() and rel.get("TargetMode") != "External":
                    part = resolve(target, rel["Target"])
                    comment_xml = ET.fromstring(archive.read(part))
                    authors = [text(x) for x in comment_xml.findall("m:authors/m:author", NS)]
                    for comment in comment_xml.iter():
                        if comment.tag.rsplit("}", 1)[-1] in {"comment", "threadedComment"}:
                            sheet["comments"].append({"part": part, "attributes": dict(comment.attrib), "text": text(comment), "authors": authors})
            sheet["cell_count"] = len(sheet["cells"])
            sheet["formula_count"] = sum("formula" in cell for cell in sheet["cells"])
            sheet["cell_content_sha256"] = sha(json.dumps(sheet["cells"], ensure_ascii=False, sort_keys=True).encode())
            result["sheets"].append(sheet)
    result["source_unchanged"] = before == path.read_bytes()
    if not result["source_unchanged"]:
        raise RuntimeError(f"Source changed during read: {path}")
    return result


def summary(book: dict) -> dict:
    return {"path": book["path"], "sha256": book["sha256"], "source_unchanged": book["source_unchanged"],
            "sheets": [{key: sheet[key] for key in ("name", "state", "dimension", "cell_count", "formula_count", "cell_content_sha256")}
                       | {"hidden_rows": len(sheet["hidden_rows"]), "hidden_columns": len(sheet["hidden_columns"]), "comments": len(sheet["comments"]), "hyperlinks": len(sheet["hyperlinks"])}
                       for sheet in book["sheets"]],
            "external_link_parts": book["external_link_parts"], "media_parts": book["media_parts"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Local JSON containing every extracted nonempty cell/formula")
    parser.add_argument("--summary", type=Path, help="Compact JSON provenance/counts without complete source values")
    args = parser.parse_args()
    sources = sorted((ROOT / "docs/research").glob("*.xlsx"))
    destinations = [path for path in (args.output, args.summary) if path is not None]
    if any(path.suffix.lower() != ".json" for path in destinations):
        parser.error("--output and --summary must use a .json filename")
    resolved_destinations = [path.resolve() for path in destinations]
    protected_paths = {path.resolve() for path in sources} | {Path(__file__).resolve()}
    if any(path in protected_paths for path in resolved_destinations):
        parser.error("output paths must not resolve to a source workbook or this reader")
    if len(resolved_destinations) != len(set(resolved_destinations)):
        parser.error("--output and --summary must resolve to distinct paths")
    books = [extract(path) for path in sources]
    output = {"method": "stdlib ZIP/XML complete source extraction; no Excel execution/recalculation or XLSX writes", "workbooks": books}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    compact = {"workbooks": [summary(book) for book in books]}
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(compact, ensure_ascii=False))


if __name__ == "__main__":
    main()
