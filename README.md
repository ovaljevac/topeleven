# Top Eleven AI Agent

Windows alat za automatizaciju svakodnevnih zadataka u igri **Top Eleven** pokrenutoj kroz **BlueStacks**. Agent kombinuje kontrolisanu PowerShell state mašinu, lokalnu OpenCV analizu i vision AI kako bi prepoznao ekran, pokrenuo dozvoljene radnje i sigurno obradio nagradne reklame.

> [!IMPORTANT]
> Projekat upravlja mišem i BlueStacks prozorom. Prvi put pokreni samo jedan kraći tok i nadgledaj njegovo ponašanje prije korištenja opcije **Pokreni sve**.

## Šta agent može raditi

| Tok | Namjena |
| --- | --- |
| **Uzmi 25 zelenih** | Preuzima dostupne besplatne zelene boostere. |
| **Odmori ekipu** | Odmara igrače redom, od izabrane početne pozicije. |
| **Top Eleven TV** | Preuzima TV nagrade i obrađuje tok priručnika. |
| **Mourinho** | Pokreće i završava Mourinho nagradnu reklamu. |
| **Kampus** | Obrađuje Kampus objekte koji još nisu dostigli 100%. |
| **Put saveza** | Završava dnevni video zadatak na Putu saveza. |
| **Trening igrača** | Ponavlja trening i po potrebi podiže kondiciju igrača. |
| **Pokreni sve** | Redom pokreće Mourinho, TV, Put saveza, Kampus i 25 zelenih. |

Centralni Manager nudi izbor toka, zajednički log, sigurno zaustavljanje, nastavak prethodne sesije, izbor početne faze za kombinovani tok i izbor početne pozicije za odmor ekipe.

## Preduslovi

- Windows 10 ili 11
- BlueStacks sa instaliranim i prijavljenim Top Elevenom
- Windows PowerShell 5.1
- Python 3 za vision komponente, testove i Discord bot
- Gemini API ključ za podrazumijevanu AI konfiguraciju

BlueStacks prozor se podrazumijevano traži pod naslovom `BlueStacks App Player`. Ako tvoja instalacija koristi drugi naslov, promijeni `windowTitle` u `AI-Agent/config.json`.

## Brzi početak

1. Kloniraj ili preuzmi projekat.
2. Otvori PowerShell u folderu `AI-Agent` i napravi Python okruženje:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
   ```

3. Pokreni `AI-Agent\Postavi Gemini API kljuc.cmd` i unesi Gemini API ključ. Ključ se čuva lokalno u `AI-Agent/.env` i nije uključen u Git.
4. Pokreni `AI-Agent\Testiraj Gemini.cmd` kako bi provjerio vezu.
5. Otvori BlueStacks i Top Eleven, zatim pokreni:

   ```text
   AI-Agent\Pokreni AI Agent.cmd
   ```

6. U Manageru prvo izaberi jedan kraći tok, pritisni **POKRENI AGENTA** i prati log.

Za prečicu na Desktopu pokreni `Napravi desktop precicu.ps1`. Prečica vodi direktno na centralni Manager.

## Kako sistem radi

1. `TopElevenManager.ps1` prikazuje korisničko sučelje i pokreće odabrani tok.
2. `TopElevenAgent.ps1` vodi state mašinu i dozvoljava samo unaprijed definisane akcije.
3. `VisionAgent.py` snima samo BlueStacks prozor i traži strukturisanu analizu slike od izabranog vision providera.
4. `XDetector.py` lokalno prepoznaje poznate ekrane i provjerava vizuelne detalje pomoću OpenCV-a.
5. Agent klikne samo kada rezultat prođe provjere odgovarajuće za trenutni korak.

Za kontrole unutar reklama AI smije predložiti samo dozvoljene akcije poput zatvaranja, preskakanja ili povratka iz Google Playa. OpenCV ne bira reklamno dugme samostalno. Dugmad za instalaciju, kupovinu i plaćanje nisu dozvoljena.

Ako ekran nije dovoljno sigurno prepoznat, agent ostaje na istom koraku i ponavlja provjeru umjesto nasumičnog klikanja. Potpuni restart odgovarajuće BlueStacks instance koristi se samo u kontrolisanim recovery scenarijima.

## AI konfiguracija

Podrazumijevani provider podešen je u `AI-Agent/ai_config.json`:

```json
{
  "provider": "gemini",
  "model": "gemini-3.5-flash-lite",
  "minimumConfidence": 0.85
}
```

Rezervni Gemini ključ možeš dodati preko `AI-Agent\Postavi rezervni Gemini API kljuc.cmd`. Ako glavni ključ dobije odgovor o potrošenoj kvoti, agent može preći na rezervni ključ.

### Lokalni Ollama provider

Za lokalnu obradu instaliraj Ollamu i model, na primjer:

```powershell
ollama pull qwen3-vl:2b
```

Zatim u `AI-Agent/ai_config.json` postavi:

```json
{
  "provider": "ollama",
  "endpoint": "http://127.0.0.1:11434/api/chat",
  "model": "qwen3-vl:2b",
  "timeoutSeconds": 120
}
```

Gemini zahtijeva slanje snimka BlueStacks prozora Googleovom API-ju. Ollama obradu radi lokalno na računaru.

## Konfiguracija

- `AI-Agent/config.json` — naslov BlueStacks prozora, timeouti, pauze, broj pokušaja i parametri pojedinačnih tokova.
- `AI-Agent/ai_config.json` — AI provider, model, endpoint, prag pouzdanosti, rate limit i debug postavke.
- `AI-Agent/.env` — lokalni API ključevi; fajl je ignorisan u Gitu.
- `AI-Agent/discord_config.json` — lokalni Discord token i dozvoljeni korisnici; fajl je ignorisan u Gitu.

Prije većih promjena vrijednosti sačuvaj kopiju konfiguracije. Pogrešni timeouti ili koordinate mogu učiniti automatizaciju nepouzdanom.

## Provjera projekta

Najlakše je u Manageru otvoriti **Postavke** i izabrati **Provjeri projekat**, ili pokrenuti `AI-Agent\Provjeri projekat.cmd`.

Provjera ne upravlja BlueStacksom. Ona provjerava obavezne fajlove, PowerShell i JSON sintaksu, Python testove i ugrađene SelfTest provjere. Iz komandne linije može se pokrenuti bez grafičkog dijaloga:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\AI-Agent\Provjeri projekat.ps1" -NoGui
```

Izvještaji provjere i runtime logovi čuvaju se u `%LOCALAPPDATA%\TopElevenAgent\logs`.

Pojedinačne razvojne provjere, pokrenute iz foldera `AI-Agent`, su:

```powershell
python -m py_compile .\VisionAgent.py .\XDetector.py
python -m unittest discover -s .\tests -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenAgent.ps1 -SelfTest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\TopElevenManager.ps1 -SelfTest
```

## Discord kontrola (opcionalno)

Agent se može pokretati udaljeno preko ograničenih Discord slash komandi. Bot ne prihvata proizvoljne terminalske naredbe i dozvoljava samo jednog aktivnog agenta.

1. Instaliraj zavisnosti iz `requirements.txt`.
2. Pokreni `AI-Agent\Postavi Discord Bot.cmd` i unesi bot token, Server ID i svoj User ID.
3. Pokreni `AI-Agent\Pokreni Discord Bot.cmd` i ostavi prozor otvoren.

Detaljne upute i spisak komandi nalaze se u [Discord dokumentaciji](AI-Agent/README_DISCORD.md).

## Struktura projekta

```text
topeleven/
├── README.md                         # Glavna dokumentacija
├── Napravi desktop precicu.ps1       # Kreira Desktop prečicu
└── AI-Agent/
    ├── Pokreni AI Agent.cmd          # Glavni ulaz u aplikaciju
    ├── TopElevenManager.ps1           # Grafički Manager
    ├── TopElevenAgent.ps1             # Automatizacija i state mašina
    ├── VisionAgent.py                 # Vision AI komunikacija
    ├── XDetector.py                   # Lokalna OpenCV analiza
    ├── agent_artifacts.py             # Runtime artefakti i evidencija
    ├── config.json                    # Opšta konfiguracija
    ├── ai_config.json                 # AI konfiguracija
    ├── requirements.txt               # Python zavisnosti
    ├── tests/                         # Automatizovani testovi
    ├── regression/                    # Screenshot regresijski runner
    └── */README*                      # Upute za pojedinačne tokove
```

## Rješavanje čestih problema

### Manager ne pronalazi BlueStacks

Provjeri da je BlueStacks pokrenut i da naslov prozora odgovara vrijednosti `windowTitle` u `config.json`.

### Python nije pronađen

Instaliraj aktuelni Python 3 i označi opciju **Add Python to PATH**, ili napravi `.venv` prema koracima iz brzog početka.

### Gemini test ne prolazi

Ponovo pokreni alat za postavljanje ključa, provjeri internet vezu i raspoloživu API kvotu. Ključ ne upisuj ručno u Git fajlove.

### Agent ne klikne dugme

To obično znači da ekran ili kontrola nisu dovoljno pouzdano potvrđeni. Provjeri log i debug snimke prije mijenjanja pragova. Odbijene i nepoznate AI analize mogu se čuvati u `AI-Agent/debug`.

### Reklama je otvorila Play Store ili Chrome

Agent pokušava siguran povratak Android Back komandom, a zatim ponovo potvrđuje ekran. Ako recovery ne uspije, zaustavi tok u Manageru i ručno vrati igru na poznati ekran.

## Dodatna dokumentacija

- [Detalji AI i sigurnosnog toka](AI-Agent/README_AI.md)
- [Kombinovani tok „Pokreni sve“](AI-Agent/README_SVE_REDOM.md)
- [Discord bot](AI-Agent/README_DISCORD.md)
- [Put saveza](AI-Agent/Put%20saveza/README.md)
- [Kampus](AI-Agent/Kampus/README_KAMPUS.md)
- [Mourinho](AI-Agent/Mourinho/README_MOURINHO.md)
- [Top Eleven TV](AI-Agent/za%20TV%20skriptu/README_TV.md)

## Napomena

Ovo je nezavisan alat za ličnu automatizaciju i nije službeni proizvod kompanije Nordeus. Koristi ga odgovorno i na vlastiti rizik, uz poštovanje pravila igre i uslova korištenja povezanih servisa.
