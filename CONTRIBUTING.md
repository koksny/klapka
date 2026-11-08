# Contributing to KLAPKA

Thanks for helping. There are three ways in, from easiest to most hands-on.

## 1. Request a phone

[Open a "Request a phone" issue](https://github.com/koksny/klapka/issues/new?template=request-a-phone.yml) with the brand and
model (and the colour or variant, if it matters). The most useful extra is a link to a clear photo of
an **original, unmodified** unit: no operator stickers, no replacement covers. Your own photo of your
own phone is welcome too; say that you are happy for it to be used.

## 2. Report a mistake

[Open a "Report a mistake" issue](https://github.com/koksny/klapka/issues/new?template=fix-a-phone.yml): which phone, what is
wrong (a label, the size, the screen, a detail), and a link or picture that shows how it should be.

## 3. Make or fix a phone yourself

The process is fixed and documented, so results stay consistent:

- The standard: [docs/PIPELINE.md](docs/PIPELINE.md)
- Choosing photos: [docs/REFERENCES.md](docs/REFERENCES.md)
- The file format: [docs/FORMAT.md](docs/FORMAT.md)
- The step-by-step runbook (written for AI agents, works for people too): [AGENTS.md](AGENTS.md)

You will need Python, the tools in this repo and an image server running Qwen-Image 2.1. Open a pull
request when `tools/klapka.py finish` passes and every label has been checked; the pull request
template has the checklist. A maintainer reviews every phone before it is merged.

## Changing the standard

Ideas for a better process are welcome as issues. Show what you tried and what came out; the
standard changes only when the result is clearly better.
