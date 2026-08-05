# Top Eleven automatizacija - detaljni GPT handoff

## 1. Svrha dokumenta

Ovaj dokument je kontekst za drugi GPT ili programera koji nastavlja rad na projektu u direktoriju:

`C:\Users\Korisnik\Documents\topeleven`

Cilj projekta je automatizovati gledanje nagradnih reklama u Top Eleven aplikaciji koja radi unutar BlueStacks App Playera. Automatizacija mora raditi sa promjenjivim reklamama, razlicitim stilovima dugmeta `X`, reklamama koje otvaraju Google Play ili `play.google.com`, te mora vizuelno potvrditi da se korisnik zaista vratio u Top Eleven prije nastavka.

Korisnik zeli da automatizacija:

- koristi vec otvoreni Top Eleven i odmah krene na glavni dio;
- ne pokrece aplikaciju i ne ceka pocetne popupove;
- ima duze buffere pri prelasku izmedju ekrana;
- ceka 60 sekundi od pokretanja svake reklame prije aktivnog trazenja `X` kontrole;
- podrzi portretne i landscape reklame;
- podrzi reklame koje zahtijevaju Google Play tok;
- klikne Android Back nezavisno od velicine BlueStacks prozora;
- nakon zatvaranja reklame vizuelno potvrdi povratak u Top Eleven preko gornjih kartica resursa/boostera;
- ne klikce ponovo `X` ako je reklama vec zatvorena;
- radi sa razlicitim velicinama prozora i, nakon dodatnog refaktorisanja, sa drugim rezolucijama i DPI postavkama;
- eventualno dobije lokalni ili cloud vision agent kao fallback kada OpenCV nije siguran.

## 2. Trenutni projektni fajlovi

### `TopElevenAgent.ps1`

Glavna PowerShell/WinForms aplikacija. Ima dva moda:

- `Zeleni`: otvara prodavnicu i gleda reklame za zelene odmore;
- `OdmoriEkipu`: otvara Trening/Fizio centar i prolazi igrace.

Sadrzi:

- Win32 pronalazenje BlueStacks prozora;
- relativne klikove misem;
- slanje Escape tipke kao Android Back;
- provjere boja odredjenih dijelova ekrana;
- upravljanje reklamnim tokom;
- komunikaciju sa `XDetector.py` procesom;
- WinForms prozor sa statusom, logom i dugmadima Pokreni/Zaustavi.

### `OdmoriEkipu.ps1`

Vrlo mali wrapper:

```powershell
& (Join-Path $PSScriptRoot 'TopElevenAgent.ps1') -Mode OdmoriEkipu
```

### `OG.ps1`

Testna kopija glavnog enginea. U modu odmora pocinje od prvog `MC 1`, a ne od GK. Reklamni engine je uglavnom dupliciran iz `TopElevenAgent.ps1`.

Vazno: svaka promjena reklamnog toka, OpenCV komunikacije, Back mehanizma ili geometrije najcesce se mora primijeniti u oba fajla:

- `TopElevenAgent.ps1`
- `OG.ps1`

Dugorocno je bolje izdvojiti zajednicke funkcije u npr. `TopElevenCommon.ps1` i dot-sourceati ih iz obje skripte.

### `XDetector.py`

Lokalni Python/OpenCV server. PowerShell ga pokrece sa `--server`, zatim mu salje jedan JSON zahtjev po redu preko standardnog inputa. Server vraca JSON preko standardnog outputa.

Podrzani modovi:

- bez posebnog moda: trazenje `X` ili `>>` kontrole;
- `top_resource_cards`: potvrda da su se pojavile Top Eleven kartice resursa;
- `yellow_ad_control`: zuto Google Play dugme ili zuti kruzni `X`;
- `play_destination`: bijeli Chrome Custom Tab sa `play.google.com` i njegov vlastiti `X`.

### `Pokreni Top Eleven Agent.cmd`

CMD meni:

1. Uzmi 25 zelenih.
2. Odmori ekipu.
3. Test od MC-a preko `OG.ps1`.

### `Napravi desktop precicu.ps1`

Pravi desktop precicu `Top Eleven Agent.lnk` koja pokrece CMD meni.

### `README.md`

README trenutno sadrzi zastarjele dijelove i pokvaren encoding/mojibake. Ne treba ga uzimati kao jedini izvor istine. Posebno su zastarjele tvrdnje da skripta sama pokrece Top Eleven, da korisnik rucno zatvara reklamu i da X detekcija pocinje poslije 40 sekundi.

## 3. Okruzenje i dependencyji

Trenutna konfiguracija ocekuje:

- BlueStacks executable: `C:\Program Files\BlueStacks_nxt\HD-Player.exe`
- BlueStacks instanca: `Pie64`
- naslov prozora: `BlueStacks App Player`
- BlueStacks log: `C:\ProgramData\BlueStacks_nxt\Logs\Player.log`
- Top Eleven shortcut: `%USERPROFILE%\Desktop\Top Eleven.lnk`
- Python runtime: `%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`
- lokalne Python biblioteke: `C:\Users\Korisnik\Documents\topeleven\pydeps`

`XDetector.py` dodaje `pydeps` na pocetak `sys.path`. Potrebni Python paketi su:

- `opencv-python`
- `numpy`
- `Pillow`

Za prenos na drugi racunar treba promijeniti `$script:PythonExe` u oba velika PowerShell fajla ili napraviti lokalni virtual environment. Primjer portable instalacije u projektni folder:

```powershell
python -m pip install --target .\pydeps opencv-python numpy pillow
```

Zatim `$script:PythonExe` treba pokazivati na stvarni `python.exe` tog racunara. Trenutni Codex runtime path nije univerzalan.

## 4. Trenutna logika pokretanja

Skripta vise ne otvara Top Eleven shortcut. Ocekuje da je BlueStacks sa Top Elevenom vec otvoren.

`Start-Automation` radi sljedece:

1. pronalazi vidljivi prozor ciji naslov pocinje sa `BlueStacks App Player`;
2. stavlja ga u foreground;
3. odmah pokrece glavni tok izabranog moda;
4. ako prozor nije pronadjen, prijavljuje gresku.

Varijable `$script:BlueStacksExe`, `$script:BlueStacksInstance` i `$script:TopElevenShortcut` jos postoje uglavnom zbog `-SelfTest` provjere, ali se ne koriste za automatsko pokretanje igre.

## 5. Koordinatni sistemi

Postoje dva razlicita nacina klikanja.

### 5.1 `Click-Relative`

Koordinate `X` i `Y` su izmedju 0 i 1 i odnose se na cijeli vanjski BlueStacks prozor koji vraca Win32 `GetWindowRect`.

Formula:

```text
screenX = windowLeft + windowWidth  * X
screenY = windowTop  + windowHeight * Y
```

Ovo se koristi za kontrole koje OpenCV detektuje na screenshotu cijelog prozora, jer i Python vraca koordinate normalizovane prema cijeloj slici.

### 5.2 `Click-GameRelative`

Ova funkcija pokusava iskljuciti BlueStacks naslovnu traku i desni toolbar:

```powershell
$gameLeft = $rect.Left
$gameTop = $rect.Top + 40
$gameRight = $rect.Right - 42
$gameBottom = $rect.Bottom
```

Zatim koristi:

```text
screenX = gameLeft + gameWidth  * X
screenY = gameTop  + gameHeight * Y
```

Ovo je bolje od apsolutnih koordinata, ali jos nije potpuno univerzalno jer su `40 px` i `42 px` fiksni. Promjena Windows DPI-ja, BlueStacks UI skale, verzije BlueStacksa ili sakrivanje toolbara moze promijeniti te vrijednosti.

### 5.3 Android Back

Back se vise ne klika koordinatom na desnom toolbaru. `Send-BlueStacksBack` salje Escape tipku, koju BlueStacks mapira na Android Back. Zbog toga Back ne zavisi od rezolucije ni velicine prozora.

Za Chrome `play.google.com` postoji dodatni fallback: ako Escape nije zatvorio Custom Tab, `XDetector.py` detektuje browserov vlastiti `X`, pa ga PowerShell klikne relativnom koordinatom.

## 6. Trenutne gameplay koordinate

Sve vrijednosti su normalizovane na game viewport iz `Click-GameRelative`.

| Akcija | X | Y | Fajl/mod |
|---|---:|---:|---|
| Bocni meni | 0.014 | 0.068 | oba moda odmora |
| Trening | 0.087 | 0.189 | oba moda odmora |
| Fizio centar | 0.124 | 0.914 | oba moda odmora |
| GK plus | 0.976 | 0.256 | glavni odmor ekipe |
| MC 1 plus | 0.976 | 0.736 | `OG.ps1` |
| BESPLATNO u Fizio centru | 0.778 | 0.880 | odmor ekipe |
| Portretni Google Play logo/zona | 0.104 | 0.023 | posebni ad tok |

Redovi igraca u gornjoj poziciji liste:

| Igrac | Y |
|---|---:|
| GK | 0.256 |
| DL | 0.336 |
| DC 1 | 0.417 |
| DC 2 | 0.497 |
| DR | 0.576 |
| DMC | 0.656 |
| MC 1 | 0.736 |

Nakon skrola prema dolje:

| Igrac | Y |
|---|---:|
| MC 2 | 0.256 |
| AML | 0.336 |
| AMR | 0.417 |
| ST | 0.497 |

`TopElevenAgent.ps1` prolazi GK, DL, DC1, DC2, DR, DMC, MC1, zatim MC2, AML, AMR i ST, pa ponavlja DL, ST, AMR i AML.

`OG.ps1` pocinje od MC1, zatim ide na MC2, AML, AMR, ST i ponavljanja.

## 7. Trenutni reklamni state machine

### 7.1 Pocetak reklame

Nakon sto je `BESPLATNO` vizuelno aktivno, skripta ga klikne i pamti `$adStartedAt`.

Postavlja:

- maksimalni rok reklame: 5 minuta;
- pocetak X detekcije: 60 sekundi nakon starta;
- prvi pokusaj posebnog portretnog Google Play toka: nakon 60 sekundi;
- podsjetnik/status: nakon 75 sekundi.

### 7.2 Prioritet provjera u petlji

U svakoj iteraciji:

1. provjerava da li se otvorio Google Play Store ili Chrome `play.google.com`;
2. poslije 60 sekundi trazi zutu kontrolu;
3. ako je pronadjen zuti Google Play, prvo provjerava postoji li vec pravi `X`;
4. zuti Google Play se za jednu reklamu pokusava samo jednom, da puna zuta pozadina ne izazove beskonacne klikove;
5. za portretne reklame pokusava klik u Google Play zoni, ceka 2 sekunde, zatim klikne ponovo; najvise tri pokusaja;
6. trazi obicni `X` ili `>>`;
7. `>>` se tretira kao nastavak reklame, ne kao zatvaranje;
8. pravi `X` se stabilizuje kroz vise detekcija prije klika.

### 7.3 Google Play i Chrome povratak

`Restore-AdFromGooglePlay` koristi dva izvora:

- najnovije `package` dogadjaje iz BlueStacks `Player.log` za `com.android.vending` i `com.android.chrome`;
- vizuelni fallback `play_destination` za bijelu `play.google.com` Chrome Custom Tab stranicu.

Bitna zastita od ranije utrke u logovima:

- osvjezava foreground stanje nakon novijeg Chrome dogadjaja;
- poredi vrijeme dogadjaja, a ne samo zadnju liniju;
- ne smatra dogadjaj zavrsenim dok povratak nije potvrden;
- ponavlja Back nakon dvije sekunde ako je external ekran jos vidljiv;
- ako Escape ne zatvori Chrome, detektuje i klikne njegov vlastiti `X`.

Nakon povratka u reklamu ceka se da se pojavi pravi reklamni `X`.

### 7.4 Zatvaranje reklame i potvrda

Skripta klikne detektovani `X`, zatim ne pretpostavlja da je reklama zatvorena. `Wait-ForAdExitOrControl` provjerava:

- da li su se vratile Top Eleven kartice resursa;
- ili da li se pojavila nova reklamna kontrola.

Ako su kartice pronadjene, reklama je zatvorena. Ako je pronadjen novi `X`/`>>`, reklama je jos otvorena i tok se nastavlja. Ako nije pronadjeno nista, prijavljuje gresku umjesto nasumicnog klikanja.

## 8. OpenCV detektori i poznate reklame

### 8.1 Obicni `X`

Detektor podrzava:

- svijetli `X` na tamnoj podlozi;
- tamni `X` na svijetloj podlozi;
- lijevi ili desni gornji ugao;
- mali overlay `X` od nekoliko piksela u portretnoj reklami;
- razlikovanje `>>` skip kontrole od `X` kontrole;
- provjeru cetiri dijagonalne ruke da strelica ili logo ne budu pogresno proglaseni za `X`.

### 8.2 Povratak u Top Eleven

`detect_top_resource_cards` ne provjerava aktivnu Android aplikaciju. To je namjerno, jer je reklama dio Top Eleven procesa. Umjesto toga trazi istovremeno:

- zelenu resource karticu;
- plavu resource karticu;
- crvenu resource karticu;

u gornjem dijelu stvarnog Top Eleven ekrana.

Ovo je glavni dokaz da se reklama stvarno zatvorila.

### 8.3 Zuti Google Play i zuti `X`

`detect_yellow_ad_control` trazi gornji desni dio reklame. Trenutna HSV maska je:

```python
H = 14..32
S >= 35
V >= 170
```

Maska je namjerno uska. Stara maska je ukljucivala hue do 42 i spajala lime/zelenu gameplay pozadinu sa zutim dugmetom u ogromnu konturu. Nova maska odvaja stvarni Google Play pill velicine otprilike `146x30` ili `146x58`.

Dodatni filteri za Google Play:

- aspect ratio 2.4 do 8.0;
- sirina 85 do 240 px;
- visina 20 do 65 px;
- ne smije dodirivati ivice ROI-ja;
- ne smije zauzeti vise od 25% ROI-ja;
- mora imati dio bijelog teksta/strelica;
- centar mora biti u ocekivanom gornjem desnom podrucju.

Ako su istovremeno pronadjeni Google Play i `X`, `X` uvijek ima prioritet.

### 8.4 Bijeli `play.google.com` ekran

`detect_play_destination` provjerava:

- gotovo potpuno bijelo tijelo stranice;
- bijeli Chrome header;
- tamne zone za lijevu strelicu, adresu i desne kontrole;
- puni oblik browserovog `X`.

Ovaj detektor jos sadrzi neke fiksne piksel vrijednosti i mora biti skaliran za drugi DPI.

## 9. Kako prilagoditi drugoj rezoluciji, DPI-ju ili BlueStacks postavkama

### 9.1 Prvo stabilizovati postavke

Prije kalibracije izabrati i ne mijenjati tokom rada:

- BlueStacks display resolution;
- landscape/portrait orijentaciju;
- BlueStacks DPI;
- Windows Display Scale, npr. 100%, 125% ili 150%;
- stanje desnog BlueStacks toolbara;
- da li je prozor maksimiziran ili rucno smanjen.

Kod koristi `SetProcessDPIAware`, ali to ne uklanja potrebu za pravilnim viewportom.

### 9.2 Ne prilagodavati samo sirove koordinate

Najbolje rjesenje je prvo uvesti jednu funkciju:

```powershell
function Get-GameViewportRectangle {
    param([IntPtr]$Handle)
    # Vrati Left, Top, Right, Bottom samo za Android/game sadrzaj.
}
```

Sve sljedece funkcije zatim moraju koristiti taj isti viewport:

- `Click-GameRelative`
- `Scroll-PlayerList`
- gameplay color provjere
- screenshot zahtjevi prema `XDetector.py`, ili barem metadata o viewportu
- detektori Top Eleven kartica i ad kontrola.

Ne smije svaka funkcija imati vlastitu verziju `40 px` i `42 px` pravila.

### 9.3 Kako izmjeriti viewport

Na screenshotu cijelog BlueStacks prozora izmjeriti:

- `windowLeft`, `windowTop`, `windowRight`, `windowBottom`;
- prvi red stvarnog Android sadrzaja ispod titlebara: `gameTop`;
- zadnju kolonu stvarnog Android sadrzaja prije desnog toolbara: `gameRight`;
- eventualni lijevi ili donji border.

Trenutni profil je priblizno:

```text
gameLeft   = windowLeft
gameTop    = windowTop + 40 px
gameRight  = windowRight - 42 px
gameBottom = windowBottom
```

Za novi profil upisati stvarno izmjerene vrijednosti ili ih detektovati vizuelno. Ako titlebar na novom DPI-ju ima 50 px, `+40` vise nije tacno.

### 9.4 Pretvaranje izmjerene tacke u relativnu koordinatu

Ako je centar dugmeta na ekran koordinati `(buttonX, buttonY)`, relativna koordinata je:

```text
relativeX = (buttonX - gameLeft) / (gameRight - gameLeft)
relativeY = (buttonY - gameTop)  / (gameBottom - gameTop)
```

Primjer: game viewport je od `(500, 100)` do `(1800, 850)`, a dugme je na `(1150, 700)`:

```text
relativeX = (1150 - 500) / 1300 = 0.500
relativeY = (700 - 100) / 750   = 0.800
```

U skriptu se zatim stavlja:

```powershell
Click-GameRelative $Handle 0.500 0.800 'naziv dugmeta'
```

### 9.5 Koje gameplay tacke treba ponovo kalibrisati

Za novu rezoluciju/postavke napraviti screenshot svakog relevantnog ekrana i izmjeriti centar:

1. bocnog menija;
2. Treninga;
3. Fizio centra;
4. `+` dugmeta svakog reda;
5. `BESPLATNO` dugmeta;
6. zelenog `+` za otvaranje prodavnice;
7. portretnog Google Play loga ako taj fallback ostaje koordinatni;
8. pozicije za scroll liste.

Ako se samo prozor skalira uz isti aspect ratio i isti BlueStacks chrome, normalizovane koordinate obicno ostaju iste. Ako se promijeni odnos stranica ili raspored igre, tacke moraju biti ponovo izmjerene.

### 9.6 Color ROI provjere

`Get-ColorMatchCount` trenutno racuna zone prema cijelom vanjskom prozoru. To je slabije od `Click-GameRelative`. Funkciju treba promijeniti da moze koristiti game viewport:

```powershell
Get-ColorMatchCount -Handle $Handle -Viewport Game ...
```

Posebno ponovo provjeriti ROI-je u:

- `Test-GameHomeLoaded`
- `Test-FreeButtonReady`
- `Test-ResourcePlusReady`
- `Test-AdGooglePlayBadge`
- `Test-StoreLoaded`

Za novu rezoluciju treba snimiti pozitivan i negativan primjer svakog ekrana i potvrditi da prag boje ne prolazi na pogresnom ekranu.

### 9.7 Python piksel konstante koje nisu potpuno resolution-independent

U `XDetector.py` postoje normalizovane ROI vrijednosti, ali i fiksni pikseli. Posebno pregledati:

- pretpostavljenu sirinu desnog toolbara: `42`;
- gornje pocetke ROI-ja oko `38`, `40` i `42` px;
- tiny-X raspon `44..86` px;
- Top Eleven kartice: vertikalna pretraga `38..55` px;
- Chrome Custom Tab header i `X`: fiksne zone oko `40`, `78`, `132` px;
- dozvoljene fizicke dimenzije zutog Google Play dugmeta `85..240 x 20..65` px.

Bolje rjesenje:

1. PowerShell posalje Pythonu samo crop game viewporta, bez BlueStacks titlebara/toolbara; ili
2. uz `rect` posalje i `viewport = {left, top, right, bottom}`; ili
3. Python prvo automatski pronadje granice Android viewporta.

Ako se ipak koriste piksel pragovi, uvesti referentnu velicinu i scale:

```text
scaleX = currentViewportWidth  / referenceViewportWidth
scaleY = currentViewportHeight / referenceViewportHeight
scaledPxX = referencePxX * scaleX
scaledPxY = referencePxY * scaleY
```

Za ikonice je korisno koristiti `min(scaleX, scaleY)` kako se oblik ne bi deformisao.

### 9.8 Konfiguracijski profil umjesto editovanja koda

Preporuka je dodati `config.json`:

```json
{
  "windowTitle": "BlueStacks App Player",
  "titleBarPx": 40,
  "rightToolbarPx": 42,
  "adWaitSeconds": 60,
  "transitionMs": {
    "short": 500,
    "normal": 1800,
    "long": 3000
  },
  "clicks": {
    "sideMenu": [0.014, 0.068],
    "training": [0.087, 0.189],
    "physio": [0.124, 0.914],
    "freePhysio": [0.778, 0.880]
  }
}
```

Tako se za drugi racunar moze napraviti drugi profil bez mijenjanja enginea.

### 9.9 Obavezni testovi poslije kalibracije

Ne testirati odmah cijeli red od 15 reklama. Redoslijed:

1. `-SelfTest` za oba velika PowerShell fajla;
2. test samo pronalazenja BlueStacks prozora;
3. test logovanja koordinata bez stvarnog klika, ako se uvede `DryRun`;
4. jedan klik bocnog menija;
5. jedan prolaz do Fizio centra;
6. jedan `BESPLATNO` klik;
7. replay OpenCV detektora nad sacuvanim screenshotovima;
8. jedna puna reklama uz nadzor;
9. tek zatim cijeli automatizovani red.

Preporuceni komandni testovi:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenAgent.ps1 -SelfTest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\OG.ps1 -SelfTest
python -m py_compile .\XDetector.py
git diff --check -- TopElevenAgent.ps1 OG.ps1 XDetector.py
```

Direktni `XDetector.py --image` trenutno testira samo osnovni X mod. Za ostale modove je korisno dodati CLI argument `--mode` da offline regresija bude jednostavnija.

## 10. Poznate tehnicke slabosti koje sljedeci GPT treba popraviti

1. Velika kolicina dupliciranog koda izmedju `TopElevenAgent.ps1` i `OG.ps1`.
2. Fiksnih `40 px` titlebara i `42 px` toolbara na vise mjesta.
3. `Scroll-PlayerList` koristi cijeli window rect, ne game viewport.
4. Gameplay color provjere koriste cijeli window rect.
5. Chrome `play_destination` detektor koristi vise fiksnih pixel zona.
6. Python runtime path je vezan za Codex cache ovog korisnika.
7. `README.md` je zastario i ima encoding probleme.
8. U postojecim PowerShell stringovima ima mojibake znakova. Nove poruke i komentare je sigurnije pisati ASCII tekstom dok se cijeli fajl planski ne prebaci na ispravan UTF-8 encoding.
9. Ne postoji centralni `config.json` ni `DryRun/Calibration` mod.
10. Nema formalnog screenshot regression test seta sa ocekivanim JSON rezultatima.

## 11. Plan za pravog vizuelnog agenta

### 11.1 Zasto hibrid, a ne samo AI

OpenCV je brz, besplatan i deterministican za poznate kontrole. Vision model je fleksibilniji, ali sporiji i moze pogrijesiti. Najsigurniji dizajn je:

1. state machine zna koji ekran ocekuje;
2. OpenCV prvo trazi poznate kontrole;
3. vision model se poziva samo ako OpenCV nije siguran ili ekran ostane nepoznat;
4. AI samo predlaze akciju i koordinatu;
5. PowerShell validira prijedlog prije klika;
6. novi screenshot potvrduje rezultat poslije klika.

Vision model ne treba imati direktan, neogranicen pristup misu.

### 11.2 Predlozeni JSON izlaz vision modela

```json
{
  "screenType": "ad",
  "topElevenReturned": false,
  "controls": [
    {
      "type": "google_play",
      "x": 0.89,
      "y": 0.10,
      "confidence": 0.94
    }
  ],
  "recommendedAction": "click_google_play",
  "reason": "Yellow Google Play pill is visible in the top-right corner"
}
```

Dozvoljeni `screenType`:

- `top_eleven`
- `ad`
- `google_play_store`
- `play_google_chrome`
- `unknown`

Dozvoljene kontrole:

- `close_x`
- `skip`
- `google_play`
- `back`
- `none`

### 11.3 Sigurnosna pravila agenta

- Nikada ne kliknuti `Install`, `Get`, kupovinu ili potvrdu placanja.
- Dozvoliti samo strogo definisane akcije iz state machinea.
- Za AI klik traziti confidence npr. najmanje `0.85`.
- Za rizicnu ili nepoznatu kontrolu traziti dva uzastopna saglasna screenshota.
- Close/skip kontrola mora biti u dozvoljenoj zoni ili potvrdena OpenCV oblikom.
- Nakon svakog klika napraviti novi screenshot i potvrditi promjenu stanja.
- Ako se stanje nije promijenilo, ne ponavljati beskonacno: koristiti retry limit i timeout.
- Cuvati screenshot i JSON za svaki neuspjeh radi kasnijeg poboljsanja.

### 11.4 Lokalni agent

Preporuceni pocetni model je `Qwen3-VL 4B` u Q4 kvantizaciji kroz Ollama ili llama.cpp. Model je oko 3.3 GB i podrzava GUI razumijevanje i 2D grounding. Lokalni API moze biti:

```text
http://127.0.0.1:11434/api/chat
```

Screenshot game viewporta se salje kao base64 image uz prompt koji zahtijeva iskljucivo validan JSON.

Hardverske smjernice:

| Nivo | Preporuka |
|---|---|
| Minimum CPU-only | 16 GB RAM, noviji 4-6 core CPU; radi sporije |
| Minimum GPU | 16 GB RAM i NVIDIA sa 6-8 GB VRAM-a za 4B model |
| Preporuceno | 32 GB RAM, 6+ core CPU i NVIDIA sa 12 GB VRAM-a |
| Jaci 8B model | 32 GB RAM i 12-16 GB VRAM-a |

`Qwen3-VL 2B` je oko 1.9 GB, ali ce vjerovatno biti manje pouzdan za sitne reklamne kontrole. `Qwen3-VL 8B` je oko 6.1 GB i moze biti bolji, ali trazi vise VRAM-a.

Lokalni model je bez API troska i screenshotovi ne napustaju racunar. Bez GPU-a moze raditi kroz CPU/RAM, ali analiza moze trajati vise sekundi. To je prihvatljivo ako se model poziva samo kao fallback, a ne svake sekunde.

Relevantni linkovi:

- <https://ollama.com/library/qwen3-vl:4b>
- <https://ollama.com/library/qwen3-vl:8b>
- <https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md>

### 11.5 Besplatni cloud agent

Najprakticniji besplatni cloud fallback je Gemini Developer API sa modelom `gemini-2.5-flash-lite`:

- podrzava image input;
- moze vratiti strukturirani JSON;
- free tier je ogranicen kvotama;
- na besplatnom tieru poslani podaci mogu biti koristeni za poboljsanje Google proizvoda.

Zbog kvote ga treba pozivati samo kada lokalni OpenCV ne zna sta da uradi.

Alternativa je Cloudflare Workers AI sa vision modelima i dnevnom besplatnom kvotom. Hugging Face free kredit je vrlo mali i nije pogodan za stalnu automatizaciju.

Relevantni linkovi:

- <https://ai.google.dev/gemini-api/docs/pricing>
- <https://ai.google.dev/gemini-api/docs/image-understanding>
- <https://developers.cloudflare.com/workers-ai/platform/pricing/>
- <https://developers.cloudflare.com/workers-ai/models/>

### 11.6 Predlozeni implementation roadmap

1. Izdvojiti zajednicki engine iz dva PowerShell fajla.
2. Uvesti `config.json` i `Get-GameViewportRectangle`.
3. Uvesti `DryRun` i `Calibration` mod koji prikazuje/loguje buduce klikove bez klikanja.
4. Napraviti screenshot regression folder i manifest ocekivanih rezultata.
5. Dodati `--mode` CLI opciju u `XDetector.py`.
6. Napraviti `VisionAgent.py` kao klijent za lokalni Ollama API.
7. Definisati strogu JSON schemu i validator.
8. Pozvati vision fallback tek nakon OpenCV neuspjeha ili isteka kontrolisanog vremena.
9. Dodati action guard koji odbija `Install`, `Get` i nepoznate akcije.
10. Poslije svakog AI klika vizuelno potvrditi novo stanje.
11. Cuvati nepoznate screenshotove i odluke u poseban debug folder.
12. Tek nakon offline replay testova ukljuciti puni automatski klik.

## 12. Ready-to-paste prompt za sljedeceg GPT-a

```text
Radis na Windows projektu C:\Users\Korisnik\Documents\topeleven.

Prvo potpuno procitaj GPT_HANDOFF_TOP_ELEVEN.md, zatim pregledaj stvarne verzije TopElevenAgent.ps1, OG.ps1 i XDetector.py prije bilo kakve izmjene. README.md je djelimicno zastario i ima encoding probleme.

Glavni cilj je sigurna BlueStacks/Top Eleven automatizacija koja koristi game-relative koordinate, OpenCV detekciju i vizuelnu potvrdu stanja. Ne pretpostavljaj da je reklama zatvorena samo zato sto je X kliknut. Povratak u Top Eleven potvrdi preko gornjih kartica resursa. Android Back salji preko Escape tipke, uz vizuelni Chrome-X fallback.

TopElevenAgent.ps1 i OG.ps1 trenutno dupliciraju reklamni engine. Ako mijenjas zajednicku logiku, uskladi oba fajla ili prvo izdvoji zajednicki modul. Ne uklanjaj postojece zastite za zuti Google Play, puni zuti background, portretni dvoklik, play.google Chrome tok, >> skip i stabilnost X detekcije.

Za drugu rezoluciju nemoj samo mijenjati pojedinacne apsolutne koordinate. Uvedi centralni Get-GameViewportRectangle i config profil. Ukloni ili skaliraj fiksne 40 px/42 px pretpostavke i sve Python pixel konstante. Dodaj DryRun/Calibration mod prije stvarnih klikova.

Za vision agenta koristi hibridni dizajn: OpenCV prvo, lokalni Qwen3-VL 4B ili cloud Gemini fallback samo kada je ekran nepoznat. Model smije vratiti samo strukturirani JSON prijedlog; PowerShell mora validirati koordinatu, confidence i dozvoljenu akciju. Nikada ne klikci Install/Get/kupovinu. Nakon svakog klika ponovo pregledaj ekran.

Sacuvaj korisnikove nepovezane promjene u worktreeju. Koristi apply_patch za editovanje. Nove PowerShell stringove pisi ASCII tekstom dok se encoding cijelog fajla planski ne popravi. Nakon izmjene pokreni oba PowerShell -SelfTest testa, Python py_compile, git diff --check i offline screenshot regresiju relevantnih detektora. Ne commitaj niti brisi fajlove bez izricitog zahtjeva korisnika.
```

## 13. Kriteriji zavrsenog robusnog sistema

Sistem se moze smatrati robusnim kada:

- promjena velicine BlueStacks prozora ne pomjera gameplay klikove;
- isti konfiguracijski profil radi na najmanje dvije velicine prozora istog aspect ratioja;
- drugi DPI zahtijeva samo novi profil, ne editovanje enginea;
- sve poznate reklame prolaze offline screenshot regresiju;
- lazan puni zuti ekran ne aktivira Google Play klik;
- `>>` se nikada ne tretira kao zatvaranje;
- nakon klika na `X` agent potvrdi Top Eleven kartice prije nastavka;
- Chrome/Google Play povratak radi i kada Player.log zakasni;
- nepoznat ekran zavrsi sigurnim `unknown/none`, a ne nasumicnim klikom;
- lokalni/cloud vision fallback nikada ne moze kliknuti `Install`, `Get` ili kupovinu;
- svi retry tokovi imaju timeout i maksimalan broj pokusaja.

