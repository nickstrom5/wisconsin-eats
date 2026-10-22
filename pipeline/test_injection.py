"""Tests for injection.py: planted links must fire, ordinary restaurant markup must not.
Run: ../.venv/bin/python test_injection.py   (exits 1 on any failure)

The page is a synthetic copy of Club Oasis's hacked home page (2026-10-12): the real one hid a Polish casino link in a block at
left:-5466px. The spam host here is fictional, so this repo carries no real spam link.
"""
import sys

import injection as D

H, F, N = "cluboasissparta.com", "https://cluboasissparta.com/", "Club Oasis"
PAGE = """<!doctype html><html><head><title>Club Oasis Supper Club</title></head><body>
<div id="main-content"><h1>Club Oasis Supper Club</h1><p>Dine-in, Outdoor Seating, In-Store Pickup</p>
<a href="https://cluboasissparta.com/menu">Menu</a> <a href="https://www.facebook.com/cluboasis">Facebook</a></div>
</body></html>"""
INJ = ('<div style="position:absolute;left:-5466px;width:500px;">W <a href="https://galaxy-kasyno.example.pl/pl/">milky way casino</a> '
       'od razu masz wrażenie: jackpoty migają, zadania z darmowymi spinami</div>')


def add(html):
    return PAGE.replace("</body>", html + "</body>")


cases = {
    # must fire
    "club oasis as captured": (add(INJ), True),
    "english casino link, visible": (add('<p>Partners: <a href="https://best-online-casino.example/">online casino</a></p>'), True),
    "casino host with innocent text (the first injected() exempted any 'casino' host)":
        (add('<a href="https://spincasino-nz.example/">click</a>'), True),
    "display:none pharma link": (add('<div style="display:none"><a href="https://rx-meds.example/buy-cialis">buy cialis online</a></div>'), True),
    "visibility:hidden adult link": (add('<span style="visibility: hidden"><a href="https://hotxxxvids.example/">free porn</a></span>'), True),
    "font-size:0 link farm": (add('<div style="font-size:0;"><a href="https://a1-loans.example/">a</a> <a href="https://b2-essays.example/">b</a> '
                                  '<a href="https://c3-watches.example/">c</a></div>'), True),
    "height:0 overflow hidden farm": (add('<div style="height:0;overflow:hidden"><a href="https://paydayfast.example/">payday loans</a></div>'), True),
    "noscript link farm": (add('<noscript><a href="https://x1.example/">payday loans</a><a href="https://x2.example/">y</a>'
                               '<a href="https://x3.example/">z</a><a href="https://x4.example/">w</a></noscript>'), True),
    # false positives found in the 2026-10-21 recheck
    "noscript press links (B10 Chophouse)": (add('<noscript>' + "".join(f'<a href="https://news{i}.example/story">Press {i}</a>' for i in range(6))
                                                 + '</noscript>'), False),
    "opacity:0 fade-in menu of sister restaurants (Max Restaurant Group)":
        (add('<div style="opacity:0"><a href="https://www.maxdowntown.example/">Max Downtown</a><a href="https://maxfish.example/">Max Fish</a>'
             '<a href="https://maxamia.example/">Max A Mia</a></div>'), False),
    "opacity:0 block with a casino link still fires": (add('<div style="opacity:0"><a href="https://best-casino.example/">casino</a></div>'), True),
    "designer credit at -931px (Rustico)": (add('<div style="position:absolute;top:-931px;left:-931px"><a href="http://www.designer.example/">web design</a></div>'), False),
    "Foursquare link at top:-200px (Gondola)": (add('<div style="position:absolute;top:-200px;right:10px"><a href="https://4sq.com/927utv">4sq</a></div>'), False),
    "nested hidden div": (add('<div style="display:none"><div class="a"><p>hi</p></div><div><a href="https://slot-gacor.example/">situs slot</a></div></div>'), True),
    "pharma text visible": (add("<p>Cheap viagra and cialis without prescription</p>"), True),
    "Chinese lottery page (Rupp's old domain)": ("<html><head><title>Washington 168网 历史查询记录 中国体彩幸运168官方飞艇直播</title></head>"
                                                "<body><p>幸运飞艇 开奖记录</p></body></html>", True),
    "Indonesian 4D lottery link": (add('<a href="https://harum4d.example/">daftar harum4d</a>'), True),
    "Thai casino copy (Napoli Pizza)": (add("<p>เรามีเกมจากผู้ให้บริการ บาคาร่า สล็อตออนไลน์ แทงบอลออนไลน์</p>"), True),
    "Vietnamese betting title (BBG's)": ("<html><head><title>keonhacai 5 tỷ lệ kèo nhà cái 88</title></head><body><p>x</p></body></html>", True),
    "Indonesian gaming copy (House of Corned Beef)": (add("<p>promo login daftar link alternatif live chat, kejar target kemenangan</p>"), True),
    "one link far off the page (Paddy's Pizza)": (add('<div style="position:absolute;left:-8897px;width:500px;"><a href="https://m.someblog.example.ru/">'
                                                     'https://m.someblog.example.ru/</a></div>'), True),
    "decoded loader injecting an ad script (Champs)": (add(f"<script>eval(atob('dmFyIHM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc2NyaXB0Jyk7cy5zcmM9J2h0dHBzOi8vYWRzbmV0LmV4YW1wbGUvcGxhY2VyLmpzJztkb2N1bWVudC5oZWFkLmFwcGVuZENoaWxkKHMpOw=='))</script>"), True),
    # must not fire
    "club oasis cleaned": (PAGE, False),
    "negative margin layout (Murray's On Main)": (add('<div style="margin-top:-138px"><a href="https://www.facebook.com/murrays">FB</a> '
                                                      '<a href="https://www.toasttab.com/murrays">Order</a></div>'), False),
    "hidden mobile menu with social and ordering": (add('<div style="display:none" class="mobile-nav"><a href="https://www.facebook.com/x">FB</a>'
                                                       '<a href="https://www.instagram.com/x">IG</a><a href="https://www.toasttab.com/x">Order</a>'
                                                       '<a href="https://cluboasissparta.com/menu">Menu</a></div>'), False),
    "noscript tag manager and pixel": (add('<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-X" height="0" width="0" '
                                           'style="display:none;visibility:hidden"></iframe></noscript>'), False),
    "real casino links from a tribal casino's restaurant": (add('<a href="https://www.potawatomi.com/">Potawatomi Casino</a> '
                                                               '<a href="https://www.ho-chunkgaming.com/">Ho-Chunk Gaming</a>'), False),
    "monte cassino and poker run": (add("<p>Chicken Monte Cassino. Join our motorcycle poker run!</p>"), False),
    "xxx root beer": (add('<a href="https://xxxrootbeer.com/">XXX Root Beer Drive-In</a>'), False),
    "sports bar title with darts & slots (Angry Bob's)": ("<html><head><title>Sports bar in Kenosha | 11 HD TVs, pool, darts &amp; slots"
                                                         "</title></head><body><p>wings</p></body></html>", False),
    "name Judi's Place": ("<html><head><title>Judi&#39;s Place</title></head><body><p>burgers</p></body></html>", False),
    "email obfuscator that decodes to mailto": (add(f"<script>eval(atob('ZG9jdW1lbnQud3JpdGUoJzxhIGhyZWY9Im1haWx0bzppbmZvQGV4YW1wbGUuY29tIj5FbWFpbCB1czwvYT4nKQ=='))</script>"), False),
    "Chinese restaurant menu in Chinese": (add("<h2>菜单</h2><p>宫保鸡丁 北京烤鸭 幸运饼干 麻婆豆腐 春卷</p><p>Lucky Star Chinese Restaurant</p>"), False),
    "CSS colour #ffffff4d and a collection4d image": (add('<style>.t{background:#ffffff4d}</style><img src="hp-collection4d-pizza.png" alt="">'), False),
    "Indonesian slot title (Takarajima Sushi)": ("<html><head><title>spaceman | situs link spaceman slot gampang menang hari ini</title></head>"
                                                 "<body><p>x</p></body></html>", True),
    "food porn and ski-porn on a bar's own page (Matterhorn Ski Bar)": (add("<p>Our burgers are pure food porn. We play ski-porn on big screens, and more ski porn on Fridays.</p>"), False),
    "porn star martini on a cocktail menu, twice (The Five Lamps)": (add("<p>Porn Star Martini $16</p><p>pornstar martini pitcher</p>"), False),
    "adult text twice still fires": (add("<p>free porn videos here</p><p>watch porn now</p>"), True),
    "3D/4D printing and movie words": (add("<p>See our 4D movie night and the 3D printed menus</p>"), False),
    "skip link off-screen, internal": (add('<a style="position:absolute;left:-9999px" href="#main">Skip to content</a>'), False),
    "link to a Wisconsin tribal casino (Mole Lake)": (add('<a href="http://www.molelakecasino.com/">Mole Lake Casino</a>'), False),
    "malformed bracketed host doesn't crash the scan": (add('<a href="http://[0]/x">x</a> <a href="https://[::1/">y</a>'), False),
}

bad = 0
for label, (body, want) in cases.items():
    got = [r for r, _ in D.scan(body, H, F, N)]
    ok = bool(got) == want
    bad += not ok
    print(("ok  " if ok else "FAIL"), label, got)
for label, body in (("parked page", "<html><body><h1>This domain is for sale!</h1><p>Make an offer</p></body></html>"),
                    ("cPanel placeholder (Mihm's)", '<html><head><META HTTP-EQUIV="refresh" CONTENT="0;URL=/cgi-sys/defaultwebpage.cgi"></head></html>')):
    ok = D.parked(body, "https://example.com/") is not None
    bad += not ok
    print(("ok  " if ok else "FAIL"), label)
# casino=True (a state's own list of its real casinos says the place is one): its sportsbook link is the casino's own business
CASINO_PAGE = add('<a href="https://sportsbook-casino.example/">sportsbook and casino</a>')
ok = bool(D.scan(CASINO_PAGE, H, F, N)) and not D.scan(CASINO_PAGE, H, F, N, casino=True)
bad += not ok
print(("ok  " if ok else "FAIL"), "casino=True exempts a real casino's own betting links")
# a real casino's own page (named casino host) hides a menu linking its online casino: not a hijack
CAS = '<html><body><h1>Harrah\'s Steakhouse</h1><div style="display:none"><a href="https://horseshoeonlinecasino.example/">Online casino</a></div></body></html>'
ok = not D.scan(CAS, "www.caesars.com", "https://www.caesars.com/harrahs/dining", "Harrah's Steakhouse")
bad += not ok
print(("ok  " if ok else "FAIL"), "real casino's hidden online-casino menu")
ok = not D.scan(CAS.replace("Harrah\'s", "Rivers"), "www.riverscasino.com", "https://www.riverscasino.com/schenectady/dining", "Rivers Casino")
bad += not ok
print(("ok  " if ok else "FAIL"), "Rivers Casino's own dining page")
ok = D.parked(PAGE, F) is None
bad += not ok
print(("ok  " if ok else "FAIL"), "club oasis isn't parked")
print("failures:", bad)
sys.exit(1 if bad else 0)
