# Top Eleven AI vision agent

Ovaj folder sadrzi aktivnu AI-first verziju projekta. Roditeljski folder sadrzi samo ulaznu dokumentaciju i alat za desktop precicu.

Glavni ulaz je `Pokreni AI Agent.cmd`, koji otvara centralni svijetli dashboard sa svim skriptama, zajednickim logom i Start/Stop kontrolama. Svaki modul se moze pokrenuti zasebno. Za `Pokreni sve` moguce je izabrati pocetnu fazu, a za odmor igraca pocetnu poziciju. Odvojivi mini-log ima prekidac `Iznad: DA/NE`; iskljuci `Iznad` ako bi prozor prekrivao BlueStacks i ulazio u AI screenshot.

Obicna AI ili vizuelna neizvjesnost ne gasi Top Eleven: agent ostaje na istom koraku i ponavlja sigurnu provjeru. Potpuni restart tacne BlueStacks instance koristi se samo za potvrdeno zaglavljenu reklamu ili kada je prije sljedece faze neophodan provjeren pocetni ekran. U kombinovanom toku neuspjela faza se evidentira, a agent zatim sigurno prelazi na sljedecu fazu.

## Kako radi

1. PowerShell state machine kontrolise dozvoljene akcije.
2. `VisionAgent.py` snimi samo BlueStacks prozor i salje dijagnosticku sliku izabranom vision provideru.
3. Model mora vratiti strogo definisan JSON.
4. Za reklamne kontrole prihvataju se samo AI akcije `click_close`, `click_skip` i `click_google_play` sa koordinatom na originalnoj slici.
5. OpenCV ne predlaze, ne potvrduje, ne pomjera i ne klika X, skip ili Google Play dugmad reklame.
6. Ako AI nije dostupan ili ne vidi dozvoljenu kontrolu, agent ne klika nista.
7. Google Play i Chrome prepoznaju se iskljucivo preko AI analize slike. ADB ostaje samo za slanje Back komande; Escape je rezerva.
8. Prihvacena AI potvrda Top Eleven ekrana zavrsava reklamni nadzor. Lokalni puni Pocetni ekran i Prodavnica mogu se potvrditi na dva svjeza framea. Android aktivnost, dumpsys i Player.log ne citaju se i ne ucestvuju ni u jednoj odluci.

AI nikada direktno ne upravlja misem. PowerShell prihvata samo poznatu akciju sa odgovarajucom vrstom kontrole i koordinatom unutar originalne slike. `Install`, `Get`, kupovina i placanje se nikada ne klikcu, ali njihovo prisustvo vise ne skriva odvojeni pravi X/skip niti blokira Back iz Storea.

## Gemini 3.5 Flash-Lite (trenutno ukljucen)

`ai_config.json` koristi `gemini-3.5-flash-lite` sa `minimal` thinking nivoom radi kratke latencije. Google vise ne daje `gemini-2.5-flash` novim API korisnicima. U Manageru otvori `Postavke` i izaberi `Postavi API kljuc`: alat atomarno sprema `GEMINI_API_KEY` u lokalni `AI-Agent/.env`, bez prikazivanja ili zapisivanja kljuca u log. `.env` je iskljucen iz Gita. Nakon toga provjeri sa `Testiraj Gemini`.

Free-tier kljuc je dovoljan dok se ne prekorace Googleova ogranicenja zahtjeva. Slike se salju Google Gemini API-ju; ako zelis potpuno lokalnu obradu, vrati Ollama konfiguraciju ispod.

## Lokalni Ollama model (rezerva)

Na ovom racunaru je instalirana Ollama `0.32.5`. Agent koristi lokalni vision model `qwen3-vl:2b` (oko 1.9 GB), jer veci 4B model moze ostati bez VRAM-a kada istovremeno radi BlueStacks na RX 580. Konfiguracija koristi lokalni API `http://127.0.0.1:11434/api/chat`.

Ako se model nekada obrise, ponovo ga preuzmi naredbom:

```powershell
ollama pull qwen3-vl:2b
```

Provjeri da servis i model rade:

```powershell
ollama list
```

Model, endpoint i sigurnosni pragovi podesavaju se u `ai_config.json`. Ako je potrebno privremeno iskljuciti AI bez promjene koda, postavi `enabled` na `false`.

Za povratak na lokalni model postavi:

```json
"provider": "ollama",
"endpoint": "http://127.0.0.1:11434/api/chat",
"model": "qwen3-vl:2b",
"timeoutSeconds": 120
```

Prva detekcija X-a pocinje 12 sekundi nakon pokretanja reklame. Model se ucitava u pozadini cim se pritisne `POKRENI`. Google Play Store i Chrome se prepoznaju iz trenutnog `dumpsys` activity stanja i vracaju direktnim Android Back pozivom, pa fokus Managera ili mini-loga ne moze progutati Escape. AI trenutne slike je fallback kada ADB stanje nije dostupno.

Za duge interaktivne reklame postoji wake mehanizam. Nakon 75 sekundi bez izlaza agent svakih 12 sekundi dodirne neutralnu zonu oglasa i bez dodatnog cekanja odmah pravi AI screenshot. Time pokusava ponovo prikazati Google Play/skip kontrole koje se pojave samo nakratko. Vrijednosti su podesive kroz `adWakeTapAfterSeconds`, `adWakeTapIntervalSeconds` i `adWakeTapMaximum` u `config.json`.

Reklamne kontrole su semanticki `AI-only`: Gemini na cistoj originalnoj BlueStacks slici jedini bira da li je kontrola X, >>/skip ili Google Play/Play Store. OpenCV ne smije sam predloziti drugo dugme niti pokrenuti klik; kod X-a smije samo u maloj zoni oko AI tacke potvrditi dijagonale i vratiti njihov stvarni centar. Ne postoji univerzalni pomak koordinata.

Za `X` AI i dalje jedini odlucuje koja je kontrola za zatvaranje. Nakon njegove odluke agent uzima novu sliku i samo u maloj zoni oko te tacke pokusava geometrijski centrirati dvije dijagonale istog X-a. Lokalna analiza ne smije traziti drugo dugme niti primijeniti fiksni pomak. Jedna AI odluka je dovoljna kada taj svjezi lokalni frame potvrdi dijagonale i njihov centar; tada se X odmah klikne bez drugog Gemini zahtjeva. AI koordinata bez lokalno pronadjenih dijagonala ostaje samo kandidat i ne moze sama autorizovati klik.

Prva AI provjera pocinje 12 sekundi nakon pokretanja reklame, zatim se Gemini redovno poziva svakih 12 sekundi (`aiProbeIntervalSeconds`). Lokalno potvrden X iz te jedne provjere odmah je spreman za klik, bez dodatnog Gemini zahtjeva. Nakon klika ili gubitka kandidata pre-click tok pokrece stvarni nadzor povratka i novih kontrola: potvrden povratak odmah zavrsava reklamu, a novi lokalno potvrden X koristi se u istoj iteraciji. Ako nadzor ostane neodlucan, naredni pokusaj ceka redovni interval. Potrosene koordinate se brisu prije nadzora. Wake provjera takodjer odmah koristi potvrdu povratka umjesto da je odbaci. Wake dodir kod dugih interaktivnih reklama moze odmah pokrenuti dodatnu AI provjeru, uz postojeca ogranicenja API poziva.

Povratak iz Google Play/Chrome toka koristi svjezu AI potvrdu prije Back-a i novu AI sliku poslije njega. Broj Back komandi je ogranicen, a nepromijenjen ekran prekida niz. Android activity provjere potpuno su uklonjene iz pocetka faza, pokretanja reklama, nadzora, treninga i oporavka. ADB sluzi samo kao kanal za komande, ne za prepoznavanje ekrana.

TV nagrada `PRIRUCNIK` takodjer ima vlastitu sigurnu izlaznu putanju: nakon vec opazene reklame dva uzastopna lokalna `manual_3` framea (`NABAVLJEN NOVI PRIRUCNIK`) odmah predaju tok obradi prirucnika. Time kasni Android activity zapis vise ne ostavlja agent u reklamnoj petlji na ekranu vec osvojene nagrade.

Obicna TV nagrada nakon vec opazene reklame prihvata dva uzastopna lokalna `tv` framea kao povratak, cak i kada Android activity zapis kasni poslije Play Storea. Ova putanja je zabranjena za nagradu `PRIRUCNIK`, koja mora prikazati poseban `manual_3` ekran.

Lokalne brze potvrde povratka (`tv`, `manual_3` i profil igraca) aktiviraju se tek nakon sto je AI na prethodnom svjezem frameu stvarno vidio reklamni ekran. Sam ADB `AdActivity` nije dovoljan, jer se u prvim sekundama iza nove aktivnosti moze jos vidjeti stari ekran igre. Profil igraca uz dva stabilna framea mora imati i vlastiti strogi vizuelni potpis: veliki svijetli modal te poravnate crvenu `POVREDE`, plavu `MORAL` i zelenu `KONDICIJA` kontrolu. Resource zaglavlje nije obavezno jer ga profil moze djelimicno prekriti.

Put saveza nakon AI-potvrdjene reklame prihvata povratak kada dva uzastopna lokalna `alliance_flow` framea vide isti `path` modal i stabilan modalni X. Taj vec potvrden modal ne prolazi kroz dodatnu 75-sekundnu `MainPlayerNativeActivity` kapiju; odmah se predaje postojecoj stabilnoj provjeri X-a i zatvara.

Prije pocetka faze stari ADB/Player.log `AdActivity` zapis ne moze sam pokrenuti reklamni watcher. Ako dva uzastopna lokalna TV-flow framea jasno prepoznaju puni ekran `POCETNI`, zapis se smatra zastarjelim i faza nastavlja bez izmisljene reklame. Stvarni Store/Chrome foreground i dalje ima prioritet i mora se prvo zatvoriti.

Ako Gemini pri potvrdi povratka jednom vrati prekinut ili nedovrsen JSON, agent odmah ponavlja analizu na svjezoj slici. U toku odmora igraca nakon klika na X ostavlja se dovoljno vremena i za narednu provjeru nakon API backoffa, pa jedan neispravan odgovor vise ne prekida cijeli red igraca iako je reklama vec zatvorena.

Ako Gemini uprkos 0..1 shemi vrati svoju prostornu skalu 0..1000 (npr. `26,94`), AI-only validator je automatski pretvara u `0.026,0.094` umjesto da odbije pronadjeni X. Podrzane su i doslovne piksel-koordinate kao rezerva.

U toku `Odmori ekipu` plava pozadina sama nije dokaz da je nagradno dugme spremno. Lokalni recognizer mora vidjeti puni bijeli natpis `BESPLATNO` rasiren preko dugmeta u stvarnom Top Eleven prozoru; tri tacke i prazno plavo dugme se odbijaju. Natpis mora ostati na istoj lokaciji kroz dvije provjere najmanje 350 ms, a neposredno prije klika radi se jos jedna svjeza provjera. Klik koristi pronadjeni centar dugmeta bez fiksnog pomaka. Poslije klika agent zasebno potvrdi da je reklama pokrenuta; ponovni klik nije dozvoljen prije osam sekundi. Ako se vrati stabilni natpis ili ostane loading, agent se vraca na sigurno cekanje umjesto da prerano pokrene X nadzor.

Prozor za `Odmori ekipu` ima listu `Pocni od pozicije`. Izabrana stavka je prvi igrac kojeg agent obradi, a sve ranije stavke preskace i nastavlja postojecim redoslijedom do kraja, ukljucujuci stavke drugog kruga. Isto se moze zadati iz komandne linije, npr. `OdmoriEkipu.ps1 -TeamRestStart AMR`.

U Campus toku jedan validan AI izbor objekta sa parsabilnim `TARGET` nazivom i procentom ispod 100% odmah ide na klik, jer lokalni Campus recognizer zatim mora potvrditi da se otvorio detalj sa stvarnim plavim reward podrucjem za `100%`; sam bilo koji detail ekran nije dovoljan. Time vise objekata sa istim procentom ne mogu zaglaviti potvrdu na `1/2`. Odluka da nema vise objekata i dalje zahtijeva dvije svjeze AI potvrde. Ako klik promasi ili otvori objekat bez tog reward podrucja, detalj se zatvara, a sve prethodno promasene tacke oznacavaju se crvenim prekrizenim krugovima na novoj AI slici i zabranjuju pri narednom pokusaju. Klik i dalje koristi direktnu novu AI koordinatu bez univerzalnog pomaka.

Put saveza tok koristi lokalne vizuelne anchore samo za Top Eleven navigaciju: pronalazi red `Savezi`, plocicu `PUT SAVEZA`, tacni plavi video-`IDI` i modalni `X`. Zelena `IDI` dugmad se odbijaju. Plavi `IDI` mora imati video ikonu i puni tekst kroz dvije stabilne provjere, pa jos jednu svjezu provjeru neposredno prije klika. Sama plava pozadina ili loading stanje nisu dovoljni. Reklama zatim koristi isti AI-only nadzor X/skip/Google Play kao ostali tokovi.

Nakon otvaranja bocnog menija Put saveza tok pravi tacno jedan wheel korak prema dolje i zatim trazi `Savezi`. Ako red tada nije prepoznat, tok se sigurno zaustavlja umjesto da ponavlja scroll deset puta.

## Pokretanje

Za automatizovano ponavljanje najnovijeg treninga koristi `Trening igraca\Pokreni Trening igraca Agent.cmd`. Tok provjerava kondiciju odabranog igraca, koristi puni tekst `BESPLATNO` i postojeci AI-only nadzor reklame dok igrac ne dostigne najmanje 85%, zatim pokrece trening i ponavlja ciklus.

Prvo otvori BlueStacks i Top Eleven, zatim pokreni:

```text
Pokreni AI Agent.cmd
```

Za sigurnu provjeru koordinata koristi opciju Kalibracija. Ona ne klikce.

## Offline provjere

Kampus poslije prvog otvaranja objekta ostaje u detalju i bira naredne objekte iz donje lijeve trake. Puni zeleni indikatori se preskacu, a potpuno vidljive kartice s bijelim ostatkom biraju se uz svjezu lokalnu potvrdu. Traka se prvo dovodi do lijevog kraja, a zatim se za naredne objekte povlaci zdesna nalijevo. Zavrsavanje zahtijeva dva pokusaja bez pomjeranja na desnom kraju i bez vidljivih nepotpunih kartica. Reklama se pokrece samo preko potvrdenog plavog video dugmeta `100%`, nikad preko placenog `+10%` ili `UNAPRIJEDI`.

Najjednostavnije je u Manageru otvoriti `Postavke` i pritisnuti `Provjeri projekat`, ili pokrenuti `Provjeri projekat.cmd`. Provjera ne upravlja BlueStacksom: validira obavezne fajlove, PowerShell i JSON sintaksu, Python testove i oba SelfTesta. Iz komandne linije se moze pokrenuti bez dijaloga:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Provjeri projekat.ps1" -NoGui
```

Ako racunar nema ugradjeni Codex Python runtime, napravi `.venv` ili `venv` i instaliraj zavisnosti:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Pojedinacne provjere su:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenAgent.ps1 -SelfTest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenManager.ps1 -SelfTest
python -m unittest discover -s .\tests -v
python -m py_compile .\VisionAgent.py .\XDetector.py
python .\regression\run_opencv_regression.py --zip "C:\putanja\do\ss.zip"
```

Regresijski runner cita screenshotove direktno iz zadatog `ss.zip`; ne raspakuje ih u projekat i ne mijenja arhivu. Ako arhiva nije prisutna, kompletna provjera je jasno oznacava kao opcionalno preskocenu.

Ne ukljucuj puni automatizovani red prije testiranja jedne reklame pod nadzorom. Odbijeni i nepoznati AI rezultati spremaju se u `debug` folder radi naknadne analize; zadrzava se najvise `maximumDebugCaptures` snimaka (standardno 200) zajedno sa njihovim JSON metapodacima.
# Rezervni Gemini API kljuc

Pokreni `Postavi rezervni Gemini API kljuc.cmd` za unos drugog kljuca. Kada Gemini vrati HTTP 429 zbog potrosene kvote, VisionAgent automatski prelazi na sljedeci konfigurirani kljuc. Rezervni kljuc treba pripadati drugom Google Cloud projektu s vlastitom dostupnom kvotom; kljucevi istog projekta dijele limit.
