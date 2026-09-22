"""Developer-only visual calibration surface for the canonical Probe theme."""

from __future__ import annotations

import html
import json

import streamlit as st
import streamlit.components.v1 as components

from probe_theme import (
    PALETTES,
    TYPOGRAPHY_PRESET_NAME,
    contrast_ratio,
    dump_theme_config,
    theme_config,
    typography_css,
    typography_for_preset,
)


SPECIMENS = {
    "display": "Communs de données et IA",
    "section": "Qui suis-je ?",
    "lead": "Genève 2027",
    "question": "Dans quelle position est-ce que je participe ?",
    "body": "Les informations recueillies poursuivent deux objectifs : comprendre les communs et préparer la rencontre.",
    "helper": "Une participation aux deux journées consécutives est souhaitée.",
    "option": "À titre individuel",
    "validation": "Précisons « Autre » avant de continuer.",
    "metadata": "Étape 4 sur 18",
}

VIEWPORTS = (("MOBILE", 390), ("TABLET", 768), ("DESKTOP", 1280), ("WIDE", 1600))


def _interpolated_size(level: dict[str, float | int | str], width: int) -> float:
    if "size" in level:
        return float(level["size"])
    low, high = float(level["min"]), float(level["max"])
    return max(low, min(high, width * 0.04))


def _type_style(level: dict[str, float | int | str], width: int) -> str:
    return (
        f"font-size:{_interpolated_size(level, width):.1f}px;"
        f"line-height:{float(level['line_height'])};"
        f"font-weight:{int(level.get('weight', 400))};"
        f"max-width:{level['max_width']}"
    )


def _typography_markup(typography: dict[str, dict[str, float | int | str]]) -> str:
    cards = []
    for label, width in VIEWPORTS:
        rows = []
        for semantic, copy in SPECIMENS.items():
            rows.append(
                f'<div class="type-row"><span>{semantic.replace("_", " ")}</span>'
                f'<div class="type-{semantic}" style="{_type_style(typography[semantic], width)}">{html.escape(copy)}</div></div>'
            )
        cards.append(
            f'<article class="viewport" style="width:{width}px"><header><b>{label}</b><code>{width} px</code></header>{"".join(rows)}</article>'
        )
    return f'<div class="viewport-strip">{"".join(cards)}</div>'


def _component_set(palette: dict[str, str], *, compact: bool = False) -> str:
    return f"""
    <div class="component-set{' compact' if compact else ''}" style="
      --bg:{palette['background']};--surface:{palette['surface']};--text:{palette['text']};--muted:{palette['muted']};
      --primary:{palette['primary']};--primary-text:{palette['primary_text']};--secondary:{palette['secondary']};
      --secondary-text:{palette['secondary_text']};--selected:{palette['selected']};--focus:{palette['focus']};
      --success:{palette['success']};--warning:{palette['warning']};--error:{palette['error']};
      --checkpoint:{palette['checkpoint']};--disabled:{palette['disabled']};">
      <div class="button-row"><button class="primary">Continuer</button><button class="secondary">Passer</button><button class="tertiary">Signaler</button></div>
      <div class="button-row"><span class="pill selected">Sélectionné</span><span class="pill">Non sélectionné</span></div>
      <label class="input">Votre réponse<span>Écrire ici…</span></label>
      <div class="signals"><i class="success">Success</i><i class="warning">Warning</i><i class="error">Error</i><i class="checkpoint">Checkpoint</i><i class="disabled">Disabled</i></div>
      <p class="sample-text">Text <small>Muted text</small></p>
    </div>"""


def _render_live_palette(name: str, palette: dict[str, str], index: int) -> None:
    """Render the same native primitives used by the production Probe."""

    key = f"probe_palette_{index}"
    scope = f".st-key-{key}"
    css = f"""
    {scope}{{background:{palette['background']};color:{palette['text']};border:1px solid {palette['text']};border-radius:14px;padding:12px;height:100%;}}
    {scope} h4{{font-size:var(--type-metadata)!important;line-height:var(--line-metadata)!important;min-height:34px;letter-spacing:0!important}}
    {scope} div[data-testid="stButton"] button{{width:100%;background:{palette['surface']}!important;color:{palette['text']}!important;border:2px solid {palette['text']}!important;box-shadow:none!important;}}
    {scope} div[data-testid="stButton"]:first-of-type button{{background:{palette['primary']}!important;color:{palette['primary_text']}!important;}}
    {scope} button[data-testid="stBaseButton-pillsActive"]{{background:{palette['selected']}!important;color:{palette['text']}!important;border-color:{palette['text']}!important;}}
    {scope} button[data-testid="stBaseButton-pills"]{{background:{palette['surface']}!important;color:{palette['text']}!important;}}
    {scope} div[data-baseweb="input"]>div{{background:{palette['surface']}!important;border-color:{palette['muted']}!important;}}
    {scope} div[data-testid="stAlert"]{{border-radius:8px;}}
    """
    st.html(f"<style>{css}</style>")
    with st.container(key=key):
        st.markdown(f"#### {name}")
        st.button("Continuer", type="primary", key=f"palette_continue_{index}")
        st.button("Passer", type="secondary", key=f"palette_skip_{index}")
        st.button("Signaler", type="tertiary", key=f"palette_flag_{index}")
        st.pills(
            "Option state",
            ["Sélectionné", "Non sélectionné"],
            default="Sélectionné",
            label_visibility="collapsed",
            key=f"palette_pills_{index}",
        )
        st.text_input(
            "Votre réponse",
            placeholder="Écrire ici…",
            key=f"palette_input_{index}",
        )
        st.success("Success / checkpoint")
        st.warning("Warning")
        st.error("Error")
        st.button("Disabled", disabled=True, key=f"palette_disabled_{index}")


def _ratio(label: str, foreground: str, background: str) -> str:
    value = contrast_ratio(foreground, background)
    return f'<li><span>{html.escape(label)}</span><b>{value:.1f}:1</b><em>{"✓" if value >= 4.5 else "!"}</em></li>'


def _contrast_markup(palette: dict[str, str]) -> str:
    pairs = (
        ("Text / background", palette["text"], palette["background"]),
        ("Text / surface", palette["text"], palette["surface"]),
        ("Muted / background", palette["muted"], palette["background"]),
        ("Continue", palette["primary_text"], palette["primary"]),
        ("Passer", palette["secondary_text"], palette["secondary"]),
        ("Error / surface", palette["error"], palette["surface"]),
    )
    return '<ul class="contrast-list">' + "".join(_ratio(*pair) for pair in pairs) + "</ul>"


def _states_markup(palette: dict[str, str]) -> str:
    variables = ";".join(f"--{key.replace('_', '-')}:{value}" for key, value in palette.items())
    return f"""
    <div class="state-lab" style="{variables}">
      <section><h4>BUTTON</h4><div class="state-row"><button>normal</button><button class="hover">hover</button><button class="focus">focus</button><button class="pressed">pressed</button><button disabled>disabled</button></div></section>
      <section><h4>PILL</h4><div class="state-row"><span class="pill">unselected</span><span class="pill selected">selected</span><span class="pill hover">hover</span><span class="pill disabled">disabled</span></div></section>
      <section><h4>INPUT</h4><div class="state-row"><label class="fake-input">empty</label><label class="fake-input">Montréal</label><label class="fake-input focus">focus</label><label class="fake-input invalid">invalid</label></div></section>
      <section><h4>SKIP</h4><div class="state-row"><div class="micro">Passer</div><div class="micro dialog">Pourquoi passer ?</div><div class="micro confirmed">Question passée ✓</div></div></section>
      <section><h4>CHECKPOINT</h4><div class="state-row"><div class="checkpoint unreached">unreached</div><div class="checkpoint current">current</div><div class="checkpoint saved">saved ✓</div><div class="checkpoint dirty">dirty •</div></div></section>
      <section><h4>TOAST</h4><div class="state-row"><div class="toast success">Enregistré</div><div class="toast warning">À vérifier</div><div class="toast error">À corriger</div></div></section>
    </div>"""


def _compositions_markup(palette: dict[str, str], typography: dict[str, dict[str, float | int | str]]) -> str:
    variables = ";".join(f"--{key.replace('_', '-')}:{value}" for key, value in palette.items())
    display = _type_style(typography["display"], 390)
    question = _type_style(typography["question"], 390)
    cards = (
        ("1 · LANDING", f'<h3 style="{display}">Communs de données et IA</h3><p>Questionnaire participant · environ 20 minutes</p><button>Commencer</button>'),
        ("2 · PORTRAIT", f'<small>QUI SUIS-JE ?</small><h3 style="{question}">Dans quelle position est-ce que je participe ?</h3><span class="pill selected">À titre individuel</span>'),
        ("3 · DENSE MULTI-SELECT", '<small>CE QUE NOUS PARTAGEONS</small><h3>Quels communs mobilisez-vous ?</h3><div class="pill-cloud"><span class="pill selected">Données</span><span class="pill">IA</span><span class="pill">Recherche</span><span class="pill">Institutions</span><span class="pill selected">Savoirs</span><span class="pill">Territoires</span></div>'),
        ("4 · CHECKPOINT", '<small>QUI SUIS-JE ?</small><h3>Enregistrer cette étape</h3><div class="checkpoint saved">Portrait ───────── ✓ checkpoint</div><button>Continuer</button>'),
        ("5 · GENEVA CONTEXT", '<small>CONTEXTE</small><h3>Genève 2027</h3><p>Une participation aux deux journées consécutives est souhaitée.</p><label class="fake-input focus">Votre contribution</label>'),
        ("6 · FINAL INTEGRATION", '<small>RELIRE VOS RÉPONSES</small><h3>Intégrer au paysage commun</h3><p>Vérifiez ce qui sera transmis avant la confirmation finale.</p><button>Intégrer</button>'),
    )
    return '<div class="composition-grid" style="' + variables + '">' + "".join(
        f'<article><header>{label}</header><div>{content}</div></article>' for label, content in cards
    ) + "</div>"


st.markdown(
    f"""
    <style>
    {typography_css()}
    .block-container{{max-width:1600px;padding-top:1.2rem}}.theme-lab-head{{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid rgba(18,33,27,.25);padding-bottom:1rem}}.theme-lab-head h1{{font-size:var(--type-display)!important;line-height:var(--line-display)!important;margin:.2rem 0}}.theme-lab-head p{{max-width:var(--measure-lead);font-size:var(--type-lead);line-height:var(--line-lead)}}.lab-badges{{display:flex;flex-direction:column;align-items:flex-end;gap:.45rem}}.lab-mode{{font-family:"DM Mono",monospace;font-size:var(--type-metadata);letter-spacing:.04em;border:1px solid;padding:.4rem .65rem;border-radius:999px;white-space:nowrap}}.lab-section{{margin:4rem 0 1.25rem;border-top:2px solid var(--ink);padding-top:1rem}}.lab-section span{{font-family:"DM Mono",monospace;font-size:var(--type-metadata);letter-spacing:.08em}}.lab-section h2{{font-size:var(--type-section);line-height:var(--line-section);margin:.25rem 0}}.viewport-strip,.palette-strip{{display:flex;gap:1rem;overflow-x:auto;padding:.25rem .25rem 1.2rem}}.viewport{{flex:0 0 auto;min-height:700px;background:#fffdf6;border:1px solid #12211b;border-radius:16px;padding:20px;overflow:hidden}}.viewport>header{{display:flex;justify-content:space-between;padding-bottom:1rem;border-bottom:1px solid #ccd0ca}}.viewport>header code,.type-row>span{{font-family:"DM Mono",monospace;font-size:var(--type-metadata);text-transform:uppercase;letter-spacing:.08em;color:#647068}}.type-row{{padding:16px 0;border-bottom:1px solid #e1e2dc}}.type-row>div{{margin-top:8px;overflow-wrap:anywhere}}.type-helper,.type-metadata{{color:#647068}}.type-validation{{color:#b73232}}.palette-card{{flex:1 0 310px;border:1px solid #12211b;border-radius:16px;overflow:hidden}}.palette-card>header{{padding:12px 14px;font-family:"DM Mono",monospace;font-size:var(--type-metadata);background:#12211b;color:#fffdf6}}.component-set{{padding:16px;background:var(--bg);color:var(--text);min-height:310px}}.component-set.compact{{min-height:0}}.button-row,.signals,.state-row{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}.component-set button,.state-lab button,.composition-grid button{{appearance:none;border:2px solid var(--text);border-radius:999px;padding:9px 14px;font-weight:800;color:var(--text);background:var(--surface);font-size:var(--type-option);line-height:var(--line-option)}}.component-set .primary{{background:var(--primary);color:var(--primary-text)}}.component-set .secondary{{background:var(--secondary);color:var(--secondary-text)}}.component-set .tertiary{{border-style:dashed}}.pill{{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:6px 10px;font-size:var(--type-option);line-height:var(--line-option)}}.component-set .selected,.state-lab .selected,.composition-grid .selected{{background:var(--selected);color:var(--text)}}.input,.fake-input{{display:flex;flex-direction:column;gap:5px;border:1px solid var(--muted);background:var(--surface);padding:9px 11px;margin:10px 0;border-radius:7px;font-size:var(--type-option);line-height:var(--line-option)}}.input span{{color:var(--muted)}}.signals i{{font-style:normal;padding:4px 7px;border-radius:4px;background:var(--surface);font-size:var(--type-helper)}}.signals .success{{color:var(--success)}}.signals .warning{{color:var(--warning)}}.signals .error{{color:var(--error)}}.signals .checkpoint{{background:var(--checkpoint)}}.signals .disabled{{background:var(--disabled);color:var(--muted)}}.sample-text{{font-size:var(--type-body);line-height:var(--line-body);max-width:var(--measure-body)}}.sample-text small{{color:var(--muted)}}.contrast-list{{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}}.contrast-list li{{display:grid;grid-template-columns:1fr auto auto;gap:8px;background:#fffdf6;border:1px solid #d7d8d1;padding:10px;border-radius:8px}}.contrast-list span{{font-size:var(--type-helper)}}.contrast-list em{{font-style:normal}}.state-lab{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}.state-lab section{{border:1px solid #cfd2cc;border-radius:12px;padding:14px;background:var(--surface)}}.state-lab h4{{font-size:var(--type-metadata);font-family:"DM Mono",monospace;letter-spacing:.08em}}.state-lab button{{background:var(--primary);color:var(--primary-text)}}.state-lab .hover{{filter:brightness(.93);transform:translateY(-1px)}}.state-lab .focus{{outline:3px solid var(--focus);outline-offset:2px}}.state-lab .pressed{{transform:translate(2px,2px);box-shadow:none}}.state-lab button:disabled,.state-lab .disabled{{background:var(--disabled);color:var(--muted);opacity:.75}}.fake-input{{min-width:130px}}.fake-input.invalid{{border:2px solid var(--error);color:var(--error)}}.micro,.checkpoint,.toast{{padding:9px;border:1px solid var(--muted);border-radius:7px;font-size:var(--type-helper)}}.dialog{{box-shadow:0 8px 22px #0002}}.confirmed,.saved,.toast.success{{background:var(--success);color:white}}.current{{border:3px solid var(--focus)}}.dirty,.toast.warning{{background:var(--warning);color:white}}.toast.error{{background:var(--error);color:white}}.composition-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.composition-grid article{{background:var(--background);border:1px solid var(--text);border-radius:14px;overflow:hidden;min-height:330px}}.composition-grid article>header{{background:var(--text);color:var(--surface);font:500 var(--type-metadata) "DM Mono",monospace;padding:9px 12px}}.composition-grid article>div{{padding:18px}}.composition-grid h3{{overflow-wrap:anywhere}}.composition-grid button{{background:var(--primary);color:var(--primary-text);margin-top:14px}}.pill-cloud{{display:flex;flex-wrap:wrap;gap:7px}}.composition-grid .fake-input{{background:var(--surface)}}@media(max-width:900px){{.state-lab,.composition-grid{{grid-template-columns:1fr}}.theme-lab-head{{display:block}}.lab-badges{{align-items:flex-start;margin-top:1rem}}.lab-mode{{display:inline-block}}}}
    .component-set button,.state-lab button,.composition-grid button{{min-height:var(--control-min-height);height:auto;padding:12px 16px}}
    .pill{{padding:.55rem .85rem;min-height:var(--pill-min-height);height:auto;white-space:normal;line-height:1.2}}
    .input,.fake-input{{justify-content:center;min-height:var(--input-min-height);padding:12px 16px}}
    </style>
    <div class="theme-lab-head"><div><div class="eyebrow">DESIGN LAB / THEME LAB</div><h1>Probe visual calibration</h1><p>Typography, palette and component behaviour shown together. Changes on this page are previews only until the exported configuration is deliberately adopted.</p></div><div class="lab-badges"><span class="lab-mode">{TYPOGRAPHY_PRESET_NAME}</span><span class="lab-mode">Developer preview · no writes</span></div></div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Theme controls")
    palette_name = st.selectbox("Working palette", list(PALETTES), index=0)
    typography = typography_for_preset(TYPOGRAPHY_PRESET_NAME)

    palette = dict(PALETTES[palette_name])
    with st.expander("Palette fine controls"):
        for token, value in palette.items():
            palette[token] = st.color_picker(token.replace("_", " ").title(), value, key=f"colour_{palette_name}_{token}")

st.markdown('<div class="lab-section"><span>01 / TYPOGRAPHY LAB</span><h2>One system, four real widths</h2><p>Scroll horizontally to inspect wrapping at each representative viewport.</p></div>', unsafe_allow_html=True)
st.markdown(_typography_markup(typography), unsafe_allow_html=True)

st.markdown('<div class="lab-section"><span>02 / PALETTE LAB</span><h2>Candidate systems</h2><p>The same semantic component set is rendered for every candidate.</p></div>', unsafe_allow_html=True)
palette_columns = st.columns(len(PALETTES))
for palette_index, ((candidate_name, candidate), column) in enumerate(zip(PALETTES.items(), palette_columns)):
    with column:
        _render_live_palette(candidate_name, candidate, palette_index)
st.caption("These are live native Probe primitives. The state matrix below freezes pseudo-states only so they can be compared simultaneously.")

st.markdown(f'<div class="lab-section"><span>03 / INTERACTIVE STATES</span><h2>{html.escape(palette_name)}</h2><p>Forced visual states make hover, focus and pressed treatments comparable at once.</p></div>{_states_markup(palette)}', unsafe_allow_html=True)
st.markdown('<h3>Contrast information</h3>' + _contrast_markup(palette), unsafe_allow_html=True)
st.caption("✓ marks 4.5:1 or better for normal text. ! remains available for experimentation and needs review.")

st.markdown('<div class="lab-section"><span>04 / THEME TOKENS</span><h2>Portable preview configuration</h2><p>Nothing on this page rewrites the canonical theme.</p></div>', unsafe_allow_html=True)
config_text = dump_theme_config(theme_config(typography, palette))
st.code(config_text, language="yaml")
copy_payload = json.dumps(config_text)
components.html(
    f"""<button id="copy">Copy theme config</button><span id="status"></span><style>body{{margin:0;font-family:Manrope,sans-serif}}button{{border:2px solid #12211b;border-radius:999px;background:#d7ff48;padding:.7rem 1rem;font-weight:800}}span{{margin-left:10px}}</style><script>document.getElementById('copy').onclick=async()=>{{await navigator.clipboard.writeText({copy_payload});document.getElementById('status').textContent='Copied';}}</script>""",
    height=48,
)
if st.button("Apply preview", type="secondary", help="Applies only inside this lab session; it does not write theme files."):
    st.session_state["probe_theme_lab_preview"] = theme_config(typography, palette)
    st.toast("Preview applied in this lab only.", icon="🎨")
st.caption("Apply preview is session-local. Adopting these tokens in production remains an explicit code change.")

st.markdown('<div class="lab-section"><span>05 / ACTUAL FIRST VIEWPORTS</span><h2>Atomic choices in composition</h2><p>Six faithful mini-previews use the currently selected preview tokens.</p></div>' + _compositions_markup(palette, typography), unsafe_allow_html=True)
