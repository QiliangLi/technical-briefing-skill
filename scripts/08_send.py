#!/usr/bin/env python3
from briefing_skill.cli import main
raise SystemExit(main(["send", *(__import__('sys').argv[1:])]))
