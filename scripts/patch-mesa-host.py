#!/usr/bin/env python3
"""Minimal, idempotent patches so osy/mesa's host mesa_clc build compiles
against any recent Homebrew LLVM major.

Background: the pinned mesa commit predates LLVM >= 20, which:
  1. moved clang::driver::Driver::GetResourcesPath to a free
     clang::GetResourcesPath function, and
  2. added an OffloadArch enumerator named UNUSED in clang headers, which
     collides with mesa's UNUSED macro (from src/util/macros.h) while the
     LLVM/clang headers are parsed inside clc_helpers.cpp.

Usage: patch-mesa-host.py <path-to-mesa.git>
"""
import re
import sys


def patch(path: str) -> int:
    clc = path + "/src/compiler/clc/clc_helpers.cpp"
    try:
        text = open(clc, encoding="utf-8").read()
    except OSError:
        print("patch-mesa-host: cannot read", clc, file=sys.stderr)
        return 1

    changed = False

    # 1) Driver::GetResourcesPath is no longer a static member in LLVM >= 20.
    if "Driver::GetResourcesPath" in text:
        text = text.replace("Driver::GetResourcesPath", "clang::GetResourcesPath")
        changed = True
        print("patch-mesa-host: GetResourcesPath fixed")

    # 2) Keep mesa's UNUSED macro out of the LLVM/clang include block.
    if '#pragma push_macro("UNUSED")' not in text:
        lines = text.split("\n")
        out = []
        guard_done = False
        for line in lines:
            if not guard_done and line.startswith("#include <llvm/"):
                out.append('/* patch-mesa-host: keep mesa UNUSED macro out of clang headers */')
                out.append('#pragma push_macro("UNUSED")')
                out.append("#undef UNUSED")
                guard_done = True
            out.append(line)
            if guard_done and line.startswith("#include <clang/Basic/TargetInfo.h>"):
                out.append('#pragma pop_macro("UNUSED")')
                guard_done = False
        text = "\n".join(out)
        changed = True
        print("patch-mesa-host: UNUSED macro guard added")

    if changed:
        with open(clc, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print("patch-mesa-host: already patched, nothing to do")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: patch-mesa-host.py <path-to-mesa.git>", file=sys.stderr)
        sys.exit(1)
    sys.exit(patch(sys.argv[1]))
