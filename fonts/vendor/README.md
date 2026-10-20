# Pinned font build dependencies

- `JetBrainsMono-v3.5.1.tar.xz`: unmodified [Nerd Fonts v3.5.1 release asset](https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/JetBrainsMono.tar.xz).
- `fonttools-4.67.0-py3-none-any.whl`: unmodified pure Python wheel from [PyPI fonttools 4.67.0](https://pypi.org/project/fonttools/4.67.0/).
- `pypng-0.20220715.0-py3-none-any.whl`: pinned pure Python PNG reader from [PyPI pypng](https://pypi.org/project/pypng/0.20220715.0/), under the included MIT license.
- `Pet-Cats-Pack.zip`: unmodified [Pet Cats Pack by LuizMelo](https://luizmelo.itch.io/pet-cat-pack), downloaded 2026-10-20 (itch.io upload `14065011`). The included `License.txt` declares CC0; a copy is in `Pet-Cats-Pack-LICENSE.txt`. The first cat supplies the new skin.

`SHA256SUMS` verifies the exact inputs before every build. The wheels load
directly through `PYTHONPATH`: no pip, virtual environment, or network is
needed for font setup. Python 3.11 or newer is required. Licenses are included
here and in the original archives. RunCat's BSD license is in `../LICENSE`.
