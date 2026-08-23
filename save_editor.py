#!/usr/bin/env python3
import struct
import sys
import copy

# --------------------------------------------------------------------------
# Codec binario (Godot Variant)
# --------------------------------------------------------------------------

NIL, BOOL, INT, FLOAT, STRING, DICTIONARY, ARRAY = 0, 1, 2, 3, 4, 27, 28

TYPE_NAMES = {
    NIL: "Nil", BOOL: "Bool", INT: "Int", FLOAT: "Float",
    STRING: "String", DICTIONARY: "Dictionary", ARRAY: "Array",
}


class Variant:
    """Um valor do Godot com seu tipo/flags originais preservados."""
    __slots__ = ("vtype", "flags", "value")

    def __init__(self, vtype, flags, value):
        self.vtype = vtype
        self.flags = flags
        self.value = value

    def __repr__(self):
        return f"Variant({TYPE_NAMES.get(self.vtype, self.vtype)}, {self.value!r})"


def decode_variant(buf, off):
    header = struct.unpack_from("<I", buf, off)[0]
    off += 4
    vtype = header & 0xFFFF
    flags = header >> 16

    if vtype == NIL:
        return Variant(vtype, flags, None), off
    if vtype == BOOL:
        v = struct.unpack_from("<i", buf, off)[0]
        off += 4
        return Variant(vtype, flags, bool(v)), off
    if vtype == INT:
        if flags & 1:
            v = struct.unpack_from("<q", buf, off)[0]
            off += 8
        else:
            v = struct.unpack_from("<i", buf, off)[0]
            off += 4
        return Variant(vtype, flags, v), off
    if vtype == FLOAT:
        if flags & 1:
            v = struct.unpack_from("<d", buf, off)[0]
            off += 8
        else:
            v = struct.unpack_from("<f", buf, off)[0]
            off += 4
        return Variant(vtype, flags, v), off
    if vtype == STRING:
        ln = struct.unpack_from("<I", buf, off)[0]
        off += 4
        s = buf[off:off + ln].decode("utf-8", errors="replace")
        off += ln
        pad = (4 - (ln % 4)) % 4
        off += pad
        return Variant(vtype, flags, s), off
    if vtype == DICTIONARY:
        size = struct.unpack_from("<I", buf, off)[0]
        off += 4
        pairs = []
        for _ in range(size):
            k, off = decode_variant(buf, off)
            v, off = decode_variant(buf, off)
            pairs.append((k, v))
        return Variant(vtype, flags, pairs), off
    if vtype == ARRAY:
        size = struct.unpack_from("<I", buf, off)[0]
        off += 4
        items = []
        for _ in range(size):
            v, off = decode_variant(buf, off)
            items.append(v)
        return Variant(vtype, flags, items), off

    raise ValueError(f"Tipo de Variant nao suportado: {vtype} (offset {off - 4})")


def encode_variant(v):
    header = (v.flags << 16) | v.vtype
    buf = bytearray(struct.pack("<I", header))

    if v.vtype == NIL:
        pass
    elif v.vtype == BOOL:
        buf += struct.pack("<i", 1 if v.value else 0)
    elif v.vtype == INT:
        if v.flags & 1:
            buf += struct.pack("<q", int(v.value))
        else:
            buf += struct.pack("<i", int(v.value))
    elif v.vtype == FLOAT:
        if v.flags & 1:
            buf += struct.pack("<d", float(v.value))
        else:
            buf += struct.pack("<f", float(v.value))
    elif v.vtype == STRING:
        s = str(v.value).encode("utf-8")
        buf += struct.pack("<I", len(s))
        buf += s
        pad = (4 - (len(s) % 4)) % 4
        buf += b"\x00" * pad
    elif v.vtype == DICTIONARY:
        buf += struct.pack("<I", len(v.value))
        for k, val in v.value:
            buf += encode_variant(k)
            buf += encode_variant(val)
    elif v.vtype == ARRAY:
        buf += struct.pack("<I", len(v.value))
        for item in v.value:
            buf += encode_variant(item)
    else:
        raise ValueError(f"Tipo de Variant nao suportado para escrita: {v.vtype}")

    return bytes(buf)


class SaveFile:
    """Save do Godot carregado em memoria, com acesso por chave ao dicionario raiz."""

    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read()
        declared = struct.unpack_from("<I", raw, 0)[0]
        if declared != len(raw) - 4:
            raise ValueError(
                f"Tamanho declarado ({declared}) nao bate com o arquivo "
                f"({len(raw) - 4} bytes restantes). Arquivo pode estar truncado "
                f"ou nao ser um save Godot store_var()."
            )
        root, end = decode_variant(raw, 4)
        if end != len(raw):
            raise ValueError("Sobrou lixo no final do arquivo apos o parse; "
                              "formato inesperado.")
        if root.vtype != DICTIONARY:
            raise ValueError("A raiz do save nao e um Dictionary.")
        self.root = root
        self._reindex()

    def _reindex(self):
        self.index = {}
        for k, v in self.root.value:
            self.index[k.value] = v

    def keys(self):
        return [k.value for k, _ in self.root.value]

    def get(self, key):
        return self.index.get(key)

    def has(self, key):
        return key in self.index

    def to_bytes(self):
        body = encode_variant(self.root)
        return struct.pack("<I", len(body)) + body

    def save_as(self, path):
        data = self.to_bytes()
        with open(path, "wb") as f:
            f.write(data)
        self.path = path

    def save(self):
        self.save_as(self.path)


# --------------------------------------------------------------------------
# GUI (PyQt5)
# --------------------------------------------------------------------------

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFormLayout, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QLabel, QPushButton, QScrollArea, QGroupBox, QFileDialog, QMessageBox,
    QComboBox, QStatusBar, QFrame, QProgressBar, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QIcon


# --------------------------------------------------------------------------
# Tema visual
# --------------------------------------------------------------------------

ACCENT = "#4fc3f7"
ACCENT_DARK = "#0288d1"
BG = "#1e2128"
BG_PANEL = "#262a33"
BG_CARD = "#2d323c"
BORDER = "#3a4050"
TEXT = "#e8eaf0"
TEXT_DIM = "#9aa2b1"
GOOD = "#4caf50"
BAD = "#e57373"

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Ubuntu", "Cantarell", sans-serif;
    color: {TEXT};
}}
QMainWindow, QWidget#central {{
    background: {BG};
}}
QLabel#title {{
    font-size: 19px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#subtitle {{
    color: {TEXT_DIM};
    font-size: 11px;
}}
QLabel#pathLabel {{
    color: {TEXT_DIM};
    font-size: 11px;
    padding: 2px 4px;
}}
QFrame#topBar {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}
QPushButton {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background: #363c48;
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background: #20242c;
}}
QPushButton#primary {{
    background: {ACCENT_DARK};
    border: 1px solid {ACCENT_DARK};
    color: white;
}}
QPushButton#primary:hover {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QPushButton#danger {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QPushButton#danger:hover {{
    border-color: {BAD};
    color: {BAD};
}}
QTabWidget::pane {{
    border: none;
    background: {BG};
    top: 0px;
}}
QTabWidget {{
    background: {BG};
}}
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_DIM};
    padding: 10px 18px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 12px;
    border-bottom: 3px solid transparent;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 3px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QGroupBox {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    font-weight: 700;
    font-size: 12px;
    padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    top: 2px;
    padding: 0 6px;
    color: {ACCENT};
}}
QCheckBox {{
    spacing: 8px;
    padding: 3px 2px;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1.5px solid {BORDER};
    background: {BG};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {GOOD};
    border-color: {GOOD};
}}
QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    min-width: 90px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QStatusBar {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QProgressBar {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 7px;
    height: 14px;
    text-align: center;
    color: {TEXT};
    font-size: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_DARK}, stop:1 {ACCENT});
    border-radius: 6px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_DARK};
}}
QToolTip {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {ACCENT};
    padding: 4px 8px;
    border-radius: 5px;
}}
"""

TAB_ICONS = {
    "Niveis": "\U0001F5FA\uFE0F",
    "Armas": "\U0001F52B",
    "Coracoes && E-Tanks": "\u2764\uFE0F",
    "Upgrades": "\u2B06\uFE0F",
    "Estatisticas": "\U0001F4CA",
    "Config.": "\u2699\uFE0F",
    "Chips": "\U0001FA99",
    "Outros campos": "\U0001F4C1",
}


# Categorias conhecidas deste save (MMX fangame). Chaves fora dessas listas
# ainda aparecem na aba "Outros campos", detectadas automaticamente pelo tipo.
LEVEL_KEYS = [
    "intro_level_complete", "air_level_complete", "fire_level_complete",
    "train_level_complete", "water_level_complete", "snow_level_complete",
    "desert_level_complete", "space_level_complete", "swamp_level_complete",
    "sigma_level_1_complete", "sigma_level_2_complete", "sigma_level_3_complete",
]
WEAPON_KEYS = [
    "weapon_unlocked_fire", "weapon_unlocked_air", "weapon_unlocked_water",
    "weapon_unlocked_snow", "weapon_unlocked_train", "weapon_unlocked_space",
    "weapon_unlocked_desert", "weapon_unlocked_swamp",
]
HEART_KEYS = [
    "heart_air", "heart_fire", "heart_train", "heart_water",
    "heart_snow", "heart_desert", "heart_space", "heart_swamp",
]
ETANK_FLAG_KEYS = ["etank_snow", "etank_water", "etank_air", "etank_space"]
ETANK_HEALTH_KEYS = ["etank1_health", "etank2_health", "etank3_health", "etank4_health"]
UPGRADE_KEYS = [
    "leg_upgrade", "leg_upgrade2", "arm_upgrade", "helmet_upgrade",
    "chest_upgrade", "chest_upgrade2", "buster_upgrade", "buster_upgrade2",
    "hadouken_upgrade", "double_tap_dash",
]
STAT_KEYS = [
    "hearts", "etanks", "lives", "max_health", "chips_spent",
    "total_deaths", "total_kills", "total_standard_shots",
    "total_standard_charge_shots", "total_special_weapon_shots",
    "total_special_weapon_charge_shots",
]
SETTING_KEYS = [
    "difficulty", "language", "haptic_feedback", "environment_particles",
    "set_music_volume", "set_sfx_volume", "speedrunning", "enable_weapon_wheel",
]
ARRAY_KEY = "chips"

ALL_KNOWN = set(
    LEVEL_KEYS + WEAPON_KEYS + HEART_KEYS + ETANK_FLAG_KEYS + ETANK_HEALTH_KEYS
    + UPGRADE_KEYS + STAT_KEYS + SETTING_KEYS + [ARRAY_KEY, "save_file_exists"]
)


def pretty_label(key):
    return key.replace("_", " ").strip().capitalize()


class BoolField(QCheckBox):
    def __init__(self, variant):
        super().__init__()
        self.variant = variant
        self.setChecked(bool(variant.value))
        self.stateChanged.connect(self._on_change)

    def _on_change(self, _state):
        self.variant.value = self.isChecked()


class IntField(QSpinBox):
    def __init__(self, variant):
        super().__init__()
        self.variant = variant
        self.setRange(-2_000_000_000, 2_000_000_000)
        self.setValue(int(variant.value))
        self.valueChanged.connect(self._on_change)

    def _on_change(self, val):
        self.variant.value = int(val)


class FloatField(QDoubleSpinBox):
    def __init__(self, variant):
        super().__init__()
        self.variant = variant
        self.setRange(-1_000_000.0, 1_000_000.0)
        self.setDecimals(4)
        self.setValue(float(variant.value))
        self.valueChanged.connect(self._on_change)

    def _on_change(self, val):
        self.variant.value = float(val)


class StringField(QLineEdit):
    def __init__(self, variant):
        super().__init__()
        self.variant = variant
        self.setText(str(variant.value))
        self.textChanged.connect(self._on_change)

    def _on_change(self, text):
        self.variant.value = text


def make_field_widget(variant):
    if variant.vtype == BOOL:
        return BoolField(variant)
    if variant.vtype == INT:
        return IntField(variant)
    if variant.vtype == FLOAT:
        return FloatField(variant)
    if variant.vtype == STRING:
        return StringField(variant)
    lbl = QLabel(f"<{TYPE_NAMES.get(variant.vtype, variant.vtype)}> nao editavel aqui")
    lbl.setEnabled(False)
    return lbl


class MainWindow(QMainWindow):
    def __init__(self, initial_path=None):
        super().__init__()
        self.setWindowTitle("Save Editor - Godot (store_var)")
        self.resize(820, 680)

        self.save = None
        self.bool_widgets = []          # p/ botoes "marcar tudo"
        self.chip_checkboxes = []

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- barra superior -------------------------------------------------
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(18, 14, 18, 14)
        top_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("\U0001F3AE  Save Editor")
        title.setObjectName("title")
        self.path_label = QLabel("Nenhum arquivo aberto")
        self.path_label.setObjectName("pathLabel")
        title_box.addWidget(title)
        title_box.addWidget(self.path_label)
        title_row.addLayout(title_box)
        title_row.addStretch()

        self.progress = QProgressBar()
        self.progress.setFixedWidth(180)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p% completo")
        title_row.addWidget(self.progress)
        top_layout.addLayout(title_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_open = QPushButton("\U0001F4C2  Abrir")
        btn_open.clicked.connect(self.open_file)
        btn_save = QPushButton("\U0001F4BE  Salvar")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self.save_file)
        btn_save_as = QPushButton("Salvar como...")
        btn_save_as.clicked.connect(self.save_file_as)
        btn_unlock_all = QPushButton("\u2728  Desbloquear tudo")
        btn_unlock_all.setObjectName("primary")
        btn_unlock_all.setToolTip(
            "Marca todos os niveis, armas, coracoes, upgrades, E-Tanks e "
            "coletaveis como completos/desbloqueados, e enche a vida/E-Tanks."
        )
        btn_unlock_all.clicked.connect(self.unlock_everything)
        btn_reset_all = QPushButton("Zerar tudo")
        btn_reset_all.setObjectName("danger")
        btn_reset_all.clicked.connect(self.reset_everything)

        btn_row.addWidget(btn_open)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_save_as)
        btn_row.addStretch()
        btn_row.addWidget(btn_reset_all)
        btn_row.addWidget(btn_unlock_all)
        top_layout.addLayout(btn_row)

        outer.addWidget(top_bar)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 16, 16, 8)
        container_layout.addWidget(self.tabs)
        outer.addWidget(container, 1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        if initial_path:
            self.load(initial_path)

    # --- carregamento / gravacao --------------------------------------------

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir save", "", "Save files (*.json *.sav *.dat);;Todos (*)"
        )
        if path:
            self.load(path)

    def load(self, path):
        try:
            self.save = SaveFile(path)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao abrir", str(e))
            return
        self.path_label.setText(path)
        self.status.showMessage(f"Carregado: {len(self.save.keys())} campos", 5000)
        self.build_tabs()
        self.update_progress()

    def save_file(self):
        if not self.save:
            return
        self._write(self.save.path)

    def save_file_as(self):
        if not self.save:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar como", self.save.path, "Save files (*.json);;Todos (*)"
        )
        if path:
            self._write(path)

    def _write(self, path):
        try:
            # valida que o proprio codec consegue re-ler o que vai escrever
            data = self.save.to_bytes()
            decode_variant(data, 4)
            with open(path, "wb") as f:
                f.write(data)
            self.save.path = path
            self.path_label.setText(path)
            self.status.showMessage(f"Salvo em {path} ({len(data)} bytes)", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao salvar", str(e))

    # --- construcao das abas -------------------------------------------------

    def build_tabs(self):
        self.tabs.clear()
        self.bool_widgets = []
        self.chip_checkboxes = []

        def add(widget, name):
            icon = TAB_ICONS.get(name, "")
            self.tabs.addTab(widget, f"{icon}  {name}" if icon else name)

        add(self._build_group_tab(
            [("save_file_exists", "Save existe")] +
            [(k, pretty_label(k)) for k in LEVEL_KEYS],
            "Progresso dos niveis"
        ), "Niveis")

        add(self._build_group_tab(
            [(k, pretty_label(k)) for k in WEAPON_KEYS],
            "Armas desbloqueadas"
        ), "Armas")

        add(self._build_group_tab(
            [(k, pretty_label(k)) for k in HEART_KEYS] +
            [(k, pretty_label(k)) for k in ETANK_FLAG_KEYS] +
            [(k, pretty_label(k)) for k in ETANK_HEALTH_KEYS],
            "Coletaveis de vida e energia"
        ), "Coracoes && E-Tanks")

        add(self._build_group_tab(
            [(k, pretty_label(k)) for k in UPGRADE_KEYS],
            "Upgrades de equipamento"
        ), "Upgrades")

        add(self._build_group_tab(
            [(k, pretty_label(k)) for k in STAT_KEYS],
            "Estatisticas do jogador"
        ), "Estatisticas")

        add(self._build_group_tab(
            [(k, pretty_label(k)) for k in SETTING_KEYS],
            "Preferencias"
        ), "Config.")

        if self.save.has(ARRAY_KEY):
            add(self._build_chips_tab(), "Chips")

        other_tab = self._build_other_tab()
        if other_tab is not None:
            add(other_tab, "Outros campos")

        self.update_progress()

    def _build_group_tab(self, key_labels, group_title=None):
        area = QScrollArea()
        area.setWidgetResizable(True)
        outer_content = QWidget()
        outer_vbox = QVBoxLayout(outer_content)
        outer_vbox.setContentsMargins(2, 2, 2, 2)
        outer_vbox.setSpacing(12)

        box = QGroupBox(group_title or " ")
        form = QFormLayout(box)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)
        form.setContentsMargins(18, 18, 18, 16)
        any_field = False
        for key, label in key_labels:
            variant = self.save.get(key)
            if variant is None:
                continue
            any_field = True
            widget = make_field_widget(variant)
            if isinstance(widget, BoolField):
                self.bool_widgets.append(widget)
                widget.stateChanged.connect(self.update_progress)
            form.addRow(label + "  ", widget)
        outer_vbox.addWidget(box)
        outer_vbox.addStretch()
        if not any_field:
            box.setVisible(False)
        area.setWidget(outer_content)
        return area

    def _build_chips_tab(self):
        area = QScrollArea()
        area.setWidgetResizable(True)
        content = QWidget()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(2, 2, 2, 2)
        vbox.setSpacing(12)

        top = QHBoxLayout()
        info = QLabel(f"{len(self.save.get(ARRAY_KEY).value)} coletaveis")
        info.setObjectName("subtitle")
        btn_all = QPushButton("\u2714  Marcar todos")
        btn_none = QPushButton("Desmarcar todos")
        top.addWidget(info)
        top.addStretch()
        top.addWidget(btn_all)
        top.addWidget(btn_none)
        vbox.addLayout(top)

        box = QGroupBox("Chips coletados")
        grid = QGridLayout(box)
        grid.setSpacing(6)
        grid.setContentsMargins(18, 20, 18, 16)
        items = self.save.get(ARRAY_KEY).value
        cols = 12
        self.chip_checkboxes = []
        for i, item_variant in enumerate(items):
            cb = QPushButton(str(i))
            cb.setCheckable(True)
            cb.setChecked(bool(item_variant.value))
            cb.setFixedSize(34, 30)
            cb.setStyleSheet(self._chip_style(cb.isChecked()))
            cb.toggled.connect(
                lambda checked, v=item_variant, b=cb: self._on_chip_toggle(checked, v, b)
            )
            self.chip_checkboxes.append(cb)
            grid.addWidget(cb, i // cols, i % cols)
        vbox.addWidget(box)
        vbox.addStretch()
        area.setWidget(content)

        btn_all.clicked.connect(lambda: [cb.setChecked(True) for cb in self.chip_checkboxes])
        btn_none.clicked.connect(lambda: [cb.setChecked(False) for cb in self.chip_checkboxes])
        return area

    @staticmethod
    def _chip_style(checked):
        if checked:
            return f"""
                QPushButton {{ background: {GOOD}; border: 1px solid {GOOD};
                    border-radius: 6px; font-weight: 700; color: white; padding: 0; }}
                QPushButton:hover {{ background: #5cd260; }}
            """
        return f"""
            QPushButton {{ background: {BG}; border: 1px solid {BORDER};
                border-radius: 6px; font-weight: 600; color: {TEXT_DIM}; padding: 0; }}
            QPushButton:hover {{ border-color: {ACCENT}; }}
        """

    def _on_chip_toggle(self, checked, variant, button):
        variant.value = checked
        button.setStyleSheet(self._chip_style(checked))
        self.update_progress()

    def _build_other_tab(self):
        known = ALL_KNOWN
        remaining = [k for k in self.save.keys() if k not in known]
        if not remaining:
            return None
        return self._build_group_tab(
            [(k, pretty_label(k)) for k in remaining], "Campos nao categorizados"
        )

    # --- acoes de conveniencia -----------------------------------------------

    def unlock_everything(self):
        if not self.save:
            return

        def set_bool(key, val):
            v = self.save.get(key)
            if v is not None:
                v.value = val

        def set_int(key, val):
            v = self.save.get(key)
            if v is not None:
                v.value = val

        for key in LEVEL_KEYS + WEAPON_KEYS + HEART_KEYS + ETANK_FLAG_KEYS + UPGRADE_KEYS:
            set_bool(key, True)

        hearts_v = self.save.get("hearts")
        n_hearts = len(HEART_KEYS) if hearts_v is not None else 0
        set_int("hearts", n_hearts)
        set_int("etanks", len(ETANK_FLAG_KEYS))

        max_health = 16 + 2 * n_hearts
        set_int("max_health", max_health)
        for key in ETANK_HEALTH_KEYS:
            set_int(key, max_health)

        if self.save.has(ARRAY_KEY):
            for item in self.save.get(ARRAY_KEY).value:
                item.value = True

        self.build_tabs()
        self.status.showMessage("Tudo desbloqueado (lembre de Salvar)", 5000)

    def reset_everything(self):
        if not self.save:
            return
        reply = QMessageBox.question(
            self, "Zerar tudo",
            "Isso vai desmarcar todos os niveis, armas, coracoes, E-Tanks, "
            "upgrades e chips. Continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for key in (LEVEL_KEYS + WEAPON_KEYS + HEART_KEYS + ETANK_FLAG_KEYS
                    + UPGRADE_KEYS):
            v = self.save.get(key)
            if v is not None:
                v.value = False
        for key in ("hearts", "etanks"):
            v = self.save.get(key)
            if v is not None:
                v.value = 0
        for key in ETANK_HEALTH_KEYS:
            v = self.save.get(key)
            if v is not None:
                v.value = 0
        v = self.save.get("max_health")
        if v is not None:
            v.value = 16
        if self.save.has(ARRAY_KEY):
            for item in self.save.get(ARRAY_KEY).value:
                item.value = False

        self.build_tabs()
        self.status.showMessage("Tudo zerado (lembre de Salvar)", 5000)

    # --- progresso -------------------------------------------------------

    def update_progress(self):
        if not self.save:
            self.progress.setValue(0)
            return
        keys = LEVEL_KEYS + WEAPON_KEYS + HEART_KEYS + ETANK_FLAG_KEYS + UPGRADE_KEYS
        total = 0
        done = 0
        for key in keys:
            v = self.save.get(key)
            if v is not None:
                total += 1
                done += 1 if v.value else 0
        if self.save.has(ARRAY_KEY):
            chips = self.save.get(ARRAY_KEY).value
            total += len(chips)
            done += sum(1 for item in chips if item.value)
        pct = int(round(100 * done / total)) if total else 0
        self.progress.setValue(pct)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    win = MainWindow(initial)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
