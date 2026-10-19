# Pinned font build dependencies

- `JetBrainsMono-v3.5.1.tar.xz`: unmodified [Nerd Fonts v3.5.1 release asset](https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/JetBrainsMono.tar.xz).
- `fonttools-4.67.0-py3-none-any.whl`: unmodified pure Python wheel from [PyPI fonttools 4.67.0](https://pypi.org/project/fonttools/4.67.0/).

`SHA256SUMS` verifies the exact inputs before every build. The wheel loads
directly through `PYTHONPATH`: no pip, virtual environment, or network is
needed for font setup. Python 3.11 or newer is required. Licenses are included
here and in the original archives. RunCat's BSD license is in `../LICENSE`.
