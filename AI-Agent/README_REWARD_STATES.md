# Završetak i restart: zeleni i trening igrača

Od 2026-09-02 ova dva toka razlikuju tekst i boju ciljane ponude:

| Stanje | Postupak |
|---|---|
| Plavo BESPLATNO | Lokalna provjera dugmeta i klik. |
| Sivo/tamno BESPLATNO | Dvije svježe AI potvrde, pauza 10 s, postojeći restart tačne BlueStacks instance, ponovno otvaranje odgovarajućeg toka. |
| OGRAN. DOSTIGNUTO | Dvije svježe AI potvrde; normalan završetak faze. |
| Nepoznato, skriveno dugme ili tačkice učitavanja | Čekanje; nikad dokaz ograničenja niti razlog za restart. Nakon roka prijavljuje grešku, ne uspjeh. |

AI čita samo ponudu zelenih odmora u prodavnici ili besplatnog oporavka KONDICIJE u profilu. Plavi MORAL, plaćeni Unajmi i navigacijski BESPLATNI nisu ciljevi. Posebni AI odgovori ne smiju sadržavati akciju klika. Potvrđene klasifikacije zahtijevaju confidence najmanje 0,90.

Provjere se ponavljaju najranije nakon 12 s i prolaze postojeći zajednički Gemini limiter od najviše 15 zahtjeva u kliznih 60 s. Ove provjere su dodatne u odnosu na prepoznavanje reklamnog X-a; pravilo jedne AI potvrde X-a nije promijenjeno.

Ako je nakon uspješnog restarta ponovo potvrđeno sivo BESPLATNO, ponavlja restart bez starog ograničenja na jedan restart. STOP ostaje dostupan. Greška samog restarta ili neprepoznat ekran i dalje prekidaju rad s greškom.

Zeleni nakon restarta ponovo otvaraju prodavnicu. Trening ponovo otvara IZVJEŠTAJI → PONOVI, svježe čita FIT i pronalazi igrača ispod 30%; ne čuva staru koordinatu igrača preko restarta. Ako je potvrđeno ograničenje, ne pokreće naredni trening.

Sigurnosni limiti trening ciklusa i drugi rokovi ostaju greške, a ne normalan završetak zbog potrošenih reklama. Vizuelna AI klasifikacija nije garancija savršenog prepoznavanja. Automatski testovi pokrivaju validaciju odgovora i simulirane tokove; stvarni API/igra nisu dio tih testova.
