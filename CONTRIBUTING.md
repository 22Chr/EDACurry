# Contributing to EDACurry

Thanks for your interest in EDACurry. This document covers how to build the
project, how to propose a change, and the few conventions that keep the
repository tidy.

## Building

### Prerequisites

- A C++17 compiler (GCC, Clang, or AppleClang).
- CMake 3.15 or newer.
- Python 3.7 to 3.13, **including the development headers**. On Debian/Ubuntu
  that is `python3-dev`; on macOS the python.org installers and Homebrew both
  ship them. Without the headers CMake will not find `Development.Module` and
  the build fails at configure time.
- `git`, because CMake fetches pybind11, JSON, pugixml, and pybind11-stubgen at
  configure time via `FetchContent`.
- Doxygen is optional and only needed to build the documentation.

The ANTLR4 runtime is bundled in `sources/libraries/` and is not fetched.

### Build steps

```bash
cd sources
cmake -S . -B build
cmake --build build -j
```

This produces the Python extension module in the build directory, named
something like `edacurry.cpython-311-x86_64-linux-gnu.so`. To use it, put that
directory on your `PYTHONPATH`:

```bash
PYTHONPATH=sources/build python3 -c "import edacurry; print(edacurry.write_eldo)"
```

### Rebuild from scratch when a dependency pin changes

`sources/CMakeLists.txt` pins each fetched dependency to an exact commit. When
one of those `GIT_TAG` values changes, an existing build directory still holds
the old sources and a `CMakeCache.txt` that points at them. The resulting
errors look unrelated to the version change and are hard to diagnose. If you
have just pulled a commit that touches a `GIT_TAG`, delete the build directory
first:

```bash
rm -rf sources/build
```

### Type stubs

The `stubs` target regenerates `edacurry.pyi`, a machine-readable description
of the whole binding surface:

```bash
cmake --build build --target stubs
```

The generated stub is useful for reviewing binding changes: a diff of the
`.pyi` shows exactly what the Python API gained or lost.

## Making a change

### Workflow

External contributors work through a fork:

1. Fork the repository on GitHub and clone your fork.
2. Add this repository as a second remote:
   ```bash
   git remote add upstream https://github.com/esd-univr/EDACurry.git
   ```
3. Create a branch for your work, based on `upstream/main`:
   ```bash
   git fetch upstream
   git checkout -b feature/short-description upstream/main
   ```
4. Commit, push to your fork, and open a pull request against `main`.

Never commit directly to `main`, and never open a pull request from your
fork's `main`.

### Keeping your branch current

Two commands, run from your feature branch:

```bash
git fetch upstream
git merge upstream/main
```

You do not need to keep your fork's `main` up to date — nothing depends on it.
Always branch from `upstream/main` rather than from your own `main`, and this
never becomes a problem.

**Once a pull request is open, use `merge`, not `rebase`.** Rebasing rewrites
the commits the pull request points at, which forces a force-push and discards
the review history attached to them.

## Conventions

### Repository layout

```
grammar/     Eldo and Spectre grammar definitions
sources/     The C++ library, its pybind11 bindings, and tests
tools/       Auxiliary tooling built on top of EDACurry
figures/     Images used by the documentation
```

New C++ goes under `sources/`. Standalone tools that consume the EDACurry API
belong in `tools/<ToolName>/`.

**Do not put a branch name in a directory path.** Branches are temporary and
paths are permanent; a directory named after the branch that introduced it
outlives its own meaning immediately.

### What not to commit

- Build outputs. `build*/` and compiled artifacts (`*.so`, `*.o`, `*.a`) are
  already in `.gitignore` — the one deliberate exception is the bundled ANTLR
  runtime under `sources/libraries/`.
- Large binaries. Git keeps every version of a file forever, so a big asset
  committed once inflates every clone from then on. If a tool needs model
  weights, a vector database, or similar bulk data, have it download that at
  runtime and add the destination to `.gitignore`.
- Anything machine-specific: virtualenvs, IDE directories, local caches.

### Commit messages

Write a short imperative subject line, then a blank line, then the reasoning if
it is not obvious from the diff. Explain *why* the change is needed; the diff
already shows *what* changed. Reference issues and pull requests by number
(`Closes #12`) so GitHub links them.

### Tests

The scripts in `sources/test/` each take one or more netlists or directories as
arguments:

```bash
cd sources/test
PYTHONPATH=../build python3 test_eldo.py eldo/opamp_10_variants.cir
```

They parse the input, write it back out, and print a coloured diff against the
original. Note that they report differences for you to read rather than
returning a non-zero exit status, and that some differences are expected: the
AST normalises numeric literals to scientific notation (`6.05e-6` becomes
`6.05e-06`) and emits the subcircuit name on `.ends`. What you are looking for
is a change in *structure* — a lost component, a dropped parameter, a rewired
node.

If you change the parser, a backend, or the bindings, run the relevant script
before and after and compare the two reports. A parser or backend change should
round-trip: parse a netlist, write it, and confirm the result re-parses.

If `import edacurry` picks up something other than your fresh build, check for
a leftover `edacurry.*.so` in the directory of the script you are running:
Python puts the script's own directory ahead of `PYTHONPATH` on `sys.path`, so
a stale module sitting next to the tests silently shadows the one you just
compiled.

## Reporting bugs

Open an issue with the netlist that triggers it (reduced to the smallest input
that still reproduces), the command you ran, and the full error output. For
build failures, include your OS, compiler version, CMake version, and Python
version — most build problems turn out to be specific to one combination.
