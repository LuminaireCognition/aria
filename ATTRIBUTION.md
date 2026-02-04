# Attribution

## EVE Online

EVE Online and all associated content, including but not limited to:
- Game mechanics and terminology
- Faction names and lore
- Ship and module names
- In-game locations and organizations

are the intellectual property of **CCP Games**.

### Required Notice (CCP Developer License Agreement)

© 2014 CCP hf. All rights reserved. "EVE", "EVE Online", "CCP", and all related logos and images are trademarks or registered trademarks of CCP hf.

### Disclaimer

This is a fan project created for personal use and is **not affiliated with, endorsed by, or sponsored by CCP Games**. ARIA is not affiliated with AURA, CCP's in-game AI assistant.

Use of EVE Online content and the ESI API is subject to the [CCP Developer License Agreement](https://developers.eveonline.com/license-agreement), which restricts commercial use.

For more information about EVE Online, visit: https://www.eveonline.com/

## EVE University Wiki

Mission intelligence data, fitting guides, and game mechanics references have been adapted from the [EVE University Wiki](https://wiki.eveuniversity.org/).

EVE University Wiki content is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License (CC-BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).

Under the terms of this license:
- **Attribution** — You must give appropriate credit to EVE University
- **ShareAlike** — Derivative works must be licensed under the same terms

## Claude Code

ARIA is designed to work with [Claude Code](https://claude.com/claude-code), a product of [Anthropic](https://www.anthropic.com/).

Claude Code and Claude are products of Anthropic, PBC.

## EOS Fitting Library

ARIA includes a vendored copy of the EOS library from the Pyfa project.

- **Source**: https://github.com/pyfa-org/eos
- **Commit**: c2cc80fd3b1951ac44be3702d59e5047cc7fa494
- **License**: GNU Lesser General Public License v3.0 (LGPL-3.0)
- **Copyright**: Pyfa Team (Diego Duclos, Anton Vorobyov, and contributors)
- **Location**: `src/aria_esi/_vendor/eos/`

EOS is a ship fitting calculation library used to compute DPS, tank statistics, and resource usage for EVE Online ship fits. The LGPL-3.0 license allows vendoring within this MIT-licensed project while maintaining the LGPL terms for the EOS code itself.

Under the terms of the LGPL-3.0:
- The vendored EOS source code remains available in `src/aria_esi/_vendor/eos/`
- The full LGPL-3.0 license is included at `src/aria_esi/_vendor/eos/LICENSE`
- The referenced GPL-3.0 is included at `src/aria_esi/_vendor/eos/COPYING`
- Users are free to modify and replace the vendored EOS with a modified version

## Open Source

The ARIA framework itself is released under the [MIT License](LICENSE).

## Contributors

Thank you to all contributors who have helped improve ARIA.

---

*If you believe any content in this project requires additional attribution or licensing consideration, please open an issue.*
