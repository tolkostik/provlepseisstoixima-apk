"""
Στοίχημα – ανάλυση πιθανοτήτων ποδοσφαίρου και μπάσκετ (νέα εμφάνιση).
Καρτέλες: Σήμερα · Αγώνες · Δελτίο · Ιστορικό · Ρυθμίσεις.
"""
import datetime
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import NoTransition, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import betting as B
import model as M
import ui_widgets as UW

TABS = ("today", "matches", "slip", "history", "settings")
TITLES = {"today": "Σήμερα", "matches": "Αγώνες", "slip": "Δελτίο", "history": "Ιστορικό & απόδοση",
          "settings": "Ρυθμίσεις", "match": "Αγώνας"}
GREEN, RED, AMBER, BLUE = UW.GOOD, UW.BAD, UW.WARN, (0.25, 0.55, 0.95, 1)
REL_RGBA = {"Υψηλή": UW.GOOD, "Μέτρια": (0.25, 0.55, 0.95, 1), "Χαμηλή": UW.BAD}
FOOT = ("Δεν υπάρχει σίγουρο αποτέλεσμα: ένα σημείο 80% χάνει 1 στις 5. Μακροπρόθεσμα κερδίζει μόνο όποιος "
        "παίζει αποδόσεις μεγαλύτερες από τις δίκαιες. Παίζε μόνο σε εταιρείες με άδεια ΕΕΕΠ και μόνο ποσά που "
        "αντέχεις να χάσεις. Αν το παιχνίδι γίνει πρόβλημα, υπάρχει βοήθεια (π.χ. ΚΕΘΕΑ ΑΛΦΑ).")

KV = """
#:import dp kivy.metrics.dp

<NavItem>:
    orientation: 'vertical'
    padding: 0, dp(6)
    spacing: dp(2)

<Root>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: app.c_bg
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        size_hint_y: None
        height: dp(58)
        padding: dp(8), dp(6)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size
                texture: app.grad
        Button:
            text: '<'
            bold: True
            font_size: '24sp'
            size_hint_x: None
            width: dp(46) if app.can_back else 0
            opacity: 1 if app.can_back else 0
            disabled: not app.can_back
            background_normal: ''
            background_color: 1, 1, 1, 0.15
            on_release: app.back()
        Label:
            text: app.title_text
            bold: True
            font_size: '20sp'
            halign: 'left'
            valign: 'middle'
            text_size: self.size
            shorten: True
    ScreenManager:
        id: sm
    BoxLayout:
        id: undo_bar
        size_hint_y: None
        height: 0
        opacity: 0
        padding: dp(8), dp(4)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: 0.15, 0.17, 0.24, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            id: undo_lbl
            halign: 'left'
            valign: 'middle'
            text_size: self.size
        Button:
            id: undo_btn
            text: 'ΑΝΑΙΡΕΣΗ'
            bold: True
            size_hint_x: None
            width: dp(120)
            background_normal: ''
            background_color: 0.96, 0.62, 0.0, 1
    BoxLayout:
        id: nav
        size_hint_y: None
        height: dp(64)
        canvas.before:
            Color:
                rgba: app.c_card
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: app.c_line
            Rectangle:
                pos: self.x, self.top - dp(1)
                size: self.width, dp(1)
"""


class NavItem(ButtonBehavior, BoxLayout):
    pass


class Root(BoxLayout):
    pass


class Tap(ButtonBehavior, BoxLayout):
    pass


# ------------------------------------------------------------------ προστασία από κλεισίματα
from kivy.base import ExceptionHandler, ExceptionManager  # noqa: E402


class _Guard(ExceptionHandler):
    def handle_exception(self, inst):
        try:
            import traceback
            B.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(B.DATA_DIR / "errors.log", "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%d/%m %H:%M ") + "".join(
                    traceback.format_exception(type(inst), inst, inst.__traceback__))[-1500:] + "\n")
        except Exception:  # noqa: BLE001
            pass
        return ExceptionManager.PASS


ExceptionManager.add_handler(_Guard())


def esc(t):
    return str(t).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def gr(x):
    t = f"{x:.1f}".replace(".", ",")
    return t[:-2] if t.endswith(",0") else t


def euro(x):
    return f"{x:.2f}".replace(".", ",") + " €"




def pct(x):
    return f"{x * 100:.0f}%"


def num(x):
    return f"{x:.2f}".replace(".", ",")


class StoiximaApp(App):
    title = "Stoixima"
    c_bg = ListProperty([0.055, 0.07, 0.10, 1])
    c_card = ListProperty([0.10, 0.125, 0.17, 1])
    c_line = ListProperty([0.18, 0.21, 0.28, 1])
    grad = ObjectProperty(None, allownone=True)
    can_back = BooleanProperty(False)
    title_text = StringProperty("Σήμερα")

    # ================================================================== εκκίνηση
    def build(self):
        B.set_dir(self.user_data_dir)
        self.s = {**B.DEFAULTS, "bankroll": 100.0, "risk": "Συντηρητικό", "week_limit": 10, "use_model": True,
                  "theme": "dark", **B.load_settings()}
        UW.set_theme(self.s.get("theme", "dark"))
        self.c_bg, self.c_card, self.c_line = list(UW.C["bg"]), list(UW.C["card"]), list(UW.C["line"])
        Window.clearcolor = UW.C["bg"]
        self.grad = UW.gradient(UW.PRIMARY, UW.PRIMARY2)
        Builder.load_string(KV)
        self.root_w = Root()
        self.sm = self.root_w.ids.sm
        self.sm.transition = NoTransition()
        self.pages = {}
        for name in TITLES:
            scr = Screen(name=name)
            sv = ScrollView(do_scroll_x=False, bar_width=dp(4))
            box = BoxLayout(orientation="vertical", size_hint_y=None, padding=(dp(12), dp(12)), spacing=dp(12))
            box.bind(minimum_height=box.setter("height"))
            sv.add_widget(box)
            scr.add_widget(sv)
            self.sm.add_widget(scr)
            self.pages[name] = (sv, box)
        self.nav_items = {}
        for key, icon, label in (("today", "home", "Σήμερα"), ("matches", "ball", "Αγώνες"), ("slip", "ticket", "Δελτίο"),
                                 ("history", "chart", "Ιστορικό"), ("settings", "gear", "Ρυθμίσεις")):
            it = NavItem()
            ic = UW.Icon(kind=icon, size_hint_y=None, height=dp(26))
            lb = Label(text=label, font_size=sp(11), size_hint_y=None, height=dp(18))
            it.add_widget(ic)
            it.add_widget(lb)
            it.icon, it.lab = ic, lb
            it.bind(on_release=lambda w, k=key: self.tab(k))
            self.root_w.ids.nav.add_widget(it)
            self.nav_items[key] = it
        self.models = B._read("models.json", {})
        self.busy = False
        self.settle_busy = False
        self._token = 0
        self.stack = []
        self.slip_mode = "Αυτόματο"
        self.manual = B._read("manual_slip.json", [])
        self.filters = {"sport": "Όλα", "day": "Όλες"}
        self.status_msg = ""
        Window.bind(on_keyboard=self._key)
        self.tab("today")
        cache = B.load_cache()
        stale = True
        if cache.get("updated"):
            try:
                t = datetime.datetime.strptime(cache["updated"], "%d/%m/%Y %H:%M")
                stale = datetime.datetime.now() - t > datetime.timedelta(hours=6)
            except ValueError:
                pass
        if stale:
            Clock.schedule_once(lambda dt: self.update(), 0.8)
        return self.root_w

    def on_pause(self):
        return True

    # ================================================================== πλοήγηση
    def page(self, name):
        sv, box = self.pages[name]
        box.clear_widgets()
        sv.scroll_y = 1
        return box

    def show(self, name, push=True):
        if push and self.sm.current != name:
            self.stack.append(self.sm.current)
        self.sm.current = name
        self.title_text = TITLES.get(name, "Στοίχημα")
        self.can_back = name not in TABS
        tab = name if name in TABS else (self.stack[0] if self.stack and self.stack[0] in TABS else "today")
        for k, it in self.nav_items.items():
            on = k == tab
            col = UW.PRIMARY if on else UW.C["muted"]
            it.icon.rgba = list(col)
            it.lab.color = col
            it.lab.bold = on

    def tab(self, name):
        self.stack = []
        getattr(self, "build_" + name)()
        self.show(name, push=False)

    def back(self):
        if not self.stack:
            return False
        prev = self.stack.pop()
        if prev in TABS:
            getattr(self, "build_" + prev)()
        self.show(prev, push=False)
        return True

    def _key(self, win, key, *a):
        if key == 27:
            return self.back()
        return False

    def refresh_current(self):
        cur = self.sm.current
        if cur in TABS:
            getattr(self, "build_" + cur)()

    # ================================================================== στοιχεία
    def card(self, box, pad=14):
        c = UW.CardBox(pad=pad)
        box.add_widget(c)
        return c

    def btn(self, parent, text, cb, color=None, fg=(1, 1, 1, 1), h=50):
        b = Button(text=text, bold=True, size_hint_y=None, height=dp(h), background_normal="",
                   background_color=color or UW.PRIMARY, color=fg, font_size=sp(15))
        b.bind(on_release=lambda *a: cb())
        parent.add_widget(b)
        return b

    def ghost(self, parent, text, cb, h=44):
        return self.btn(parent, text, cb, color=UW.C["line"], fg=UW.C["ink"], h=h)

    def chips(self, parent, items, h=30):
        row = BoxLayout(size_hint_y=None, height=dp(h), spacing=dp(6))
        for t, col in items:
            row.add_widget(UW.Chip(t, col))
        row.add_widget(Widget())
        parent.add_widget(row)
        return row

    def seg(self, parent, options, current, cb):
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        for opt in options:
            on = opt == current
            b = Button(text=opt, bold=on, background_normal="", font_size=sp(13),
                       background_color=UW.PRIMARY if on else UW.C["line"], color=(1, 1, 1, 1) if on else UW.C["ink"])
            b.bind(on_release=lambda w, o=opt: cb(o))
            row.add_widget(b)
        parent.add_widget(row)

    # ================================================================== ανάλυση
    def upcoming(self):
        return B.upcoming(B.load_cache(), self.s)

    def enrich_pick(self, m, p):
        mp = M.model_prob(self.models, m, p["sign"]) if self.s.get("use_model") else None
        ap = B.consensus(m, p["sign"])
        rs, rl, why = M.reliability(m, p, mp, ap)
        return {"model": mp, "alt": ap, "rel": rs, "rel_label": rl, "why": why}

    def enrich(self, items):
        return [(m, p, self.enrich_pick(m, p)) for m, p in items]

    def auto_slip(self, ups, greek=False):
        pool_m = [m for m in ups if M.is_greek(m)] if greek else ups
        stds = B.standards(pool_m, self.s)
        if greek and len(stds) < int(self.s["slip"]):
            stds = B.standards(pool_m, {**self.s, "min_prob": 50})
        rich = [x for x in self.enrich(stds) if not x[1].get("double")]
        good = sorted([x for x in rich if x[2]["rel"] >= 45], key=lambda x: -x[1]["prob"])
        rest = sorted([x for x in rich if x[2]["rel"] < 45], key=lambda x: -x[1]["prob"])
        return (good + rest)[: max(1, int(self.s["slip"]))]

    def pick_card(self, parent, m, p, ex, on_tap=None, show_add=True):
        """Κάρτα επιλογής: δαχτυλίδι πιθανότητας, αγώνας, σημείο, αξιοπιστία."""
        r = Tap(orientation="horizontal", size_hint_y=None, height=dp(96), spacing=dp(12), padding=(dp(10), dp(10)))

        def bg(*a):
            r.canvas.before.clear()
            with r.canvas.before:
                Color(*UW.C["card"])
                RoundedRectangle(pos=r.pos, size=r.size, radius=[dp(16)])
        r.bind(pos=bg, size=bg)
        ring = UW.ScoreRing(size_hint=(None, None), size=(dp(70), dp(70)), thickness=dp(6), text_size_sp=17,
                            percent=True, color_override=list(REL_RGBA.get(ex["rel_label"], UW.PRIMARY)))
        ring.set_score(p["prob"] * 100, animate=False)
        a = AnchorLayout(size_hint_x=None, width=dp(72))
        a.add_widget(ring)
        r.add_widget(a)
        col = BoxLayout(orientation="vertical")
        t = Label(text=f"[b]{esc(m['home'])} – {esc(m['away'])}[/b]", markup=True, color=UW.C["ink"], font_size=sp(14),
                  halign="left", valign="middle", shorten=True)
        t.bind(size=lambda w, s: setattr(w, "text_size", s))
        sport = "Ποδόσφαιρο" if m["sport"] == "football" else "Μπάσκετ"
        sub = Label(text=f"{esc(m['league'])} · {B.local_time(m)}", color=UW.C["muted"], font_size=sp(11),
                    halign="left", valign="middle", shorten=True)
        sub.bind(size=lambda w, s: setattr(w, "text_size", s))
        rel_col = UW.hexc(REL_RGBA.get(ex["rel_label"], UW.PRIMARY))
        sign = Label(text=f"[b][size=18sp]{esc(p['sign'])}[/size][/b]  {esc(p['name'])}   "
                          f"[color={rel_col}]αξιοπιστία {ex['rel_label'].lower()}[/color]",
                     markup=True, color=UW.C["ink"], font_size=sp(12), halign="left", valign="middle", shorten=True)
        sign.bind(size=lambda w, s: setattr(w, "text_size", s))
        col.add_widget(t)
        col.add_widget(sub)
        col.add_widget(sign)
        r.add_widget(col)
        if show_add:
            add = Button(text="+", bold=True, font_size=sp(22), size_hint_x=None, width=dp(42), background_normal="",
                         background_color=UW.C["line"], color=UW.PRIMARY)
            add.bind(on_release=lambda *x: self.add_manual(m, p))
            r.add_widget(add)
        r.bind(on_release=lambda *x: (on_tap or (lambda: self.open_match(m)))())
        parent.add_widget(r)
        _ = sport
        return r

    # ================================================================== ενημέρωση
    def update(self):
        if self.busy:
            return
        self.busy = True
        self._token += 1
        token = self._token
        self.status_msg = "Ενημέρωση από όλες τις πηγές…"
        self.refresh_current()

        def watchdog(dt):
            if self.busy and self._token == token:
                self.busy = False
                self.status_msg = "Η ενημέρωση άργησε πολύ (αργή σύνδεση;). Δοκίμασε ξανά."
                self.refresh_current()
        Clock.schedule_once(watchdog, 90)

        def log(msg):
            def put(dt):
                self.status_msg = msg
                lbl = getattr(self, "_status_lbl", None)
                if lbl is not None:
                    lbl.text = msg
            Clock.schedule_once(put)

        def work():
            err = None
            try:
                data = B.fetch_all(self.s, log)
                if self.s.get("use_model"):
                    ups = B.upcoming(data, self.s)
                    models = M.build_models(ups, log)
                    B._write("models.json", models)
                    self.models = models
                if data.get("notes"):
                    err = "Μερική ενημέρωση: " + data["notes"][0]
            except Exception as e:  # noqa: BLE001
                err = "Σφάλμα: " + str(e)[:120]
            Clock.schedule_once(lambda dt: done(err) if self._token == token else None)

        def done(err):
            self.busy = False
            self.status_msg = err or ""
            self.refresh_current()
        threading.Thread(target=work, daemon=True).start()

    # ================================================================== ΣΗΜΕΡΑ
    def build_today(self):
        box = self.page("today")
        cache = B.load_cache()
        ups = self.upcoming()
        stds = self.enrich(B.standards(ups, self.s))
        vals = self.enrich(B.value_picks(ups, self.s))
        hero = BoxLayout(orientation="vertical", size_hint_y=None, padding=(dp(16), dp(16)), spacing=dp(8))
        hero.bind(minimum_height=hero.setter("height"))

        def hbg(*a):
            hero.canvas.before.clear()
            with hero.canvas.before:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=hero.pos, size=hero.size, radius=[dp(22)], texture=self.grad)
        hero.bind(pos=hbg, size=hbg)
        hero.add_widget(UW.text("[b]Η ανάλυση της ημέρας[/b]", size=20, color=(1, 1, 1, 1)))
        stats = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        for n, label in ((len(ups), "αγώνες"), (len(stds), "σταντάρ"), (len(vals), "με αξία")):
            st = BoxLayout(orientation="vertical")
            st.add_widget(Label(text=f"[b]{n}[/b]", markup=True, font_size=sp(26), color=(1, 1, 1, 1)))
            st.add_widget(Label(text=label, font_size=sp(12), color=(1, 1, 1, 0.85)))
            stats.add_widget(st)
        hero.add_widget(stats)
        upd = (f"Ενημέρωση: {cache['updated']}" if cache.get("updated") else "Δεν έχει γίνει ενημέρωση")
        self._status_lbl = UW.text(self.status_msg or upd, size=12, color=(1, 1, 1, 0.9))
        hero.add_widget(self._status_lbl)
        b = Button(text="Ενημέρωση…" if self.busy else "ΕΝΗΜΕΡΩΣΗ ΤΩΡΑ", bold=True, size_hint_y=None, height=dp(46),
                   background_normal="", background_color=(1, 1, 1, 0.22), disabled=self.busy)
        b.bind(on_release=lambda *a: self.update())
        hero.add_widget(b)
        box.add_widget(hero)

        st = M.stats()
        bank = M.bankroll_now(self.s)
        c = self.card(box)
        c.add_widget(UW.text("[b]Το κεφάλαιό μου[/b]", size=15))
        pc = GREEN if st["profit"] >= 0 else RED
        c.add_widget(UW.text(f"[size=24sp][b]{num(bank)} €[/b][/size]   [color={UW.hexc(pc)}]"
                             f"{'+' if st['profit'] >= 0 else ''}{num(st['profit'])} €[/color]"))
        limit = bank * float(self.s.get("week_limit", 10)) / 100
        spent = M.week_spent()
        c.add_widget(UW.NutrientBar("Αυτή την εβδομάδα", num(spent), f" € από {num(limit)} €",
                                    "υψηλή" if spent > limit * 0.8 else ("μέτρια" if spent > limit * 0.5 else "χαμηλή"),
                                    max(limit, 0.01)))

        top = [x for x in stds if x[2]["rel"] >= 70][:5] or stds[:5]
        box.add_widget(UW.text("[b]Κορυφαίες επιλογές[/b]  [size=12sp](πιθανότερες, υψηλή αξιοπιστία)[/size]", size=16))
        if not top:
            box.add_widget(UW.text("Δεν υπάρχουν ακόμα επιλογές. Πάτα «Ενημέρωση τώρα».", color=UW.C["muted"]))
        for m, p, ex in top:
            self.pick_card(box, m, p, ex)
        if vals:
            box.add_widget(UW.text("[b]Ευκαιρίες αξίας[/b]  [size=12sp](απόδοση πάνω από τη δίκαιη)[/size]", size=16))
            for m, p, ex in vals[:3]:
                self.pick_card(box, m, p, ex)
        self.btn(box, "ΦΤΙΑΞΕ ΔΕΛΤΙΟ", lambda: self.tab("slip"))
        box.add_widget(UW.text(FOOT, size=11, color=UW.C["muted"]))

    # ================================================================== ΑΓΩΝΕΣ
    def build_matches(self):
        box = self.page("matches")
        self.seg(box, ["Όλα", "Ποδόσφαιρο", "Μπάσκετ", "Ελλάδα", "UEFA"], self.filters["sport"],
                 lambda o: (self.filters.__setitem__("sport", o), self.build_matches()))
        self.seg(box, ["Σήμερα", "Αύριο", "Όλες"], self.filters["day"],
                 lambda o: (self.filters.__setitem__("day", o), self.build_matches()))
        ups = self.upcoming()
        f = self.filters["sport"]
        if f == "Ποδόσφαιρο":
            ups = [m for m in ups if m["sport"] == "football"]
        elif f == "Μπάσκετ":
            ups = [m for m in ups if m["sport"] == "basketball"]
        elif f == "Ελλάδα":
            ups = [m for m in ups if M.is_greek(m)]
        elif f == "UEFA":
            ups = [m for m in ups if m.get("uefa")]
        day = self.filters["day"]
        if day != "Όλες":
            target = datetime.date.today() + datetime.timedelta(days=0 if day == "Σήμερα" else 1)
            ups = [m for m in ups if B._start(m) and B._start(m).astimezone().date() == target]
        if not ups:
            box.add_widget(UW.text("Δεν υπάρχουν αγώνες με αυτά τα φίλτρα.", color=UW.C["muted"]))
            return
        leagues = {}
        for m in ups:
            leagues.setdefault(m["league"], []).append(m)
        shown = 0
        for lg in sorted(leagues, key=lambda k: (not k.startswith("UEFA"), not k.startswith("Ελλάδα"), k)):
            box.add_widget(UW.text(f"[b]{esc(lg)}[/b]  [size=11sp]({len(leagues[lg])})[/size]", size=15))
            for m in leagues[lg][:25]:
                ps = [p for p in B.picks_for(m, self.s["overunder"]) if not p.get("double")]
                best = max(ps, key=lambda p: p["prob"])
                self.pick_card(box, m, best, self.enrich_pick(m, best))
                shown += 1
            if shown > 120:
                box.add_widget(UW.text("Εμφανίζονται οι πρώτοι 120 αγώνες. Χρησιμοποίησε τα φίλτρα.",
                                       color=UW.C["muted"], size=12))
                break

    # ================================================================== ΑΓΩΝΑΣ
    def open_match(self, m):
        box = self.page("match")
        c = self.card(box)
        c.add_widget(UW.text(f"[b]{esc(m['home'])}[/b]\nκατά\n[b]{esc(m['away'])}[/b]", size=19, halign="center"))
        c.add_widget(UW.text(f"{esc(m['league'])} · {B.local_time(m)}", size=12, color=UW.C["muted"],
                             halign="center"))
        srcs = [(s_, BLUE) for s_ in (m.get("sources") or [])]
        if m.get("pin"):
            srcs.append(("Pinnacle", GREEN))
        self.chips(c, srcs)
        fh, fa = M.team_form(self.models, m)
        if fh or fa:
            def fchips(team, f):
                row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
                lab = Label(text=team, color=UW.C["ink"], font_size=sp(12), size_hint_x=0.45, halign="left",
                            valign="middle", shorten=True)
                lab.bind(size=lambda w, s: setattr(w, "text_size", s))
                row.add_widget(lab)
                for ch in (f or ""):
                    row.add_widget(UW.Chip(ch, GREEN if ch == "Ν" else (RED if ch == "Η" else UW.C["muted"])))
                row.add_widget(Widget())
                return row
            c.add_widget(UW.text("[b]Φόρμα[/b] (τελευταίοι 5, πιο πρόσφατος αριστερά)", size=13))
            c.add_widget(fchips(m["home"], fh))
            c.add_widget(fchips(m["away"], fa))
        picks = B.picks_for(m, self.s["overunder"])
        groups = [("Τελικό αποτέλεσμα", [p for p in picks if p["sign"] in ("1", "Χ", "2")]),
                  ("Διπλή ευκαιρία", [p for p in picks if p.get("double")]),
                  ("Γκολ", [p for p in picks if p["sign"].startswith(("Over", "Under"))])]
        for title, ps in groups:
            if not ps:
                continue
            cc = self.card(box)
            cc.add_widget(UW.text(f"[b]{title}[/b]", size=15))
            for p in ps:
                ex = self.enrich_pick(m, p)
                row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
                info = []
                if ex["model"] is not None:
                    info.append(f"μοντέλο {pct(ex['model'])}")
                if ex["alt"] is not None:
                    info.append(f"2η πηγή {pct(ex['alt'])}")
                if p.get("best"):
                    info.append(f"καλύτερη {num(p['best'])}")
                bar = UW.NutrientBar(f"{p['sign']}  {p['name']}", pct(p['prob']), f"   δίκαιη {num(p['fair_odds'])}",
                                     None, 1.0)
                bar.children[-1].text += (f"\n[size=11sp][color={UW.hexc(UW.C['muted'])}]{' · '.join(info)}"
                                          f"[/color][/size]" if info else "")
                bar.height = dp(56)
                bar.children[-1].height = dp(36)
                row.add_widget(bar)
                add = Button(text="+", bold=True, font_size=sp(22), size_hint_x=None, width=dp(44),
                             background_normal="", background_color=UW.C["line"], color=UW.PRIMARY)
                add.bind(on_release=lambda w, pp=p: self.add_manual(m, pp))
                row.add_widget(add)
                cc.add_widget(row)
                self._fill_bar(bar, p["prob"], REL_RGBA.get(ex["rel_label"], UW.PRIMARY))
        best = max([p for p in picks if not p.get("double")], key=lambda p: p["prob"])
        ex = self.enrich_pick(m, best)
        rc = self.card(box)
        rc.add_widget(UW.text(f"[b]Αξιοπιστία εκτίμησης: [color={UW.hexc(REL_RGBA[ex['rel_label']])}]"
                              f"{ex['rel_label']} ({ex['rel']}/100)[/color][/b]", size=14))
        if ex["why"]:
            rc.add_widget(UW.text(" · ".join(ex["why"]), size=12, color=UW.C["muted"]))
        box.add_widget(UW.text(FOOT, size=11, color=UW.C["muted"]))
        self.show("match")

    def _fill_bar(self, bar, frac, col):
        """Επαναχρωματισμός της μπάρας με το χρώμα της αξιοπιστίας."""
        w = bar.bar

        def draw(*a):
            w.canvas.clear()
            with w.canvas:
                Color(*UW.C["line"])
                RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(6)])
                Color(*col)
                RoundedRectangle(pos=w.pos, size=(w.width * max(0.02, min(1, frac)), w.height), radius=[dp(6)])
        w.bind(pos=draw, size=draw)
        Clock.schedule_once(draw, 0.1)

    # ================================================================== ΔΕΛΤΙΟ
    def add_manual(self, m, p):
        key = (m["home"], m["away"], m["start"][:10])
        self.manual = [x for x in self.manual if (x["m"]["home"], x["m"]["away"], x["m"]["start"][:10]) != key]
        self.manual.append({"m": m, "p": p})
        B._write("manual_slip.json", self.manual)
        self.slip_mode = "Δικό μου"
        self.status_msg = f"Μπήκε στο δελτίο: {m['home']} – {m['away']} ({p['sign']})"

    def build_slip(self):
        box = self.page("slip")
        self.seg(box, ["Αυτόματο", "Ελληνικό", "Δικό μου"], self.slip_mode,
                 lambda o: (setattr(self, "slip_mode", o), self.build_slip()))
        ups = self.upcoming()
        if self.slip_mode == "Δικό μου":
            now = datetime.datetime.now(datetime.timezone.utc)
            self.manual = [x for x in self.manual if B._start(x["m"]) and B._start(x["m"]) > now]
            chosen = [(x["m"], x["p"], self.enrich_pick(x["m"], x["p"])) for x in self.manual]
            if not chosen:
                box.add_widget(UW.text("Το δελτίο σου είναι άδειο. Πάτα «+» σε μια επιλογή (Σήμερα, Αγώνες ή σελίδα "
                                       "αγώνα).", color=UW.C["muted"]))
        else:
            chosen = self.auto_slip(ups, greek=self.slip_mode == "Ελληνικό")
            if not chosen:
                box.add_widget(UW.text("Δεν υπάρχουν αρκετοί αγώνες. Πάτα ενημέρωση ή άλλαξε τις ρυθμίσεις.",
                                       color=UW.C["muted"]))
        for m, p, ex in chosen:
            card = self.pick_card(box, m, p, ex, show_add=False)
            if self.slip_mode == "Δικό μου":
                rm = Button(text="x", size_hint_x=None, width=dp(40), background_normal="",
                            background_color=UW.C["line"], color=RED)
                rm.bind(on_release=lambda w, mm=m: self._rm_manual(mm))
                card.add_widget(rm)
        if not chosen:
            return
        prob, fair = 1.0, 1.0
        for _, p, _ in chosen:
            prob *= p["prob"]
            fair *= p["fair_odds"]
        c = self.card(box)
        row = BoxLayout(size_hint_y=None, height=dp(110), spacing=dp(12))
        ring = UW.ScoreRing(size_hint=(None, None), size=(dp(104), dp(104)), thickness=dp(9), text_size_sp=24,
                            percent=True)
        Clock.schedule_once(lambda dt: ring.set_score(prob * 100), 0.05)
        a = AnchorLayout(size_hint_x=None, width=dp(108))
        a.add_widget(ring)
        row.add_widget(a)
        info = BoxLayout(orientation="vertical")
        info.add_widget(UW.text(f"[b]Πιθανότητα να βγει όλο[/b]\n{len(chosen)} επιλογές", size=14))
        info.add_widget(UW.text(f"Δίκαιη συνολική απόδοση: [b]{num(fair)}[/b]", size=14))
        row.add_widget(info)
        c.add_widget(row)
        c.add_widget(UW.text(f"Αν ο ΟΠΑΠ δίνει πάνω από {num(fair)}, το δελτίο έχει αξία. Αν δίνει λιγότερο, "
                             f"μακροπρόθεσμα χάνεις.", size=12, color=UW.C["muted"]))
        c2 = self.card(box)
        c2.add_widget(UW.text(f"[b]Πόσα να ποντάρω[/b]   κεφάλαιο {num(M.bankroll_now(self.s))} € · "
                              f"{self.s.get('risk')}", size=14))
        r2 = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        odds_in = TextInput(hint_text="Συνολική απόδοση ΟΠΑΠ", input_filter="float", multiline=False)
        stake_in = TextInput(hint_text="Ποσό €", input_filter="float", multiline=False)
        r2.add_widget(odds_in)
        r2.add_widget(stake_in)
        c2.add_widget(r2)
        advice = UW.text("", size=13)
        c2.add_widget(advice)

        def recalc(*a):
            try:
                o = float(odds_in.text.replace(",", ".")) if odds_in.text else None
            except ValueError:
                o = None
            stv, note, left = M.suggest_stake(self.s, prob, o)
            stake_in.text = f"{stv:g}"
            advice.text = f"Πρόταση: [b]{num(stv)} €[/b]. {esc(note)}"
        odds_in.bind(text=recalc)
        recalc()

        def save():
            try:
                stv = float(stake_in.text.replace(",", ".") or 0)
                o = float(odds_in.text.replace(",", ".")) if odds_in.text else fair
            except ValueError:
                return
            M.add_slip([M.pick_record(m, p, ex["model"], ex["rel"]) for m, p, ex in chosen], stv, o, self.slip_mode)
            if self.slip_mode == "Δικό μου":
                self.manual = []
                B._write("manual_slip.json", [])
            self.tab("history")
        self.btn(c2, "ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ ΙΣΤΟΡΙΚΟ", save, color=GREEN)
        box.add_widget(UW.text(FOOT, size=11, color=UW.C["muted"]))

    def _rm_manual(self, m):
        key = (m["home"], m["away"], m["start"][:10])
        self.manual = [x for x in self.manual if (x["m"]["home"], x["m"]["away"], x["m"]["start"][:10]) != key]
        B._write("manual_slip.json", self.manual)
        self.build_slip()

    # ================================================================== ΙΣΤΟΡΙΚΟ
    def build_history(self):
        box = self.page("history")
        st = M.stats()
        bank = M.bankroll_now(self.s)
        c = self.card(box)
        row = BoxLayout(size_hint_y=None, height=dp(70))
        for v, label, col in ((f"{num(bank)} €", "κεφάλαιο", UW.C["ink"]),
                              (f"{'+' if st['profit'] >= 0 else ''}{num(st['profit'])} €", "κέρδος/ζημιά",
                               GREEN if st["profit"] >= 0 else RED),
                              (f"{st['won']}/{st['settled']}", "κερδισμένα", UW.C["ink"])):
            b = BoxLayout(orientation="vertical")
            b.add_widget(Label(text=f"[b]{v}[/b]", markup=True, color=col, font_size=sp(19)))
            b.add_widget(Label(text=label, color=UW.C["muted"], font_size=sp(11)))
            row.add_widget(b)
        c.add_widget(row)
        if st.get("clv_n"):
            share = st["clv_pos"] / st["clv_n"]
            c.add_widget(UW.text(f"[b]Κίνηση γραμμής:[/b] σε {st['clv_pos']} από {st['clv_n']} επιλογές ({pct(share)}) η "
                                 f"αγορά κινήθηκε προς τη δική σου επιλογή μέχρι την έναρξη. Πάνω από 50% σημαίνει ότι "
                                 f"διαλέγεις καλά, ακόμα κι όταν η τύχη δεν βοηθά.", size=13))
        if st["buckets"]:
            cc = self.card(box)
            cc.add_widget(UW.text("[b]Πόσο σωστές βγήκαν οι πιθανότητες[/b]", size=15))
            for lo, (n, w, ps) in st["buckets"].items():
                nb = UW.NutrientBar(f"Σημεία {lo}–{lo + 10}%", pct(w / n), f"  ({w}/{n}, αναμ. {pct(ps / n)})", None, 1.0)
                cc.add_widget(nb)
                self._fill_bar(nb, w / n, GREEN if w / n >= ps / n - 0.03 else AMBER)
        self.btn(box, "Έλεγχος αποτελεσμάτων…" if self.settle_busy else "ΕΛΕΓΧΟΣ ΑΠΟΤΕΛΕΣΜΑΤΩΝ", self.settle)
        if self.status_msg:
            box.add_widget(UW.text(self.status_msg, size=12, color=UW.C["muted"]))
        slips = M.load_slips()
        if not slips:
            box.add_widget(UW.text("Δεν έχεις αποθηκεύσει ακόμα δελτία.", color=UW.C["muted"]))
        for sl in slips[:60]:
            col = {"κέρδισε": GREEN, "χάθηκε": RED}.get(sl["status"], BLUE)
            cc = self.card(box, pad=12)
            self.chips(cc, [({"κέρδισε": "ΚΕΡΔΙΣΕ", "χάθηκε": "ΧΑΘΗΚΕ"}.get(sl["status"], "ΕΚΚΡΕΜΕΙ"), col),
                            (sl["kind"], UW.C["line"])])
            cc.add_widget(UW.text(f"{sl['date']} · ποσό {num(sl['stake'])} € · απόδοση {num(sl['odds'] or 0)}",
                                  size=12, color=UW.C["muted"]))
            for pk in sl["picks"]:
                mark = ("[color=#2FAE5A]ΝΑΙ[/color]" if pk.get("won") else "[color=#E03131]ΟΧΙ[/color]") \
                    if pk.get("won") is not None else "…"
                res = f" ({pk['result']})" if pk.get("result") else ""
                cc.add_widget(UW.text(f"{mark}  {esc(pk['home'])} – {esc(pk['away'])}: [b]{esc(pk['sign'])}[/b] "
                                      f"{pct(pk['prob'])}{res}", size=13))
            self.ghost(cc, "Διαγραφή", lambda sid=sl["id"]: (M.delete_slip(sid), self.build_history()), h=36)
        if any(s_["status"] == "εκκρεμεί" for s_ in slips) and not self.settle_busy and not getattr(self, "_auto_settled", 0):
            self._auto_settled = 1
            Clock.schedule_once(lambda dt: self.settle(), 0.5)

    def settle(self):
        if self.settle_busy:
            return
        self.settle_busy = True

        def work():
            try:
                n = M.settle_all()
                msg = f"Ενημερώθηκαν {n} αποτελέσματα." if n else ("Δεν υπάρχουν νέα αποτελέσματα (τα ποδοσφαιρικά "
                                                                   "ανεβαίνουν 2 φορές την εβδομάδα).")
            except Exception as e:  # noqa: BLE001
                msg = "Σφάλμα ελέγχου: " + str(e)[:80]
            Clock.schedule_once(lambda dt: done(msg))

        def done(msg):
            self.settle_busy = False
            self.status_msg = msg
            if self.sm.current == "history":
                self.build_history()
        threading.Thread(target=work, daemon=True).start()

    # ================================================================== ΡΥΘΜΙΣΕΙΣ
    def build_settings(self):
        box = self.page("settings")
        s = self.s
        w = {}

        def line(parent, label, widget):
            r = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
            lb = Label(text=label, color=UW.C["ink"], halign="left", valign="middle", font_size=sp(14))
            lb.bind(size=lambda x, v: setattr(x, "text_size", v))
            r.add_widget(lb)
            widget.size_hint_x = 0.42
            r.add_widget(widget)
            parent.add_widget(r)

        c = self.card(box)
        c.add_widget(UW.text("[b]Αγώνες[/b]", size=15))
        for key, label in (("football", "Ποδόσφαιρο (football-data + ESPN, με UEFA)"),
                           ("basketball", "Μπάσκετ (NBA, NCAA, WNBA)"), ("overunder", "Και Over/Under 2,5"),
                           ("use_model", "Στατιστικό μοντέλο και φόρμα")):
            cb = CheckBox(active=bool(s.get(key, True)), color=UW.C["ink"])
            w[key] = cb
            line(c, label, cb)
        for key, label, vals in (("hours", "Αγώνες των επόμενων ωρών", ["24", "48", "72", "120", "168"]),
                                 ("min_prob", "Ελάχιστη πιθανότητα «σταντάρ» %", ["55", "60", "65", "70", "75", "80", "85"]),
                                 ("slip", "Αγώνες στο αυτόματο δελτίο", ["1", "2", "3", "4", "5", "6"])):
            sp_ = Spinner(text=str(s[key]), values=vals)
            w[key] = sp_
            line(c, label, sp_)
        c2 = self.card(box)
        c2.add_widget(UW.text("[b]Διαχείριση κεφαλαίου[/b]", size=15))
        bank = TextInput(text=f"{float(s.get('bankroll', 100)):g}", input_filter="float", multiline=False)
        w["bankroll"] = bank
        line(c2, "Αρχικό κεφάλαιο (€)", bank)
        risk = Spinner(text=s.get("risk", "Συντηρητικό"), values=list(M.RISK))
        w["risk"] = risk
        line(c2, "Προφίλ ρίσκου", risk)
        wl = Spinner(text=str(s.get("week_limit", 10)), values=["5", "10", "15", "20", "30"])
        w["week_limit"] = wl
        line(c2, "Όριο εβδομάδας (% κεφαλαίου)", wl)
        c3 = self.card(box)
        c3.add_widget(UW.text("[b]Εμφάνιση[/b]", size=15))
        th = Spinner(text="Σκοτεινό" if s.get("theme", "dark") == "dark" else "Φωτεινό", values=["Σκοτεινό", "Φωτεινό"])
        w["theme"] = th
        line(c3, "Θέμα (με επανεκκίνηση)", th)
        msg = UW.text("", size=12, color=GREEN)

        def save():
            old = (s["football"], s["basketball"], s["hours"], s.get("use_model"))
            try:
                bv = float(w["bankroll"].text.replace(",", "."))
            except ValueError:
                bv = 100.0
            s.update(football=w["football"].active, basketball=w["basketball"].active,
                     overunder=w["overunder"].active, use_model=w["use_model"].active, hours=int(w["hours"].text),
                     min_prob=int(w["min_prob"].text), slip=int(w["slip"].text), bankroll=bv, risk=w["risk"].text,
                     week_limit=int(w["week_limit"].text), theme="dark" if w["theme"].text == "Σκοτεινό" else "light")
            B.save_settings(s)
            msg.text = "Αποθηκεύτηκε."
            if (s["football"], s["basketball"], s["hours"], s["use_model"]) != old:
                self.update()
        self.btn(box, "ΑΠΟΘΗΚΕΥΣΗ", save, color=GREEN)
        box.add_widget(msg)
        c4 = self.card(box)
        c4.add_widget(UW.text("[b]Πηγές[/b]", size=15))
        c4.add_widget(UW.text("Ποδόσφαιρο: football-data.co.uk (αποδόσεις Pinnacle και μέσος όρος αγοράς, ~40 "
                              "πρωταθλήματα) + ESPN (Champions/Europa/Conference League, Super League και 5 μεγάλα "
                              "πρωταθλήματα, ως δεύτερη γνώμη). Μπάσκετ: ESPN. Μοντέλο Poisson και φόρμα από τα "
                              "αποτελέσματα της σεζόν. Κίνηση γραμμής από τις αποδόσεις κλεισίματος.",
                              size=12, color=UW.C["muted"]))
        box.add_widget(UW.text(FOOT, size=11, color=UW.C["muted"]))


if __name__ == "__main__":
    StoiximaApp().run()
