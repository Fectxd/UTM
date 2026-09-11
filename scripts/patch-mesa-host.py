#!/usr/bin/env python3
"""Minimal, idempotent, LLVM-version-aware patches for osy/mesa's pinned commit
so its host mesa_clc build compiles against modern Homebrew LLVM.

The pinned mesa commit predates LLVM >= 20, which:
  1. moved clang::driver::Driver::GetResourcesPath to a free
     clang::GetResourcesPath function (>= 20);
  2. added an OffloadArch enumerator named UNUSED in clang headers, which
     collides with mesa's UNUSED macro from util/macros.h while clang headers
     are parsed (>= 22);
  3. removed TargetRegistry::lookupTarget(StringRef, std::string&) in favour of
     the overload taking a Triple (deprecated in 22, removed in 23).

Usage: patch-mesa-host.py <path-to-mesa.git> [llvm-major-version]
"""
import re
import sys


def patch(path: str, llvm_major: int) -> int:
    clc = path + "/src/compiler/clc/clc_helpers.cpp"
    try:
        text = open(clc, encoding="utf-8").read()
    except OSError:
        print("patch-mesa-host: %s missing (different mesa layout) - nothing to do" % clc)
        return 0

    notes = []

    # 1) Driver::GetResourcesPath became the free clang::GetResourcesPath.
    if llvm_major >= 20 and "Driver::GetResourcesPath" in text:
        text = text.replace("Driver::GetResourcesPath", "clang::GetResourcesPath")
        notes.append("GetResourcesPath")

    # 2) lookupTarget(StringRef, std::string&) -> lookupTarget(const Triple&, ...)
    def fix_lookup(match):
        first = match.group(1)
        if "Triple" in first:
            return match.group(0)
        return "TargetRegistry::lookupTarget(llvm::Triple(%s), %s)" % (first, match.group(2))

    text, count = re.subn(
        r"TargetRegistry::lookupTarget\(\s*([^,()]+?)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
        fix_lookup,
        text,
    )
    if count:
        notes.append("lookupTarget x%d" % count)

    # 3) Keep mesa's UNUSED macro out of the LLVM/clang include block. The macro
    #    must be defined *before* the guard because code after the clang includes
    #    (e.g. the ASSERTED macro) still needs it, so pull util/macros.h in early.
    if '#pragma push_macro("UNUSED")' not in text:
        out = []
        include_inserted = False
        guard_open = False
        guard_closed = False
        for line in text.split("\n"):
            if not include_inserted and line.startswith('#include "util/'):
                out.append('#include "util/macros.h" /* patch-mesa-host: define UNUSED early */')
                include_inserted = True
            if not guard_open and line.startswith("#include <llvm/"):
                if not include_inserted:
                    out.append('#include "util/macros.h" /* patch-mesa-host: define UNUSED early */')
                    include_inserted = True
                out.append("/* patch-mesa-host: keep mesa UNUSED macro out of clang headers */")
                out.append('#pragma push_macro("UNUSED")')
                out.append("#undef UNUSED")
                guard_open = True
            out.append(line)
            if guard_open and not guard_closed and line.startswith("#include <clang/Basic/TargetInfo.h>"):
                out.append('#pragma pop_macro("UNUSED")')
                guard_closed = True
        if guard_open:
            if not guard_closed:
                out.append('#pragma pop_macro("UNUSED")')
            text = "\n".join(out)
            notes.append("UNUSED guard")

    if notes:
        with open(clc, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("patch-mesa-host: applied " + ", ".join(notes))
    else:
        print("patch-mesa-host: nothing to patch (already compatible)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("usage: patch-mesa-host.py <path-to-mesa.git> [llvm-major-version]", file=sys.stderr)
        sys.exit(1)
    major = 0
    if len(sys.argv) == 3:
        try:
            major = int(sys.argv[2].strip())
        except ValueError:
            major = 0
    sys.exit(patch(sys.argv[1], major))
