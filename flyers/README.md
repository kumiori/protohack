# Commons QR flyers

The source produces ten editable A6 portrait flyer variants. All copy and route
settings are grouped in the `EDIT COPY AND ROUTE SETTINGS HERE` block near the
top of `commons_qr_flyers.tex`.

Build from this `flyers` directory:

```sh
make
```

The PDF is written to `../output/pdf/commons_qr_flyers.pdf`. The Makefile uses
`latexmk`, which automatically performs the multiple XeLaTeX passes required by
TikZ `remember picture`. A single direct `xelatex` pass creates pages before
their stored positions are available and therefore appears blank.

The equivalent direct command from inside `flyers` is:

```sh
latexmk -xelatex -interaction=nonstopmode -halt-on-error \
  -outdir=../output/pdf commons_qr_flyers.tex
```

The source searches both `../qrs/` and `qrs/`, so it can also be compiled from
the repository root. If using bare `xelatex`, run it twice.

To force a complete rebuild or check that the output has ten nonblank pages:

```sh
make rebuild
make check
```

Only these route/QR pairs are used:

| Module | Route | QR file | Flyer pages |
| --- | --- | --- | --- |
| Intro | `/intro` | `qrs/protohackapp.png` | 1, 10 |
| Commons | `/commons` | `qrs/ph_commons.png` | 2, 3, 4, 6, 8 |
| Mapping | `/mapping` | `qrs/ph_mapping.png` | 5, 7, 9 |

Every flyer prints its module and route in a visible badge. The extended-slides
QR is intentionally excluded.

The black signature family provides three direct comparisons:

- page 3: `DEFEND THE COMMONS. TOGETHER.`;
- page 6: `OFFENSIVE COMMONS. TOGETHER.`;
- page 9: the enlarged orbital `OFFENSIVE COMMONS` treatment.
