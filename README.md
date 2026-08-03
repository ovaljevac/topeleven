# Top Eleven Agent

CMD izbornik sada nudi dva rezima:

1. **Uzmi 25 zelenih** - pokrece `TopElevenAgent.ps1` u rezimu `Zeleni`.
2. **Odmori ekipu** - pokrece `OdmoriEkipu.ps1`, otvara bocni meni, Trening, Fizio centar i GK plus, a zatim koristi zajednicki tok za BESPLATNO i OpenCV X detekciju.

Rezim **Odmori ekipu** prolazi redom GK, DL, DC, DC, DR, DMC, MC, MC, AML, AMR i ST, zatim ponavlja DL, ST, AMR i AML. Skripta sama bira igraca i skrola, ali kod svakog oglasa ceka da korisnik rucno klikne BESPLATNO i rucno zatvori X.

Detekcija `X` koristi lokalni OpenCV proces iz `XDetector.py`. Detektor skenira gornji desni dio BlueStacks prozora, podrzava svijetli i tamni `X`, vraca stvarni centar i zahtijeva tri stabilna kadra prije klika. OpenCV i NumPy su lokalno spremljeni u `pydeps`; nije potrebna dodatna instalacija.

Aktuelno ponasanje: aplikacija sama klikne **BESPLATNO** čim postane aktivno, sačeka da reklama krene, a zatim sama klikne `X` čim taj X postane dostupan za zatvaranje. Ako klik ne upali (reklama se nije pokrenula, ili `X` klik nije zatvorio reklamu), pokušava još jednom prije nego prijavi grešku.

Ako `X` ne postane dostupan nakon 40 sekundi, aplikacija i dalje prikazuje uputu za poseban tip reklame: rucno otvoriti **Google Play**, preko BlueStacks app switchera vratiti se u Top Eleven i zatim sacekati automatski klik na `X` (ovaj rijedak slučaj i dalje traži ručnu intervenciju jer zahtijeva prebacivanje između aplikacija).

Windows aplikacija automatizira sljedeće korake:

1. pokreće desktop prečicu `Top Eleven - BlueStacks App Player 1.lnk`, koja direktno otvara igru;
2. čeka da se početni ekran igre stvarno učita;
3. pokušava zatvoriti početne popupove pomoću Back/Escape, `X` ili dugmeta `ZATVORI`;
4. otvara prodavnicu zelenim `+` dugmetom uz odmore i provjerava je li se stvarno otvorila;
5. čeka dok dugme **BESPLATNO** ne bude aktivno, pa ga sama klikne;
6. čeka da reklamin `X` postane dostupan, pa ga sama klikne i završi.

## Pokretanje

Dvaput kliknite `Pokreni Top Eleven Agent.cmd`, zatim u kontrolnom prozoru kliknite **POKRENI**.

Za desktop prečicu: desni klik na `Napravi desktop precicu.ps1`, zatim **Run with PowerShell**. Skripta samo napravi prečicu; ne premješta projektne datoteke.

## Važno

- Ne pomjerajte miš dok aplikacija izvršava klikove.
- BlueStacks se automatski maksimizira, a koordinate se računaju prema njegovoj stvarnoj veličini.
- Dugme **ZAUSTAVI** prekida čekanje prije sljedećeg klika.
- Klikovi na BESPLATNO i na X su automatski; ne dirajte miš dok se to dešava, isto kao i za ostale klikove.
- Trenutna konfiguracija odgovara instalaciji `C:\Program Files\BlueStacks_nxt` i instanci `Pie64` pronađenoj na ovom računaru.
