# Top Eleven AI vision agent

Ovaj folder sadrzi aktivnu AI-first verziju projekta. Roditeljski folder sadrzi samo ulaznu dokumentaciju i alat za desktop precicu.

Glavni ulaz je `Pokreni AI Agent.cmd`, koji otvara centralni dark dashboard sa svim skriptama, zajednickim logom i Start/Stop kontrolama. Svaki modul se moze pokrenuti zasebno. Za `Pokreni sve` moguce je izabrati pocetnu fazu, a za odmor igraca pocetnu poziciju.

Ako faza padne, zajednicki engine radi BlueStacks force-stop Top Elevena, ponovo pokrece igru i istu fazu pokusava najvise tri puta. U kombinovanom toku se tek nakon tri neuspjeha evidentira greska te nastavlja na sljedecu fazu.

## Kako radi

1. PowerShell state machine kontrolise dozvoljene akcije.
2. `VisionAgent.py` snimi samo BlueStacks prozor i salje dijagnosticku sliku izabranom vision provideru.
3. Model mora vratiti strogo definisan JSON.
4. Za reklamne kontrole prihvataju se samo AI akcije `click_close`, `click_skip` i `click_google_play` sa koordinatom na originalnoj slici.
5. OpenCV ne predlaze, ne potvrduje, ne pomjera i ne klika X, skip ili Google Play dugmad reklame.
6. Ako AI nije dostupan ili ne vidi dozvoljenu kontrolu, agent ne klika nista.
7. Povratak iz Storea koristi Android package/activity signal i novu AI sliku prije svakog dodatnog Back pokusaja.
8. Povratak u igru potvrduje svjezi `MainPlayerNativeActivity` dogadjaj ili AI koji na trenutnoj slici jasno vidi pravo Top Eleven zaglavlje sa vise kartica resursa.

AI nikada direktno ne upravlja misem. PowerShell prihvata samo poznatu akciju sa odgovarajucom vrstom kontrole i koordinatom unutar originalne slike. `Install`, `Get`, kupovina i placanje se nikada ne klikcu, ali njihovo prisustvo vise ne skriva odvojeni pravi X/skip niti blokira Back iz Storea.

## Gemini 3.5 Flash-Lite (trenutno ukljucen)

`ai_config.json` koristi `gemini-3.5-flash-lite` sa `minimal` thinking nivoom radi kratke latencije. Google vise ne daje `gemini-2.5-flash` novim API korisnicima. Otvori `.env` i zalijepi kljuc iza `GEMINI_API_KEY=` bez navodnika. `.env` je iskljucen iz Gita i agent nikada ne ispisuje njegov sadrzaj u logove. Nakon toga provjeri sa `Testiraj Gemini.cmd`.

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

Prva detekcija X-a pocinje 20.5 sekundi nakon pokretanja reklame. Model se ucitava u pozadini cim se pritisne `POKRENI`, a Google Play Store se vraca preko svjezeg BlueStacks package/activity dogadjaja; AI trenutne slike je fallback i obavezna potvrda prije drugog ili treceg Back pokusaja.

Za duge interaktivne reklame postoji wake mehanizam. Nakon 75 sekundi bez izlaza agent svakih 12 sekundi dodirne neutralnu zonu oglasa i bez dodatnog cekanja odmah pravi AI screenshot. Time pokusava ponovo prikazati Google Play/skip kontrole koje se pojave samo nakratko. Vrijednosti su podesive kroz `adWakeTapAfterSeconds`, `adWakeTapIntervalSeconds` i `adWakeTapMaximum` u `config.json`.

Reklamne kontrole su potpuno `AI-only`: Gemini od prve provjere sam bira X, >>/skip ili Google Play/Play Store na cistoj originalnoj BlueStacks slici. OpenCV nema pravo predloziti, potvrditi, precizirati niti kliknuti dugme reklame. Ne postoji univerzalni pomak koordinata; klik koristi tacno koordinatu koju vrati AI.

Za `X` AI i dalje jedini odlucuje koja je kontrola za zatvaranje. Nakon njegove odluke agent uzima novu sliku i samo u maloj zoni oko te tacke pokusava geometrijski centrirati dvije dijagonale istog X-a. Lokalna analiza ne smije traziti drugo dugme niti primijeniti fiksni pomak. Ako lokalno centriranje ne uspije, ostaje tacna AI koordinata bez izmisljenog pomaka.

Prva AI provjera pocinje 20.5 sekundi nakon pokretanja reklame, zatim se Gemini poziva svakih 20.5 sekundi (`aiProbeIntervalSeconds`). Wake dodir kod dugih interaktivnih reklama odmah pokrece dodatnu AI provjeru.

Povratak iz Google Play/Chrome toka prvo koristi tacnu Android package/activity informaciju iz BlueStacks loga, a AI provjerava trenutni ekran prije dodatnog Back pokusaja. Povratak u samu igru vise se ne potvrdjuje OpenCV slicnoscu gornje trake: prihvata se samo svjezi `eu.nordeus.common.MainPlayerNativeActivity` dogadjaj nastao nakon pokretanja reklame ili AI potvrda stvarnog Top Eleven zaglavlja sa vise kartica resursa. Oglasni `AdActivity` i stari MainPlayer zapis od prije reklame nisu dovoljni.

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

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenAgent.ps1 -SelfTest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenAgent.ps1 -SelfTest
python -m unittest discover -s .\tests -v
python -m py_compile .\VisionAgent.py .\XDetector.py
python .\regression\run_opencv_regression.py
```

Regresijski runner cita screenshotove direktno iz roditeljskog `ss.zip`; ne raspakuje ih u projekat i ne mijenja arhivu.

Ne ukljucuj puni automatizovani red prije testiranja jedne reklame pod nadzorom. Odbijeni i nepoznati AI rezultati spremaju se u `debug` folder radi naknadne analize.
