# Nastavak i screenshot greške

## Pokretanje

- Discord: `/nastavi skripta:` pa izaberi fazu ili `sve`.
- Manager → Skripte: označi **Nastavi danasnji sacuvani napredak**, pa pokreni odabranu skriptu.
- Direktno: pokreni `TopElevenAgent.ps1` s uobičajenim parametrima i dodatnim `-Resume`.
- Obični `/pokreni` i Manager bez označene opcije započinju novu sesiju i novi zapis napretka. Ne nastavljaju automatski.

Za učitavanje novih Discord komandi potrebno je ponovo pokrenuti Discord bot. Za novu Manager opciju ponovo otvori Manager.

## Šta se pamti

Napredak se čuva odvojeno po projektu, režimu i BlueStacks instanci u `%LOCALAPPDATA%\TopElevenAgent\checkpoints`. Zapis sadrži datum, otisak konfiguracije, završene faze, potvrđene odmore po pozicijama, broj završenih trening ciklusa, posljednji potvrđen korak i odvojeno započetu akciju. Ne sadrži screenshot, API ključ ni koordinate klikova. Prethodni zapis ostaje kao `.bak`.

Nastavak prihvata samo današnji zapis iste konfiguracije. Ako zapis nedostaje, neispravan je ili zastario, prijavljuje grešku bez tihog pokretanja od početka.

Završene faze u `Sve` se preskaču. Odmor preskače potvrđene pozicije; trening nastavlja broj ciklusa i ponovo čita kondiciju. TV, Kampus i zeleni ponovo provjeravaju stvarno dostupne ponude/procente. Započeta reklama ili klik nisu dokaz dobijene nagrade.

Prije nastavka nezavršene faze provjerava se trenutni početni ekran. Ako on nije sigurno potvrđen, koristi se postojeći kontrolisani restart tačne instance i povratak na početni ekran. Zatim se do nezavršenog koraka dolazi uobičajenom navigacijom i novim provjerama. Ovo nije vraćanje stare pozicije miša niti nastavak instrukcije usred reklame.

Koristi nastavak samo na istom nalogu i ne mijenjaj raspored igrača između prekida i nastavka odmora. Zapis identifikuje instancu, ne prijavljeni nalog niti igrača po imenu. Prekid između stvarne nagrade i njenog spremanja ostaje nepotvrđen: nije moguće garantovati tačno-jednom izvršavanje preko takvog prekida.

## Greške i slike

Prije recoveryja faze čuva se izvještaj uz log, u direktoriju `<log>.errors`. Sadrži fazu, posljednju potvrdu, očekivani korak, grešku i PNG BlueStacks prozora kada je snimanje dostupno. Ista poruka ne šalje se ponovo u istom pokretanju; najviše osam izvještaja po pokretanju.

Discord šalje izvještaj i sliku u kanal iz kojeg je pokrenuta skripta, i kada je obični live log isključen. Manager prikazuje lokalnu putanju izvještaja u logu. Ne snima se cijeli desktop niti se koristi desktop kao zamjena ako snimanje BlueStacksa ne uspije. GPU renderovanje može vratiti crnu sliku; tada ide tekstualni izvještaj s razlogom, bez lažne slike.

Slike mogu sadržavati naziv tima i druge podatke vidljive u igri. Koristi privatni Discord kanal ako ih ne želiš dijeliti. Izvještaji ostaju lokalno; nema automatskog brisanja starih slika.

STOP nije greška i sam po sebi ne šalje sliku. Privremeno odbijen AI prijedlog također ne pravi sliku; izvještaji se prave pri izuzetku faze ili završnoj grešci.
